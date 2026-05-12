param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [int]$DurationSeconds = 45,

    [int]$WorkerCount = 8,

    [int]$CooldownSeconds = 10,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\metrics_api_stress_probe_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

if ($DurationSeconds -lt 1) {
    throw "DurationSeconds must be at least 1."
}
if ($WorkerCount -lt 1) {
    throw "WorkerCount must be at least 1."
}
if ($CooldownSeconds -lt 0) {
    throw "CooldownSeconds must be >= 0."
}
if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH to an untracked PEM file."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath
$remoteScript = "/tmp/raasa-metrics-stress-" + [guid]::NewGuid().ToString() + ".sh"
$localScript = Join-Path $env:TEMP ("raasa-metrics-stress-" + [guid]::NewGuid().ToString() + ".sh")

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

            [int]$TimeoutSeconds = 180,

            [int[]]$AllowExitCodes = @(0)
        )

        $output = @(Invoke-SSH -RemoteCommand $RemoteCommand -TimeoutSeconds $TimeoutSeconds -AllowExitCodes $AllowExitCodes)
        Set-Content -Path (Join-Path $OutputDir $FileName) -Value $output
    }

    function Get-RemoteAuditCursor {
        $remoteCommand = @'
agent=$(sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
log=""
count=0
if [ -n "$agent" ]; then
  log=$(sudo k3s kubectl exec -n raasa-system "$agent" -c raasa-agent -- sh -c 'ls -t /app/raasa/logs/run_*.jsonl 2>/dev/null | head -n 1' 2>/dev/null)
  if [ -n "$log" ]; then
    count=$(sudo k3s kubectl exec -n raasa-system "$agent" -c raasa-agent -- env TARGET_LOG="$log" sh -c 'wc -l < "$TARGET_LOG"' 2>/dev/null || echo 0)
  fi
fi
printf 'timestamp=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
printf 'agent=%s\n' "$agent"
printf 'log=%s\n' "$log"
printf 'count=%s\n' "$count"
'@
        $lines = Invoke-SSH -RemoteCommand $remoteCommand -TimeoutSeconds 180

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
            TimestampUtc = if ($stateMap.ContainsKey("timestamp")) { [string]$stateMap["timestamp"] } else { "" }
            AgentPod = if ($stateMap.ContainsKey("agent")) { [string]$stateMap["agent"] } else { "" }
            LogFile = if ($stateMap.ContainsKey("log")) { [string]$stateMap["log"] } else { "" }
            TotalLineCount = $countValue
        }
    }

    function Get-ShellSingleQuoted {
        param([AllowEmptyString()][string]$Value)

        if ($null -eq $Value) {
            return "''"
        }
        if ($Value.Contains("'")) {
            throw "Single quotes are not supported in shell-quoted values: $Value"
        }
        return "'$Value'"
    }

    function Invoke-AgentPython {
        param(
            [Parameter(Mandatory = $true)]
            [string]$AgentPod,

            [Parameter(Mandatory = $true)]
            [string]$PythonBody,

            [hashtable]$Environment = @{}
        )

        $localPythonScript = Join-Path $env:TEMP ("raasa-agent-python-" + [guid]::NewGuid().ToString() + ".py")
        $remotePythonScript = "/tmp/" + [System.IO.Path]::GetFileName($localPythonScript)

        try {
            $PythonBody | Set-Content -Path $localPythonScript
            Copy-Remote -LocalPath $localPythonScript -RemotePath $remotePythonScript

            $envAssignments = @()
            foreach ($key in ($Environment.Keys | Sort-Object)) {
                $envAssignments += ("{0}={1}" -f $key, (Get-ShellSingleQuoted -Value ([string]$Environment[$key])))
            }

            $containerPrefix = if ($envAssignments.Count -gt 0) {
                "env " + ($envAssignments -join " ") + " "
            }
            else {
                ""
            }

            $remoteCommand = "sudo k3s kubectl exec -i -n raasa-system $AgentPod -c raasa-agent -- ${containerPrefix}python - < $remotePythonScript"
            $output = @(Invoke-SSH -RemoteCommand $remoteCommand -TimeoutSeconds 180 -AllowExitCodes @(0))
            return ($output -join [Environment]::NewLine).Trim()
        }
        finally {
            if (Test-Path -LiteralPath $localPythonScript) {
                Remove-Item -LiteralPath $localPythonScript -Force -ErrorAction SilentlyContinue
            }
            try {
                Invoke-SSH -RemoteCommand "rm -f $remotePythonScript" -TimeoutSeconds 30 -AllowExitCodes @(0) | Out-Null
            }
            catch {
            }
        }
    }

    function Get-RemoteAuditLines {
        param(
            [Parameter(Mandatory = $true)]
            [string]$AgentPod,

            [Parameter(Mandatory = $true)]
            [string]$LogFile,

            [Parameter(Mandatory = $true)]
            [int]$StartLine,

            [Parameter(Mandatory = $true)]
            [string[]]$TargetRefs
        )

        if ([string]::IsNullOrWhiteSpace($AgentPod) -or [string]::IsNullOrWhiteSpace($LogFile)) {
            return @()
        }

        $envMap = @{
            TARGET_LOG = $LogFile
            START_LINE = [string]$StartLine
        }
        for ($index = 0; $index -lt $TargetRefs.Count; $index++) {
            $envMap["TARGET_REF_$index"] = $TargetRefs[$index]
        }

        $pythonBody = @'
import json
import os
from pathlib import Path

target_log = Path(os.environ["TARGET_LOG"])
start_line = int(os.environ["START_LINE"])
target_refs = {
    value
    for key, value in os.environ.items()
    if key.startswith("TARGET_REF_") and value
}

if target_log.exists():
    with target_log.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if index <= start_line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("container_id") in target_refs:
                print(line.rstrip("\n"))
'@
        $output = Invoke-AgentPython -AgentPod $AgentPod -PythonBody $pythonBody -Environment $envMap
        if ([string]::IsNullOrWhiteSpace($output)) {
            return @()
        }
        return @($output -split "`r?`n")
    }

    function Format-MapSummary {
        param([hashtable]$Map)

        if ($null -eq $Map -or $Map.Count -eq 0) {
            return "none"
        }

        return (($Map.Keys | Sort-Object) | ForEach-Object { "${_}:$($Map[$_])" }) -join ","
    }

    function Get-AuditRowsSummary {
        param(
            [Parameter(Mandatory = $true)]
            [string]$Path
        )

        $rows = 0
        $reasons = @{}
        $metricsApiStatuses = @{}
        $memoryStatuses = @{}
        $cpuStatuses = @{}
        $telemetryStatuses = @{}
        $containerCounts = @{}

        if (-not (Test-Path -LiteralPath $Path)) {
            return @{
                rows = 0
                reasons = "none"
                metrics_api_statuses = "none"
                memory_statuses = "none"
                cpu_statuses = "none"
                telemetry_statuses = "none"
                containers = "none"
            }
        }

        foreach ($line in Get-Content -LiteralPath $Path) {
            if ([string]::IsNullOrWhiteSpace($line)) {
                continue
            }

            try {
                $record = $line | ConvertFrom-Json
            }
            catch {
                continue
            }

            $rows += 1

            $containerId = [string]$record.container_id
            if (-not [string]::IsNullOrWhiteSpace($containerId)) {
                if (-not $containerCounts.ContainsKey($containerId)) {
                    $containerCounts[$containerId] = 0
                }
                $containerCounts[$containerId] += 1
            }

            $reason = [string]$record.reason
            if (-not [string]::IsNullOrWhiteSpace($reason)) {
                if (-not $reasons.ContainsKey($reason)) {
                    $reasons[$reason] = 0
                }
                $reasons[$reason] += 1
            }

            $metricsApiStatus = [string]$record.metadata.metrics_api_status
            if (-not [string]::IsNullOrWhiteSpace($metricsApiStatus)) {
                if (-not $metricsApiStatuses.ContainsKey($metricsApiStatus)) {
                    $metricsApiStatuses[$metricsApiStatus] = 0
                }
                $metricsApiStatuses[$metricsApiStatus] += 1
            }

            $memoryStatus = [string]$record.metadata.memory_status
            if (-not [string]::IsNullOrWhiteSpace($memoryStatus)) {
                if (-not $memoryStatuses.ContainsKey($memoryStatus)) {
                    $memoryStatuses[$memoryStatus] = 0
                }
                $memoryStatuses[$memoryStatus] += 1
            }

            $cpuStatus = [string]$record.metadata.cpu_status
            if (-not [string]::IsNullOrWhiteSpace($cpuStatus)) {
                if (-not $cpuStatuses.ContainsKey($cpuStatus)) {
                    $cpuStatuses[$cpuStatus] = 0
                }
                $cpuStatuses[$cpuStatus] += 1
            }

            $telemetryStatus = [string]$record.metadata.telemetry_status
            if (-not [string]::IsNullOrWhiteSpace($telemetryStatus)) {
                if (-not $telemetryStatuses.ContainsKey($telemetryStatus)) {
                    $telemetryStatuses[$telemetryStatus] = 0
                }
                $telemetryStatuses[$telemetryStatus] += 1
            }
        }

        return @{
            rows = $rows
            reasons = (Format-MapSummary -Map $reasons)
            metrics_api_statuses = (Format-MapSummary -Map $metricsApiStatuses)
            memory_statuses = (Format-MapSummary -Map $memoryStatuses)
            cpu_statuses = (Format-MapSummary -Map $cpuStatuses)
            telemetry_statuses = (Format-MapSummary -Map $telemetryStatuses)
            containers = (Format-MapSummary -Map $containerCounts)
        }
    }

    $agentPod = (Invoke-SSH -RemoteCommand "sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o jsonpath='{.items[0].metadata.name}'").Trim()
    if (-not $agentPod) {
        throw "Could not resolve raasa-agent pod name."
    }

    $benignComputePod = (Invoke-SSH -RemoteCommand "sudo k3s kubectl get pods -n default -l app=raasa-test,raasa.class=benign,raasa.expected_tier=L2 -o jsonpath='{.items[0].metadata.name}'").Trim()
    $benignSteadyPod = (Invoke-SSH -RemoteCommand "sudo k3s kubectl get pods -n default -l app=raasa-test,raasa.class=benign,raasa.expected_tier=L1 -o jsonpath='{.items[0].metadata.name}'").Trim()
    $maliciousPod = (Invoke-SSH -RemoteCommand "sudo k3s kubectl get pods -n default -l app=raasa-test,raasa.class=malicious -o jsonpath='{.items[0].metadata.name}'").Trim()

    if (-not $benignComputePod -or -not $benignSteadyPod -or -not $maliciousPod) {
        throw "Could not resolve one or more default test pods for the Metrics API probe."
    }

    $auditTargetRefs = @(
        "default/$benignComputePod",
        "default/$benignSteadyPod",
        "default/$maliciousPod"
    )

    $remoteScriptTemplate = @'
#!/usr/bin/env bash
set -u

duration=__DURATION_SECONDS__
workers=__WORKER_COUNT__
summary_file="/tmp/raasa-metrics-stress-summary.txt"
failure_file="/tmp/raasa-metrics-stress-failures.txt"

targets=(
  "/apis/metrics.k8s.io/v1beta1/namespaces/default/pods/__BENIGN_COMPUTE_POD__"
  "/apis/metrics.k8s.io/v1beta1/namespaces/default/pods/__BENIGN_STEADY_POD__"
  "/apis/metrics.k8s.io/v1beta1/namespaces/default/pods/__MALICIOUS_POD__"
  "/apis/metrics.k8s.io/v1beta1/namespaces/default/pods"
  "/apis/metrics.k8s.io/v1beta1/pods"
)

: > "$summary_file"
: > "$failure_file"

run_worker() {
  local id="$1"
  local end=$((SECONDS + duration))
  local ok=0
  local fail=0

  while [ "$SECONDS" -lt "$end" ]; do
    for target in "${targets[@]}"; do
      if sudo k3s kubectl get --raw "$target" >/dev/null 2>>"$failure_file"; then
        ok=$((ok + 1))
      else
        fail=$((fail + 1))
      fi
    done
  done

  printf 'worker=%s ok=%s fail=%s\n' "$id" "$ok" "$fail" >> "$summary_file"
}

for worker_id in $(seq 1 "$workers"); do
  run_worker "$worker_id" &
done
wait

total_failures=0
if [ -f "$failure_file" ]; then
  total_failures=$(wc -l "$failure_file" | awk '{print $1}')
fi

printf 'total_failures=%s\n' "$total_failures" >> "$summary_file"
cat "$summary_file"
'@
    $remoteScriptContent = $remoteScriptTemplate.
        Replace("__DURATION_SECONDS__", [string]$DurationSeconds).
        Replace("__WORKER_COUNT__", [string]$WorkerCount).
        Replace("__BENIGN_COMPUTE_POD__", $benignComputePod).
        Replace("__BENIGN_STEADY_POD__", $benignSteadyPod).
        Replace("__MALICIOUS_POD__", $maliciousPod)
    $remoteScriptContent | Set-Content -Path $localScript

    Copy-Remote -LocalPath $localScript -RemotePath $remoteScript
    Invoke-SSH -RemoteCommand "sed -i 's/\r$//' $remoteScript && chmod +x $remoteScript" -TimeoutSeconds 60 | Out-Null

    @(
        "Host=$TargetHost",
        "User=$User",
        "DurationSeconds=$DurationSeconds",
        "WorkerCount=$WorkerCount",
        "CooldownSeconds=$CooldownSeconds",
        "AgentPod=$agentPod",
        "BenignComputePod=$benignComputePod",
        "BenignSteadyPod=$benignSteadyPod",
        "MaliciousPod=$maliciousPod",
        "CollectedAtLocal=" + (Get-Date).ToString("o")
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-agent --tail=120" -FileName "agent_logs_before.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl logs -n kube-system deploy/metrics-server --tail=120" -FileName "metrics_server_logs_before.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl top pods -A" -FileName "top_pods_before.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)

    $auditCursorBefore = Get-RemoteAuditCursor

    Invoke-SSH -RemoteCommand "bash $remoteScript" -TimeoutSeconds ($DurationSeconds + 180) -AllowExitCodes @(0, 1) |
        Set-Content -Path (Join-Path $OutputDir "stress_driver_output.txt")

    Save-RemoteOutput -RemoteCommand "cat /tmp/raasa-metrics-stress-summary.txt" -FileName "stress_summary.txt" -TimeoutSeconds 60 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sed -n '1,200p' /tmp/raasa-metrics-stress-failures.txt" -FileName "stress_failures_head.txt" -TimeoutSeconds 60 -AllowExitCodes @(0, 1)

    if ($CooldownSeconds -gt 0) {
        Start-Sleep -Seconds $CooldownSeconds
    }

    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-agent --tail=200" -FileName "agent_logs_after.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl logs -n kube-system deploy/metrics-server --tail=200" -FileName "metrics_server_logs_after.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl top pods -A" -FileName "top_pods_after.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods" -FileName "metrics_pods_after_raw.json" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)

    $auditCursorAfter = Get-RemoteAuditCursor
    $captureMode = "unavailable"
    $auditLines = @()

    if (-not [string]::IsNullOrWhiteSpace($auditCursorAfter.AgentPod) -and -not [string]::IsNullOrWhiteSpace($auditCursorAfter.LogFile)) {
        if (
            $auditCursorBefore.AgentPod -eq $auditCursorAfter.AgentPod -and
            $auditCursorBefore.LogFile -eq $auditCursorAfter.LogFile -and
            $auditCursorAfter.TotalLineCount -ge $auditCursorBefore.TotalLineCount
        ) {
            $captureMode = "delta_from_same_log"
            $auditLines = @(Get-RemoteAuditLines `
                -AgentPod $auditCursorAfter.AgentPod `
                -LogFile $auditCursorAfter.LogFile `
                -StartLine $auditCursorBefore.TotalLineCount `
                -TargetRefs $auditTargetRefs)
        }
        else {
            $captureMode = "full_current_log"
            $auditLines = @(Get-RemoteAuditLines `
                -AgentPod $auditCursorAfter.AgentPod `
                -LogFile $auditCursorAfter.LogFile `
                -StartLine 0 `
                -TargetRefs $auditTargetRefs)
        }
    }

    $auditRowsPath = Join-Path $OutputDir "audit_rows.jsonl"
    $auditMetaPath = Join-Path $OutputDir "audit_capture.json"
    $auditLines | Set-Content -Path $auditRowsPath
    [ordered]@{
        capture_mode = $captureMode
        captured_line_count = @($auditLines).Count
        target_refs = $auditTargetRefs
        state_before = $auditCursorBefore
        state_after = $auditCursorAfter
    } | ConvertTo-Json -Depth 6 | Set-Content -Path $auditMetaPath

    $auditSummary = Get-AuditRowsSummary -Path $auditRowsPath
    @(
        "Metrics API stress probe summary",
        "",
        "duration_seconds=$DurationSeconds",
        "worker_count=$WorkerCount",
        "cooldown_seconds=$CooldownSeconds",
        "audit.capture_mode=$captureMode",
        "audit.captured_line_count=$(@($auditLines).Count)",
        "audit.rows=$($auditSummary.rows)",
        "audit.reasons=$($auditSummary.reasons)",
        "audit.metrics_api_statuses=$($auditSummary.metrics_api_statuses)",
        "audit.memory_statuses=$($auditSummary.memory_statuses)",
        "audit.cpu_statuses=$($auditSummary.cpu_statuses)",
        "audit.telemetry_statuses=$($auditSummary.telemetry_statuses)",
        "audit.containers=$($auditSummary.containers)"
    ) | Set-Content -Path (Join-Path $OutputDir "summary.txt")

    Write-Host "Metrics API stress evidence collected in: $OutputDir"
}
finally {
    if (Test-Path -LiteralPath $localScript) {
        Remove-Item -LiteralPath $localScript -Force -ErrorAction SilentlyContinue
    }
    try {
        Invoke-SSH -RemoteCommand "rm -f $remoteScript /tmp/raasa-metrics-stress-summary.txt /tmp/raasa-metrics-stress-failures.txt" -TimeoutSeconds 60 -AllowExitCodes @(0) | Out-Null
    }
    catch {
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
