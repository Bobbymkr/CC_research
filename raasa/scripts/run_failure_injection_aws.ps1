param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [int]$TelemetryWindowSeconds = 45,

    [int]$RecoverySeconds = 30,

    [string]$AuditPodRef = "default/raasa-test-malicious-cpu",

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\failure_injection_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

    $telemetryStatuses = @{}
    $metricsApiStatuses = @{}
    $syscallStatuses = @{}
    $memoryStatuses = @{}
    $cpuStatuses = @{}
    $degradedSignals = @{}
    $newTiers = @{}
    $rows = 0
    $parseErrors = 0

    if (Test-Path -LiteralPath $Path) {
        foreach ($line in Get-Content -LiteralPath $Path) {
            if ([string]::IsNullOrWhiteSpace($line)) {
                continue
            }
            try {
                $record = $line | ConvertFrom-Json
                $rows += 1
                Add-MapCount -Map $telemetryStatuses -Value ([string]$record.metadata.telemetry_status)
                Add-MapCount -Map $metricsApiStatuses -Value ([string]$record.metadata.metrics_api_status)
                Add-MapCount -Map $syscallStatuses -Value ([string]$record.metadata.syscall_status)
                Add-MapCount -Map $memoryStatuses -Value ([string]$record.metadata.memory_status)
                Add-MapCount -Map $cpuStatuses -Value ([string]$record.metadata.cpu_status)
                Add-MapCount -Map $degradedSignals -Value ([string]$record.metadata.degraded_signals)
                Add-MapCount -Map $newTiers -Value ([string]$record.new_tier)
            }
            catch {
                $parseErrors += 1
            }
        }
    }

    return [ordered]@{
        rows = $rows
        parse_errors = $parseErrors
        telemetry_statuses = (Format-MapSummary -Map $telemetryStatuses)
        metrics_api_statuses = (Format-MapSummary -Map $metricsApiStatuses)
        syscall_statuses = (Format-MapSummary -Map $syscallStatuses)
        memory_statuses = (Format-MapSummary -Map $memoryStatuses)
        cpu_statuses = (Format-MapSummary -Map $cpuStatuses)
        degraded_signals = (Format-MapSummary -Map $degradedSignals)
        new_tiers = (Format-MapSummary -Map $newTiers)
    }
}

if ($TelemetryWindowSeconds -lt 20) {
    throw "TelemetryWindowSeconds must be at least 20 so stale probe and metrics-cache behavior can be observed."
}
if ($RecoverySeconds -lt 5) {
    throw "RecoverySeconds must be at least 5."
}
if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH to an untracked PEM file."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath
$summaryPath = Join-Path $OutputDir "summary.md"
$metricsOriginalReplicas = $null
$metricsScaledDown = $false
$probePaused = $false
$pausedAgentPod = ""

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

    function Get-AgentPod {
        return ((Invoke-SSH -RemoteCommand "sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o jsonpath='{.items[0].metadata.name}'" -TimeoutSeconds 120) -join "").Trim()
    }

    function Get-RemoteAuditState {
        param(
            [Parameter(Mandatory = $true)]
            [string]$PodRef
        )

        $escapedPodRef = $PodRef.Replace("'", "'`"''")
        $remoteCommand = @'
agent=$(sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
log=""
count=0
if [ -n "$agent" ]; then
  log=$(sudo k3s kubectl exec -n raasa-system "$agent" -c raasa-agent -- sh -c 'ls /app/raasa/logs/*.jsonl 2>/dev/null | tail -1' 2>/dev/null)
  if [ -n "$log" ]; then
    count=$(sudo k3s kubectl exec -n raasa-system "$agent" -c raasa-agent -- env TARGET_LOG="$log" POD_REF='__POD_REF__' sh -c 'cat "$TARGET_LOG" | grep -F -c "$POD_REF" 2>/dev/null || true' 2>/dev/null)
  fi
fi
printf 'timestamp=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
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

    function Capture-AuditDelta {
        param(
            [Parameter(Mandatory = $true)]
            [string]$Label,

            [Parameter(Mandatory = $true)]
            [object]$StateBefore,

            [Parameter(Mandatory = $true)]
            [string]$PodRef
        )

        $auditRowsPath = Join-Path $OutputDir "${Label}_audit_rows.jsonl"
        $auditMetaPath = Join-Path $OutputDir "${Label}_audit_capture.json"
        $auditSummaryPath = Join-Path $OutputDir "${Label}_audit_summary.json"

        $stateAfter = Get-RemoteAuditState -PodRef $PodRef
        $allAuditLines = Get-RemoteAuditLines -AgentPod $stateAfter.AgentPod -LogFile $stateAfter.LogFile -PodRef $PodRef

        $captureMode = "full_end_log"
        $deltaAuditLines = @($allAuditLines)
        if (
            $StateBefore.AgentPod -eq $stateAfter.AgentPod -and
            $StateBefore.LogFile -eq $stateAfter.LogFile -and
            $stateAfter.MatchingLineCount -ge $StateBefore.MatchingLineCount
        ) {
            $captureMode = "delta_from_same_log"
            $deltaAuditLines = @($allAuditLines | Select-Object -Skip $StateBefore.MatchingLineCount)
        }

        $deltaAuditLines | Set-Content -Path $auditRowsPath
        [ordered]@{
            label = $Label
            pod_ref = $PodRef
            capture_mode = $captureMode
            captured_line_count = @($deltaAuditLines).Count
            state_before = $StateBefore
            state_after = $stateAfter
        } | ConvertTo-Json -Depth 6 | Set-Content -Path $auditMetaPath

        $summary = Get-AuditSummary -Path $auditRowsPath
        $summary | ConvertTo-Json -Depth 6 | Set-Content -Path $auditSummaryPath
        return $summary
    }

    @(
        "# Failure Injection Summary",
        "",
        "- Host: $TargetHost",
        "- Audit pod ref: $AuditPodRef",
        "- Telemetry window seconds: $TelemetryWindowSeconds",
        "- Recovery seconds: $RecoverySeconds",
        "- Collected at: $(Get-Date -Format o)",
        ""
    ) | Set-Content -Path $summaryPath

    Save-RemoteOutput -RemoteCommand "date -u '+%Y-%m-%dT%H:%M:%SZ' && hostname && uname -a" -FileName "host_identity.txt" -TimeoutSeconds 60
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get pods -A -o wide" -FileName "pods_before.txt" -TimeoutSeconds 120
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get daemonset raasa-agent -n raasa-system -o wide" -FileName "daemonset_before.txt" -TimeoutSeconds 120

    Add-Content -Path $summaryPath -Value "## Metrics API outage"
    $metricsOriginalReplicasText = ((Invoke-SSH -RemoteCommand "sudo k3s kubectl get deployment metrics-server -n kube-system -o jsonpath='{.spec.replicas}'" -TimeoutSeconds 120) -join "").Trim()
    if ([string]::IsNullOrWhiteSpace($metricsOriginalReplicasText)) {
        $metricsOriginalReplicasText = "1"
    }
    $metricsOriginalReplicas = [int]$metricsOriginalReplicasText
    Add-Content -Path $summaryPath -Value "- Original metrics-server replicas: $metricsOriginalReplicas"

    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods" -FileName "metrics_api_before_raw.json" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    $metricsAuditBefore = Get-RemoteAuditState -PodRef $AuditPodRef
    Invoke-SSH -RemoteCommand "sudo k3s kubectl scale deployment/metrics-server -n kube-system --replicas=0" -TimeoutSeconds 120 | Set-Content -Path (Join-Path $OutputDir "metrics_scale_down.txt")
    $metricsScaledDown = $true
    Start-Sleep -Seconds $TelemetryWindowSeconds
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get pods -n kube-system -l k8s-app=metrics-server -o wide" -FileName "metrics_server_pods_during_outage.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods" -FileName "metrics_api_during_outage_raw.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl logs -n raasa-system -l app=raasa-agent --all-containers=true --tail=240" -FileName "metrics_outage_raasa_tail.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    $metricsAuditSummary = Capture-AuditDelta -Label "metrics_outage" -StateBefore $metricsAuditBefore -PodRef $AuditPodRef
    Add-Content -Path $summaryPath -Value "- Audit rows: $($metricsAuditSummary.rows)"
    Add-Content -Path $summaryPath -Value "- Telemetry statuses: $($metricsAuditSummary.telemetry_statuses)"
    Add-Content -Path $summaryPath -Value "- Metrics API statuses: $($metricsAuditSummary.metrics_api_statuses)"
    Add-Content -Path $summaryPath -Value "- Memory statuses: $($metricsAuditSummary.memory_statuses)"
    Add-Content -Path $summaryPath -Value "- New tiers: $($metricsAuditSummary.new_tiers)"

    Invoke-SSH -RemoteCommand "sudo k3s kubectl scale deployment/metrics-server -n kube-system --replicas=$metricsOriginalReplicas" -TimeoutSeconds 120 | Set-Content -Path (Join-Path $OutputDir "metrics_restore_scale.txt")
    $metricsScaledDown = $false
    Invoke-SSH -RemoteCommand "sudo k3s kubectl rollout status deployment/metrics-server -n kube-system --timeout=180s" -TimeoutSeconds 240 -AllowExitCodes @(0, 1) | Set-Content -Path (Join-Path $OutputDir "metrics_restore_rollout.txt")
    Start-Sleep -Seconds $RecoverySeconds
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods" -FileName "metrics_api_after_restore_raw.json" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Add-Content -Path $summaryPath -Value ""

    Add-Content -Path $summaryPath -Value "## Syscall probe pause"
    $probeAuditBefore = Get-RemoteAuditState -PodRef $AuditPodRef
    $pausedAgentPod = Get-AgentPod
    Add-Content -Path $summaryPath -Value "- Agent pod paused: $pausedAgentPod"
    Invoke-SSH -RemoteCommand "sudo k3s kubectl exec -n raasa-system $pausedAgentPod -c syscall-probe -- sh -lc 'pids=`$(pgrep -f [e]bpf_probe.sh || true); echo `$pids; for pid in `$pids; do kill -STOP `$pid; done'" -TimeoutSeconds 120 | Set-Content -Path (Join-Path $OutputDir "probe_pause.txt")
    $probePaused = $true
    Start-Sleep -Seconds $TelemetryWindowSeconds
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl exec -n raasa-system $pausedAgentPod -c syscall-probe -- sh -lc 'pids=`$(pgrep -f [e]bpf_probe.sh | paste -sd, -); if [ x`$pids != x ]; then ps -o pid,stat,comm,args -p `$pids; else echo no_probe_process; fi'" -FileName "probe_process_during_pause.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl logs -n raasa-system -l app=raasa-agent --all-containers=true --tail=240" -FileName "probe_pause_raasa_tail.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    $probeAuditSummary = Capture-AuditDelta -Label "probe_pause" -StateBefore $probeAuditBefore -PodRef $AuditPodRef
    Add-Content -Path $summaryPath -Value "- Audit rows: $($probeAuditSummary.rows)"
    Add-Content -Path $summaryPath -Value "- Telemetry statuses: $($probeAuditSummary.telemetry_statuses)"
    Add-Content -Path $summaryPath -Value "- Syscall statuses: $($probeAuditSummary.syscall_statuses)"
    Add-Content -Path $summaryPath -Value "- Degraded signals: $($probeAuditSummary.degraded_signals)"
    Add-Content -Path $summaryPath -Value "- New tiers: $($probeAuditSummary.new_tiers)"
    Invoke-SSH -RemoteCommand "sudo k3s kubectl exec -n raasa-system $pausedAgentPod -c syscall-probe -- sh -lc 'pids=`$(pgrep -f [e]bpf_probe.sh || true); echo `$pids; for pid in `$pids; do kill -CONT `$pid; done'" -TimeoutSeconds 120 | Set-Content -Path (Join-Path $OutputDir "probe_resume.txt")
    $probePaused = $false
    Start-Sleep -Seconds $RecoverySeconds
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl logs -n raasa-system $pausedAgentPod -c syscall-probe --tail=120" -FileName "probe_after_resume_tail.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Add-Content -Path $summaryPath -Value ""

    Add-Content -Path $summaryPath -Value "## Enforcer fake-pod fail-closed check"
    $agentForFakeCommand = Get-AgentPod
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl exec -n raasa-system $agentForFakeCommand -c raasa-enforcer -- tc qdisc show dev cni0" -FileName "fake_pod_cni0_qdisc_before.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    $fakePython = "socket=__import__(bytes([115,111,99,107,101,116]).decode());json=__import__(bytes([106,115,111,110]).decode());s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect(bytes([47,118,97,114,47,114,117,110,47,114,97,97,115,97,47,101,110,102,111,114,99,101,114,46,115,111,99,107]).decode());s.sendall((json.dumps(dict(container_id=bytes([100,101,102,97,117,108,116,47,114,97,97,115,97,45,110,111,110,101,120,105,115,116,101,110,116,45,112,111,100]).decode(),tier=bytes([76,51]).decode()))+bytes([10]).decode()).encode());print(s.recv(1024).decode().strip());s.close()"
    $fakeCommand = "sudo k3s kubectl exec -n raasa-system $agentForFakeCommand -c raasa-agent -- python -c '$fakePython'"
    $fakeResponse = @(Invoke-SSH -RemoteCommand $fakeCommand -TimeoutSeconds 120 -AllowExitCodes @(0, 1))
    $fakeResponse | Set-Content -Path (Join-Path $OutputDir "fake_pod_ipc_response.txt")
    Start-Sleep -Seconds 5
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl exec -n raasa-system $agentForFakeCommand -c raasa-enforcer -- tc qdisc show dev cni0" -FileName "fake_pod_cni0_qdisc_after.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl logs -n raasa-system $agentForFakeCommand -c raasa-enforcer --tail=120" -FileName "fake_pod_enforcer_tail.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Add-Content -Path $summaryPath -Value "- IPC response: $(($fakeResponse -join ' ').Trim())"
    Add-Content -Path $summaryPath -Value "- Expected response: ERR"
    Add-Content -Path $summaryPath -Value ""

    Add-Content -Path $summaryPath -Value "## Agent restart recovery"
    $agentBeforeRestart = Get-AgentPod
    Add-Content -Path $summaryPath -Value "- Agent pod before restart: $agentBeforeRestart"
    Invoke-SSH -RemoteCommand "sudo k3s kubectl delete pod -n raasa-system $agentBeforeRestart --wait=false" -TimeoutSeconds 120 | Set-Content -Path (Join-Path $OutputDir "agent_delete.txt")
    Invoke-SSH -RemoteCommand "sudo k3s kubectl rollout status daemonset/raasa-agent -n raasa-system --timeout=300s" -TimeoutSeconds 360 -AllowExitCodes @(0, 1) | Set-Content -Path (Join-Path $OutputDir "agent_restart_rollout.txt")
    Start-Sleep -Seconds $RecoverySeconds
    $agentAfterRestart = Get-AgentPod
    Add-Content -Path $summaryPath -Value "- Agent pod after restart: $agentAfterRestart"
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o wide" -FileName "agent_pods_after_restart.txt" -TimeoutSeconds 120
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get pods -A -o wide" -FileName "pods_after.txt" -TimeoutSeconds 120
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods" -FileName "metrics_api_after_agent_restart_raw.json" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl logs -n raasa-system $agentAfterRestart -c raasa-agent --tail=160" -FileName "agent_after_restart_tail.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)

    Write-Host "Failure injection evidence collected in: $OutputDir"
}
finally {
    if ($probePaused -and -not [string]::IsNullOrWhiteSpace($pausedAgentPod)) {
        try {
            Invoke-SSH -RemoteCommand "sudo k3s kubectl exec -n raasa-system $pausedAgentPod -c syscall-probe -- sh -lc 'pids=`$(pgrep -f [e]bpf_probe.sh || true); for pid in `$pids; do kill -CONT `$pid; done'" -TimeoutSeconds 60 -AllowExitCodes @(0, 1) | Out-Null
        }
        catch {
            try {
                Invoke-SSH -RemoteCommand "sudo k3s kubectl delete pod -n raasa-system $pausedAgentPod --wait=false && sudo k3s kubectl rollout status daemonset/raasa-agent -n raasa-system --timeout=300s" -TimeoutSeconds 360 -AllowExitCodes @(0, 1) | Out-Null
            }
            catch {
            }
        }
    }

    if ($metricsScaledDown -and $null -ne $metricsOriginalReplicas) {
        try {
            Invoke-SSH -RemoteCommand "sudo k3s kubectl scale deployment/metrics-server -n kube-system --replicas=$metricsOriginalReplicas && sudo k3s kubectl rollout status deployment/metrics-server -n kube-system --timeout=180s" -TimeoutSeconds 240 -AllowExitCodes @(0, 1) | Out-Null
        }
        catch {
        }
    }

    if (Test-Path -LiteralPath $tempKey) {
        try {
            Remove-Item -LiteralPath $tempKey -Force -ErrorAction Stop
        }
        catch {
            Write-Warning "Could not remove temporary key copy: $tempKey"
        }
    }
}

exit 0
