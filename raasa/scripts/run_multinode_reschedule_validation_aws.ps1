param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [int]$DrainTimeoutSeconds = 300,

    [int]$PostDrainObservationSeconds = 45,

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\multinode_reschedule_validation_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-RestrictedKeyCopy {
    param([string]$SourcePath)

    $tempPath = Join-Path $env:TEMP ("raasa-key-" + [guid]::NewGuid().ToString() + ".pem")
    Copy-Item -LiteralPath $SourcePath -Destination $tempPath -Force

    $identity = "$env:USERDOMAIN\$env:USERNAME"
    $acl = New-Object System.Security.AccessControl.FileSecurity
    $owner = New-Object System.Security.Principal.NTAccount($identity)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, "FullControl", "Allow")

    $acl.SetOwner($owner)
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $tempPath -AclObject $acl

    return $tempPath
}

function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,

        [Parameter(Mandatory = $true)]
        [string]$ErrorContext,

        [int]$TimeoutSeconds = 300,

        [int[]]$AllowExitCodes = @(0)
    )

    $stdoutPath = Join-Path $env:TEMP ("raasa-stdout-" + [guid]::NewGuid().ToString() + ".txt")
    $stderrPath = Join-Path $env:TEMP ("raasa-stderr-" + [guid]::NewGuid().ToString() + ".txt")

    try {
        $process = Start-Process `
            -FilePath $FilePath `
            -ArgumentList $ArgumentList `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath

        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill() } catch {}
            throw "$ErrorContext timed out after $TimeoutSeconds seconds."
        }

        $process.WaitForExit()
        $process.Refresh()
        $exitCode = [int]$process.ExitCode

        $output = @()
        if (Test-Path -LiteralPath $stdoutPath) { $output += Get-Content -LiteralPath $stdoutPath }
        if (Test-Path -LiteralPath $stderrPath) { $output += Get-Content -LiteralPath $stderrPath }

        if ($exitCode -notin $AllowExitCodes) {
            $joined = ($output -join [Environment]::NewLine).Trim()
            if ($joined) {
                throw "$ErrorContext failed with exit code $exitCode.`n$joined"
            }
            throw "$ErrorContext failed with exit code $exitCode."
        }

        return [pscustomobject]@{
            ExitCode = $exitCode
            Output   = @($output)
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath
$summaryPath = Join-Path $OutputDir "summary.md"
$remoteKubeconfigPath = if ($User -eq "root") { "/root/.kube/config" } else { "/home/$User/.kube/config" }
$namespace = "raasa-resched"
$drainedWorker = ""
$labelsApplied = $false
$workerA = ""
$workerB = ""

try {
    function Invoke-SSH {
        param(
            [Parameter(Mandatory = $true)]
            [string]$RemoteCommand,

            [int]$TimeoutSeconds = 300,

            [int[]]$AllowExitCodes = @(0)
        )

        $args = @(
            "-n",
            "-i", $tempKey,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=NUL",
            "-o", "LogLevel=ERROR",
            "-o", "ServerAliveInterval=5",
            "-o", "ServerAliveCountMax=6",
            "$User@$TargetHost",
            $RemoteCommand
        )

        $result = Invoke-NativeCapture `
            -FilePath "C:\WINDOWS\System32\OpenSSH\ssh.exe" `
            -ArgumentList $args `
            -ErrorContext "SSH command" `
            -TimeoutSeconds $TimeoutSeconds `
            -AllowExitCodes $AllowExitCodes

        return @($result.Output)
    }

    function Save-RemoteOutput {
        param(
            [Parameter(Mandatory = $true)]
            [string]$RemoteCommand,

            [Parameter(Mandatory = $true)]
            [string]$FileName,

            [int]$TimeoutSeconds = 120,

            [int[]]$AllowExitCodes = @(0)
        )

        Invoke-SSH -RemoteCommand $RemoteCommand -TimeoutSeconds $TimeoutSeconds -AllowExitCodes $AllowExitCodes |
            Set-Content -Path (Join-Path $OutputDir $FileName)
    }

    function Get-WorkerNodeNames {
        $raw = (Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get nodes -o json" -TimeoutSeconds 120) -join [Environment]::NewLine
        $parsed = $raw | ConvertFrom-Json
        $workers = @()
        foreach ($item in @($parsed.items)) {
            $labels = $item.metadata.labels
            $isControlPlane = $labels.PSObject.Properties.Name -contains "node-role.kubernetes.io/control-plane"
            if (-not $isControlPlane) {
                $workers += [string]$item.metadata.name
            }
        }
        return @($workers | Sort-Object)
    }

    function Get-PodNodeName {
        param(
            [string]$NamespaceName,
            [string]$PodName
        )

        return ((Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get pod -n $NamespaceName $PodName -o jsonpath='{.spec.nodeName}'" -TimeoutSeconds 120) -join "").Trim()
    }

    function Get-AgentPodOnNode {
        param([string]$NodeName)

        return ((Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get pods -n raasa-system -l app=raasa-agent --field-selector spec.nodeName=$NodeName -o jsonpath='{.items[0].metadata.name}'" -TimeoutSeconds 120) -join "").Trim()
    }

    function Wait-ForAuditEvidence {
        param(
            [string]$AgentPod,
            [string]$PodRef,
            [int]$TimeoutSeconds = 90
        )

        $escapedPodRef = $PodRef.Replace("'", "'`''")
        $remoteCommand = @'
export KUBECONFIG="__REMOTE_KUBECONFIG__"
log_file=$(kubectl exec -n raasa-system __AGENT_POD__ -c raasa-agent -- sh -c 'ls -t /app/raasa/logs/run_*.jsonl 2>/dev/null | head -n 1' 2>/dev/null)
if [ -n "$log_file" ]; then
  kubectl exec -n raasa-system __AGENT_POD__ -c raasa-agent -- env TARGET_LOG="$log_file" POD_REF='__POD_REF__' sh -c 'grep -F "$POD_REF" "$TARGET_LOG" | tail -n 5' 2>/dev/null
fi
'@
        $remoteCommand = $remoteCommand.Replace("__REMOTE_KUBECONFIG__", $remoteKubeconfigPath)
        $remoteCommand = $remoteCommand.Replace("__AGENT_POD__", $AgentPod)
        $remoteCommand = $remoteCommand.Replace("__POD_REF__", $escapedPodRef)
        $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
        do {
            $lines = @(Invoke-SSH -RemoteCommand $remoteCommand -TimeoutSeconds 120 -AllowExitCodes @(0, 1))
            if (@($lines | Where-Object { $_ -match '"telemetry_status"' }).Count -gt 0) {
                return @($lines)
            }
            Start-Sleep -Seconds 5
        } while ((Get-Date) -lt $deadline)
        return @($lines)
    }

    @(
        "# Multi-node Reschedule Validation Summary",
        "",
        "- Target host: $TargetHost",
        "- Collected at: $(Get-Date -Format o)",
        ""
    ) | Set-Content -Path $summaryPath

    Save-RemoteOutput -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get nodes -o wide" -FileName "nodes_before.txt" -TimeoutSeconds 120
    Save-RemoteOutput -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get pods -A -o wide" -FileName "pods_before.txt" -TimeoutSeconds 120

    $workers = @(Get-WorkerNodeNames)
    if ($workers.Count -lt 2) {
        throw "Expected at least two worker nodes, found $($workers.Count)."
    }

    $workerA = [string]$workers[0]
    $workerB = [string]$workers[1]
    $drainedWorker = $workerA

    Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl label node $workerA raasa.validation-pool=worker raasa.validation-role=worker-a --overwrite; kubectl label node $workerB raasa.validation-pool=worker raasa.validation-role=worker-b --overwrite" -TimeoutSeconds 120 | Set-Content -Path (Join-Path $OutputDir "node_labels.txt")
    $labelsApplied = $true

    $initialManifest = @"
apiVersion: v1
kind: Namespace
metadata:
  name: $namespace
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: raasa-resched-benign
  namespace: $namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: raasa-resched-benign
  template:
    metadata:
      labels:
        app: raasa-resched-benign
        raasa.class: benign
        raasa.expected_tier: L1
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: raasa.validation-role
                    operator: In
                    values:
                      - worker-a
      containers:
        - name: workload
          image: ubuntu:24.04
          command: ["sleep", "infinity"]
          resources:
            requests:
              cpu: "50m"
              memory: "32Mi"
            limits:
              cpu: "250m"
              memory: "128Mi"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: raasa-resched-malicious
  namespace: $namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: raasa-resched-malicious
  template:
    metadata:
      labels:
        app: raasa-resched-malicious
        raasa.class: malicious
        raasa.expected_tier: L3
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: raasa.validation-role
                    operator: In
                    values:
                      - worker-b
      containers:
        - name: workload
          image: ubuntu:24.04
          command:
            - sh
            - -c
            - |
              apt-get update -qq && apt-get install -y -qq stress-ng >/dev/null 2>&1
              stress-ng --cpu 1 --vm 1 --fork 8 --timeout 0
          resources:
            requests:
              cpu: "100m"
              memory: "64Mi"
            limits:
              cpu: "1000m"
              memory: "512Mi"
"@
    $initialRemote = "/tmp/raasa-multinode-resched-initial.yaml"
    $initialLocal = Join-Path $env:TEMP ("raasa-multinode-resched-initial-" + [guid]::NewGuid().ToString() + ".yaml")
    $initialManifest | Set-Content -Path $initialLocal
    try {
        $scpArgs = @(
            "-i", $tempKey,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=NUL",
            "-o", "LogLevel=ERROR",
            $initialLocal,
            "${User}@${TargetHost}:$initialRemote"
        )
        Invoke-NativeCapture -FilePath "C:\WINDOWS\System32\OpenSSH\scp.exe" -ArgumentList $scpArgs -ErrorContext "Copy initial reschedule manifest" -TimeoutSeconds 120 -AllowExitCodes @(0) | Out-Null
    }
    finally {
        Remove-Item -LiteralPath $initialLocal -Force -ErrorAction SilentlyContinue
    }

    Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl apply -f $initialRemote" -TimeoutSeconds 120 | Set-Content -Path (Join-Path $OutputDir "apply_initial_manifest.txt")
    Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl rollout status deployment/raasa-resched-benign -n $namespace --timeout=240s; kubectl rollout status deployment/raasa-resched-malicious -n $namespace --timeout=240s" -TimeoutSeconds 300 | Set-Content -Path (Join-Path $OutputDir "initial_rollouts.txt")
    Save-RemoteOutput -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get pods -n $namespace -o wide" -FileName "resched_pods_before_drain.txt" -TimeoutSeconds 120

    $benignInitialPod = ((Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get pods -n $namespace -l app=raasa-resched-benign -o jsonpath='{.items[0].metadata.name}'" -TimeoutSeconds 120) -join "").Trim()
    $maliciousPod = ((Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get pods -n $namespace -l app=raasa-resched-malicious -o jsonpath='{.items[0].metadata.name}'" -TimeoutSeconds 120) -join "").Trim()
    $benignInitialNode = Get-PodNodeName -NamespaceName $namespace -PodName $benignInitialPod
    $maliciousNode = Get-PodNodeName -NamespaceName $namespace -PodName $maliciousPod
    if ($benignInitialNode -ne $workerA) {
        throw "Benign workload did not land on worker-a. Found $benignInitialNode."
    }
    if ($maliciousNode -ne $workerB) {
        throw "Malicious workload did not land on worker-b. Found $maliciousNode."
    }

    $relaxedManifest = @"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: raasa-resched-benign
  namespace: $namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: raasa-resched-benign
  template:
    metadata:
      labels:
        app: raasa-resched-benign
        raasa.class: benign
        raasa.expected_tier: L1
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: raasa.validation-pool
                    operator: In
                    values:
                      - worker
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              preference:
                matchExpressions:
                  - key: raasa.validation-role
                    operator: In
                    values:
                      - worker-a
      containers:
        - name: workload
          image: ubuntu:24.04
          command: ["sleep", "infinity"]
          resources:
            requests:
              cpu: "50m"
              memory: "32Mi"
            limits:
              cpu: "250m"
              memory: "128Mi"
"@
    $relaxedRemote = "/tmp/raasa-multinode-resched-relaxed.yaml"
    $relaxedLocal = Join-Path $env:TEMP ("raasa-multinode-resched-relaxed-" + [guid]::NewGuid().ToString() + ".yaml")
    $relaxedManifest | Set-Content -Path $relaxedLocal
    try {
        $scpArgs = @(
            "-i", $tempKey,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=NUL",
            "-o", "LogLevel=ERROR",
            $relaxedLocal,
            "${User}@${TargetHost}:$relaxedRemote"
        )
        Invoke-NativeCapture -FilePath "C:\WINDOWS\System32\OpenSSH\scp.exe" -ArgumentList $scpArgs -ErrorContext "Copy relaxed reschedule manifest" -TimeoutSeconds 120 -AllowExitCodes @(0) | Out-Null
    }
    finally {
        Remove-Item -LiteralPath $relaxedLocal -Force -ErrorAction SilentlyContinue
    }

    Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl apply -f $relaxedRemote" -TimeoutSeconds 120 | Set-Content -Path (Join-Path $OutputDir "apply_relaxed_manifest.txt")
    Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl drain $workerA --ignore-daemonsets --delete-emptydir-data --force --grace-period=30 --timeout=${DrainTimeoutSeconds}s" -TimeoutSeconds ($DrainTimeoutSeconds + 120) -AllowExitCodes @(0, 1) | Set-Content -Path (Join-Path $OutputDir "drain_worker_a.txt")
    Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl rollout status deployment/raasa-resched-benign -n $namespace --timeout=300s" -TimeoutSeconds 360 | Set-Content -Path (Join-Path $OutputDir "benign_rollout_after_drain.txt")
    Start-Sleep -Seconds $PostDrainObservationSeconds

    Save-RemoteOutput -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get nodes -o wide" -FileName "nodes_after_drain.txt" -TimeoutSeconds 120
    Save-RemoteOutput -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get pods -A -o wide" -FileName "pods_after_drain.txt" -TimeoutSeconds 120
    Save-RemoteOutput -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get pods -n $namespace -o wide" -FileName "resched_pods_after_drain.txt" -TimeoutSeconds 120

    $benignFinalPod = ((Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl get pods -n $namespace -l app=raasa-resched-benign -o jsonpath='{.items[0].metadata.name}'" -TimeoutSeconds 120) -join "").Trim()
    $benignFinalNode = Get-PodNodeName -NamespaceName $namespace -PodName $benignFinalPod
    if ($benignFinalNode -ne $workerB) {
        throw "Benign workload did not reschedule onto worker-b after draining worker-a. Found $benignFinalNode."
    }

    $agentPodOnWorkerB = Get-AgentPodOnNode -NodeName $workerB
    if ([string]::IsNullOrWhiteSpace($agentPodOnWorkerB)) {
        throw "Could not resolve RAASA agent pod on $workerB."
    }

    $benignAuditLines = @(Wait-ForAuditEvidence -AgentPod $agentPodOnWorkerB -PodRef "$namespace/$benignFinalPod" -TimeoutSeconds 90)
    $maliciousAuditLines = @(Wait-ForAuditEvidence -AgentPod $agentPodOnWorkerB -PodRef "$namespace/$maliciousPod" -TimeoutSeconds 90)
    $benignAuditLines | Set-Content -Path (Join-Path $OutputDir "benign_rescheduled_audit_rows.jsonl")
    $maliciousAuditLines | Set-Content -Path (Join-Path $OutputDir "malicious_worker_b_audit_rows.jsonl")

    if (@($benignAuditLines | Where-Object { $_ -match '"telemetry_status"' }).Count -eq 0) {
        throw "No interpretable audit rows were found for the benign workload after reschedule."
    }
    if (@($maliciousAuditLines | Where-Object { $_ -match '"telemetry_status"' }).Count -eq 0) {
        throw "No interpretable audit rows were found for the malicious workload on worker-b."
    }

    Save-RemoteOutput -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl logs -n raasa-system $agentPodOnWorkerB -c raasa-agent --tail=160" -FileName "agent_worker_b_after_drain_tail.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl logs -n raasa-system $agentPodOnWorkerB -c raasa-enforcer --tail=160" -FileName "enforcer_worker_b_after_drain_tail.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)

    Add-Content -Path $summaryPath -Value "- Worker A: $workerA"
    Add-Content -Path $summaryPath -Value "- Worker B: $workerB"
    Add-Content -Path $summaryPath -Value "- Benign pod before drain: $benignInitialPod on $benignInitialNode"
    Add-Content -Path $summaryPath -Value "- Malicious pod stayed on: $maliciousNode"
    Add-Content -Path $summaryPath -Value "- Benign pod after drain: $benignFinalPod on $benignFinalNode"
    Add-Content -Path $summaryPath -Value "- Agent pod used for post-drain audit verification: $agentPodOnWorkerB"

    Write-Host "Multi-node reschedule evidence collected in: $OutputDir"
}
finally {
    try {
        Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl delete namespace $namespace --ignore-not-found=true" -TimeoutSeconds 180 -AllowExitCodes @(0, 1) | Out-Null
    }
    catch {
    }
    if ($labelsApplied) {
        try {
            $cleanupCommand = @(
                "export KUBECONFIG='$remoteKubeconfigPath'"
            )
            if (-not [string]::IsNullOrWhiteSpace($workerA)) {
                $cleanupCommand += "kubectl label node $workerA raasa.validation-pool- raasa.validation-role- --overwrite"
            }
            if (-not [string]::IsNullOrWhiteSpace($workerB)) {
                $cleanupCommand += "kubectl label node $workerB raasa.validation-pool- raasa.validation-role- --overwrite"
            }
            Invoke-SSH -RemoteCommand ($cleanupCommand -join "; ") -TimeoutSeconds 120 -AllowExitCodes @(0, 1) | Out-Null
        }
        catch {
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($drainedWorker)) {
        try {
            Invoke-SSH -RemoteCommand "export KUBECONFIG='$remoteKubeconfigPath'; kubectl uncordon $drainedWorker" -TimeoutSeconds 120 -AllowExitCodes @(0, 1) | Out-Null
        }
        catch {
        }
    }
    Remove-Item -LiteralPath $tempKey -Force -ErrorAction SilentlyContinue
}
