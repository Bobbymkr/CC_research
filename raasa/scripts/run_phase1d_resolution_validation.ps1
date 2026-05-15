param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$BenchmarkManifestPath = "C:\Users\Admin\OneDrive\Desktop\CC\CC_research\raasa\k8s\phase1b-network-benchmark.yaml",

    [string]$DemoManifestPath = "C:\Users\Admin\OneDrive\Desktop\CC\CC_research\raasa\k8s\test-network-pods.yaml",

    [int]$OverrideSettleSeconds = 6,

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\phase1d_resolution_validation_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

function Write-ProgressMarker {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    (Get-Date).ToString("o") + " " + $Message | Set-Content -Path $Path
}

if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH to an untracked PEM file."
}
if (-not (Test-Path -LiteralPath $BenchmarkManifestPath)) {
    throw "Benchmark manifest not found: $BenchmarkManifestPath"
}
if (-not (Test-Path -LiteralPath $DemoManifestPath)) {
    throw "Demo manifest not found: $DemoManifestPath"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath
$progressPath = Join-Path $OutputDir "progress_marker.txt"
$agentPod = $null
$benchClientRef = $null
$benchServerRef = $null
$benchClientOriginalOverride = $null
$benchServerOriginalOverride = $null
$benchmarkOverrideWindowStarted = $false
$OverridePath = "/app/raasa/logs/overrides.json"
Write-ProgressMarker -Path $progressPath -Message "script started"

try {
    function Invoke-NativeCapture {
        param(
            [Parameter(Mandatory = $true)]
            [string]$FilePath,

            [Parameter(Mandatory = $true)]
            [string[]]$ArgumentList,

            [Parameter(Mandatory = $true)]
            [string]$ErrorContext,

            [int]$TimeoutSeconds = 180,

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

    function Invoke-SSH {
        param(
            [Parameter(Mandatory = $true)]
            [string]$RemoteCommand,

            [int]$TimeoutSeconds = 180,

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
            [string]$LocalPath,
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

            [hashtable]$Environment = @{},

            [string]$OutputName
        )

        $localScript = Join-Path $env:TEMP ("raasa-agent-python-" + [guid]::NewGuid().ToString() + ".py")
        $remoteScript = "/tmp/" + [System.IO.Path]::GetFileName($localScript)

        try {
            $PythonBody | Set-Content -Path $localScript
            Copy-Remote -LocalPath $localScript -RemotePath $remoteScript

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

            $remoteCommand = "sudo k3s kubectl exec -i -n raasa-system $AgentPod -c raasa-agent -- ${containerPrefix}python - < $remoteScript"
            $output = @(Invoke-SSH -RemoteCommand $remoteCommand)
            if ($OutputName) {
                $output | Set-Content -Path (Join-Path $OutputDir $OutputName)
            }
            return ($output -join [Environment]::NewLine).Trim()
        }
        finally {
            if (Test-Path -LiteralPath $localScript) {
                Remove-Item -LiteralPath $localScript -Force -ErrorAction SilentlyContinue
            }
            try {
                Invoke-SSH -RemoteCommand "rm -f $remoteScript" -TimeoutSeconds 30 -AllowExitCodes @(0) | Out-Null
            }
            catch {
            }
        }
    }

    function Invoke-Benchmark {
        param(
            [string]$ClientPod,
            [string]$Label,
            [string]$BenchmarkTarget
        )

        $outputPath = Join-Path $OutputDir "${Label}_measurements.txt"
        if (Test-Path -LiteralPath $outputPath) {
            Remove-Item -LiteralPath $outputPath -Force
        }

        for ($i = 1; $i -le 3; $i++) {
            $measurement = (Invoke-SSH `
                -RemoteCommand "sudo k3s kubectl exec -n raasa-bench $ClientPod -- curl -sS -o /dev/null -w '%{time_total} %{speed_download}' http://${BenchmarkTarget}/payload.bin" `
                -TimeoutSeconds 45 `
                -AllowExitCodes @(0, 6, 7, 28)).Trim()
            Add-Content -Path $outputPath -Value $measurement
        }
    }

    function Capture-BenchmarkDiagnostics {
        param(
            [string]$ClientPod,
            [string]$Label,
            [string]$ServiceHost
        )

        $diagnosticPath = Join-Path $OutputDir "${Label}_dns_diagnostics.txt"
        $remoteCommand = @"
sudo k3s kubectl exec -n raasa-bench $ClientPod -- sh -lc '
echo "service_host=$ServiceHost"
echo "--- resolv.conf ---"
cat /etc/resolv.conf
echo "--- getent ---"
if command -v getent >/dev/null 2>&1; then getent hosts $ServiceHost || true; else echo "getent unavailable"; fi
echo "--- nslookup ---"
if command -v nslookup >/dev/null 2>&1; then nslookup $ServiceHost || true; else echo "nslookup unavailable"; fi
'
"@
        Invoke-SSH $remoteCommand | Set-Content -Path $diagnosticPath
    }

    function Send-EnforcementCommand {
        param(
            [string]$AgentPod,
            [string]$ContainerRef,
            [string]$Tier,
            [string]$OutputName
        )

        $localScript = Join-Path $env:TEMP ("raasa-send-enforcement-" + [guid]::NewGuid().ToString() + ".py")
        @'
from raasa.core.ipc import UnixSocketClient
import os
import sys

payload = {
    "container_id": os.environ["CONTAINER_REF"],
    "tier": os.environ["TARGET_TIER"],
}
ok = UnixSocketClient().send_command(payload)
print("OK" if ok else "ERR")
raise SystemExit(0 if ok else 1)
'@ | Set-Content -Path $localScript

        try {
            Copy-Remote -LocalPath $localScript -RemotePath "/tmp/raasa-send-enforcement.py"
            Invoke-SSH "sudo k3s kubectl exec -i -n raasa-system $AgentPod -c raasa-agent -- env CONTAINER_REF='$ContainerRef' TARGET_TIER='$Tier' python - < /tmp/raasa-send-enforcement.py" |
                Set-Content -Path (Join-Path $OutputDir $OutputName)
        }
        finally {
            if (Test-Path -LiteralPath $localScript) {
                Remove-Item -LiteralPath $localScript -Force -ErrorAction SilentlyContinue
            }
        }
    }

    function Get-AgentOverrideTier {
        param(
            [Parameter(Mandatory = $true)]
            [string]$AgentPod,

            [Parameter(Mandatory = $true)]
            [string]$ContainerRef
        )

        $pythonBody = @"
from pathlib import Path
import os
from raasa.core.override import load_overrides

value = load_overrides(Path("$OverridePath")).get(os.environ["CONTAINER_REF"], "")
print(value)
"@
        $value = Invoke-AgentPython `
            -AgentPod $AgentPod `
            -PythonBody $pythonBody `
            -Environment @{ CONTAINER_REF = $ContainerRef }

        if ([string]::IsNullOrWhiteSpace($value)) {
            return $null
        }

        return $value.Trim()
    }

    function Capture-AgentOverrides {
        param(
            [Parameter(Mandatory = $true)]
            [string]$AgentPod,

            [Parameter(Mandatory = $true)]
            [string]$OutputName
        )

        $pythonBody = @"
from pathlib import Path
import json
from raasa.core.override import load_overrides

print(json.dumps(load_overrides(Path("$OverridePath")), indent=2, sort_keys=True))
"@
        Invoke-AgentPython `
            -AgentPod $AgentPod `
            -PythonBody $pythonBody `
            -OutputName $OutputName | Out-Null
    }

    function Set-AgentOverride {
        param(
            [Parameter(Mandatory = $true)]
            [string]$AgentPod,

            [Parameter(Mandatory = $true)]
            [string]$ContainerRef,

            [Parameter(Mandatory = $true)]
            [ValidateSet("L1", "L2", "L3")]
            [string]$Tier,

            [Parameter(Mandatory = $true)]
            [string]$OutputName
        )

        $pythonBody = @"
from pathlib import Path
import os
from raasa.core.override import set_override

set_override(
    os.environ["CONTAINER_REF"],
    os.environ["TARGET_TIER"],
    path=Path("$OverridePath"),
)
"@
        Invoke-AgentPython `
            -AgentPod $AgentPod `
            -PythonBody $pythonBody `
            -Environment @{
                CONTAINER_REF = $ContainerRef
                TARGET_TIER = $Tier
            } `
            -OutputName $OutputName | Out-Null
    }

    function Clear-AgentOverride {
        param(
            [Parameter(Mandatory = $true)]
            [string]$AgentPod,

            [Parameter(Mandatory = $true)]
            [string]$ContainerRef,

            [Parameter(Mandatory = $true)]
            [string]$OutputName
        )

        $pythonBody = @"
from pathlib import Path
import os
from raasa.core.override import clear_override

clear_override(
    os.environ["CONTAINER_REF"],
    path=Path("$OverridePath"),
)
"@
        Invoke-AgentPython `
            -AgentPod $AgentPod `
            -PythonBody $pythonBody `
            -Environment @{ CONTAINER_REF = $ContainerRef } `
            -OutputName $OutputName | Out-Null
    }

    function Restore-AgentOverride {
        param(
            [Parameter(Mandatory = $true)]
            [string]$AgentPod,

            [Parameter(Mandatory = $true)]
            [string]$ContainerRef,

            [AllowNull()]
            [string]$OriginalTier,

            [Parameter(Mandatory = $true)]
            [string]$OutputName
        )

        if ([string]::IsNullOrWhiteSpace($OriginalTier)) {
            Clear-AgentOverride -AgentPod $AgentPod -ContainerRef $ContainerRef -OutputName $OutputName
            return
        }

        Set-AgentOverride -AgentPod $AgentPod -ContainerRef $ContainerRef -Tier $OriginalTier -OutputName $OutputName
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
            TimestampUtc = if ($stateMap.ContainsKey("timestamp")) { [string]$stateMap["timestamp"] } else { "" }
            AgentPod = if ($stateMap.ContainsKey("agent")) { [string]$stateMap["agent"] } else { "" }
            LogFile = if ($stateMap.ContainsKey("log")) { [string]$stateMap["log"] } else { "" }
            TotalLineCount = $countValue
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

    function Capture-AgentAuditWindow {
        param(
            [Parameter(Mandatory = $true)]
            [pscustomobject]$StartCursor,

            [Parameter(Mandatory = $true)]
            [string]$OutputPrefix,

            [Parameter(Mandatory = $true)]
            [string[]]$TargetRefs
        )

        $endCursor = Get-RemoteAuditCursor
        $captureMode = "unavailable"
        $auditLines = @()

        if (-not [string]::IsNullOrWhiteSpace($endCursor.AgentPod) -and -not [string]::IsNullOrWhiteSpace($endCursor.LogFile)) {
            if (
                $StartCursor.AgentPod -eq $endCursor.AgentPod -and
                $StartCursor.LogFile -eq $endCursor.LogFile -and
                $endCursor.TotalLineCount -ge $StartCursor.TotalLineCount
            ) {
                $captureMode = "delta_from_same_log"
                $auditLines = @(Get-RemoteAuditLines `
                    -AgentPod $endCursor.AgentPod `
                    -LogFile $endCursor.LogFile `
                    -StartLine $StartCursor.TotalLineCount `
                    -TargetRefs $TargetRefs)
            }
            else {
                $captureMode = "full_current_log"
                $auditLines = @(Get-RemoteAuditLines `
                    -AgentPod $endCursor.AgentPod `
                    -LogFile $endCursor.LogFile `
                    -StartLine 0 `
                    -TargetRefs $TargetRefs)
            }
        }

        $rowsPath = Join-Path $OutputDir "${OutputPrefix}_audit_rows.jsonl"
        $metaPath = Join-Path $OutputDir "${OutputPrefix}_audit_capture.json"
        $auditLines | Set-Content -Path $rowsPath
        [ordered]@{
            output_prefix = $OutputPrefix
            capture_mode = $captureMode
            captured_line_count = @($auditLines).Count
            target_refs = $TargetRefs
            state_before = $StartCursor
            state_after = $endCursor
        } | ConvertTo-Json -Depth 6 | Set-Content -Path $metaPath

        return $endCursor
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
            [string]$Path,

            [Parameter(Mandatory = $true)]
            [string]$BenchClientRef,

            [Parameter(Mandatory = $true)]
            [string]$BenchServerRef
        )

        $rows = 0
        $operatorOverrideRows = 0
        $benchClientRows = 0
        $benchServerRows = 0
        $reasons = @{}
        $newTiers = @{}
        $metricsApiStatuses = @{}
        $telemetryStatuses = @{}
        $firstTimestamp = $null
        $lastTimestamp = $null

        if (-not (Test-Path -LiteralPath $Path)) {
            return @{
                rows = 0
                operator_override_rows = 0
                bench_client_rows = 0
                bench_server_rows = 0
                reasons = "none"
                new_tiers = "none"
                metrics_api_statuses = "none"
                telemetry_statuses = "none"
                first_timestamp = $null
                last_timestamp = $null
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
            if ($null -eq $firstTimestamp -and $record.timestamp) {
                $firstTimestamp = [string]$record.timestamp
            }
            if ($record.timestamp) {
                $lastTimestamp = [string]$record.timestamp
            }

            $containerId = [string]$record.container_id
            if ($containerId -eq $BenchClientRef) {
                $benchClientRows += 1
            }
            if ($containerId -eq $BenchServerRef) {
                $benchServerRows += 1
            }

            $reason = [string]$record.reason
            if (-not [string]::IsNullOrWhiteSpace($reason)) {
                if (-not $reasons.ContainsKey($reason)) {
                    $reasons[$reason] = 0
                }
                $reasons[$reason] += 1
                if ($reason -eq "operator override") {
                    $operatorOverrideRows += 1
                }
            }

            $newTier = [string]$record.new_tier
            if (-not [string]::IsNullOrWhiteSpace($newTier)) {
                if (-not $newTiers.ContainsKey($newTier)) {
                    $newTiers[$newTier] = 0
                }
                $newTiers[$newTier] += 1
            }

            $metricsApiStatus = [string]$record.metadata.metrics_api_status
            if (-not [string]::IsNullOrWhiteSpace($metricsApiStatus)) {
                if (-not $metricsApiStatuses.ContainsKey($metricsApiStatus)) {
                    $metricsApiStatuses[$metricsApiStatus] = 0
                }
                $metricsApiStatuses[$metricsApiStatus] += 1
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
            operator_override_rows = $operatorOverrideRows
            bench_client_rows = $benchClientRows
            bench_server_rows = $benchServerRows
            reasons = (Format-MapSummary -Map $reasons)
            new_tiers = (Format-MapSummary -Map $newTiers)
            metrics_api_statuses = (Format-MapSummary -Map $metricsApiStatuses)
            telemetry_statuses = (Format-MapSummary -Map $telemetryStatuses)
            first_timestamp = $firstTimestamp
            last_timestamp = $lastTimestamp
        }
    }

    function Get-MetricSummary {
        param([string]$Path)

        $rows = @()
        foreach ($line in Get-Content -LiteralPath $Path) {
            $parts = $line.Trim() -split "\s+"
            if ($parts.Length -ne 2) {
                continue
            }
            $rows += [pscustomobject]@{
                time_total_sec = [double]$parts[0]
                speed_bytes_per_sec = [double]$parts[1]
            }
        }

        if ($rows.Count -eq 0) {
            return @{
                samples = 0
                avg_time_total_sec = $null
                avg_speed_bytes_per_sec = $null
            }
        }

        return @{
            samples = $rows.Count
            avg_time_total_sec = ($rows | Measure-Object -Property time_total_sec -Average).Average
            avg_speed_bytes_per_sec = ($rows | Measure-Object -Property speed_bytes_per_sec -Average).Average
        }
    }

    function Select-ResolutionSummary {
        param(
            [string[]]$LogLines,
            [string]$ContainerRef
        )

        $resolvedLine = $LogLines | Where-Object { $_ -like "*Resolved pod $ContainerRef to host interface*" } | Select-Object -Last 1
        $fallbackLine = $LogLines | Where-Object { $_ -like "*Falling back to interface*for $ContainerRef.*" } | Select-Object -Last 1

        return @{
            container_ref = $ContainerRef
            resolved = [bool]$resolvedLine
            resolved_line = if ($resolvedLine) { $resolvedLine } else { $null }
            fallback = [bool]$fallbackLine
            fallback_line = if ($fallbackLine) { $fallbackLine } else { $null }
        }
    }

    function Format-Decimal {
        param([object]$Value)

        if ($null -eq $Value) {
            return "n/a"
        }

        return ([double]$Value).ToString("0.######", [System.Globalization.CultureInfo]::InvariantCulture)
    }

    Copy-Remote -LocalPath $BenchmarkManifestPath -RemotePath "/tmp/phase1d-network-benchmark.yaml"
    Copy-Remote -LocalPath $DemoManifestPath -RemotePath "/tmp/phase1d-test-network-pods.yaml"

    Invoke-SSH "sudo k3s kubectl apply -f /tmp/phase1d-network-benchmark.yaml" |
        Set-Content -Path (Join-Path $OutputDir "kubectl_apply_benchmark.txt")
    Invoke-SSH "sudo k3s kubectl apply -f /tmp/phase1d-test-network-pods.yaml" |
        Set-Content -Path (Join-Path $OutputDir "kubectl_apply_demo.txt")

    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-bench-server -n raasa-bench --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_bench_server.txt")
    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-bench-client -n raasa-bench --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_bench_client.txt")
    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-net-server -n raasa-demo --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_demo_server.txt")
    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-net-client -n raasa-demo --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_demo_client.txt")

    $agentPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o jsonpath='{.items[0].metadata.name}'").Trim()
    $benchClientPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-bench -l app=raasa-bench-client -o jsonpath='{.items[0].metadata.name}'").Trim()
    $benchServerPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-bench -l app=raasa-bench-server -o jsonpath='{.items[0].metadata.name}'").Trim()
    $benchServerPodIp = (Invoke-SSH "sudo k3s kubectl get pod -n raasa-bench $benchServerPod -o jsonpath='{.status.podIP}'").Trim()
    $benchServiceIp = (Invoke-SSH "sudo k3s kubectl get svc -n raasa-bench raasa-bench-server -o jsonpath='{.spec.clusterIP}'").Trim()
    $benchServiceHost = "raasa-bench-server.raasa-bench.svc.cluster.local"
    $demoClientPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-demo -l app=raasa-net-client -o jsonpath='{.items[0].metadata.name}'").Trim()
    $demoServerPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-demo -l app=raasa-net-server -o jsonpath='{.items[0].metadata.name}'").Trim()
    if (-not $agentPod) {
        throw "Could not find RAASA agent pod."
    }
    if (-not $benchClientPod) {
        throw "Could not find benchmark client pod."
    }
    if (-not $benchServerPod) {
        throw "Could not find benchmark server pod."
    }
    if (-not $benchServerPodIp) {
        throw "Could not find benchmark server pod IP."
    }
    if (-not $benchServiceIp) {
        throw "Could not find benchmark service ClusterIP."
    }
    if (-not $demoClientPod) {
        throw "Could not find demo client pod."
    }
    if (-not $demoServerPod) {
        throw "Could not find demo server pod."
    }

    $benchClientRef = "raasa-bench/$benchClientPod"
    $benchServerRef = "raasa-bench/$benchServerPod"
    $demoClientRef = "raasa-demo/$demoClientPod"
    $demoServerRef = "raasa-demo/$demoServerPod"
    $benchClientOriginalOverride = Get-AgentOverrideTier -AgentPod $agentPod -ContainerRef $benchClientRef
    $benchServerOriginalOverride = Get-AgentOverrideTier -AgentPod $agentPod -ContainerRef $benchServerRef
    Capture-AgentOverrides -AgentPod $agentPod -OutputName "overrides_before_measurements.json"

    $collectedAtLocal = (Get-Date).ToString("o")
    @(
        "Host=$TargetHost",
        "User=$User",
        "CollectedAtLocal=$collectedAtLocal",
        "AgentPod=$agentPod",
        "BenchClientRef=$benchClientRef",
        "BenchServerRef=$benchServerRef",
        "BenchServerPod=$benchServerPod",
        "BenchServerPodIp=$benchServerPodIp",
        "BenchServiceHost=$benchServiceHost",
        "BenchServiceIp=$benchServiceIp",
        "DemoClientRef=$demoClientRef",
        "DemoServerRef=$demoServerRef",
        "OverrideSettleSeconds=$OverrideSettleSeconds",
        "BenchClientOriginalOverride=$(if ($benchClientOriginalOverride) { $benchClientOriginalOverride } else { 'none' })",
        "BenchServerOriginalOverride=$(if ($benchServerOriginalOverride) { $benchServerOriginalOverride } else { 'none' })"
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Invoke-SSH "sudo k3s kubectl get pods -A -o wide" |
        Set-Content -Path (Join-Path $OutputDir "pods_all_wide.txt")

    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $demoServerRef -Tier "L2" -OutputName "send_demo_server_l2.txt"
    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $demoClientRef -Tier "L2" -OutputName "send_demo_client_l2.txt"
    Start-Sleep -Seconds 3
    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=180" |
        Set-Content -Path (Join-Path $OutputDir "enforcer_logs_after_demo_l2.txt")
    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-agent --tail=180" -AllowExitCodes @(0, 1) |
        Set-Content -Path (Join-Path $OutputDir "agent_logs_after_demo_l2.txt")

    # Pin the benchmark pods with explicit overrides so the controller cannot
    # rewrite their tiers while the L1/L3 measurement window is open.
    $benchmarkAuditTargetRefs = @($benchClientRef, $benchServerRef)
    $auditCursorBeforeL1 = Get-RemoteAuditCursor
    $auditCursorBeforeL3 = $null
    $auditCursorBeforeRestore = $null
    $benchmarkOverrideWindowStarted = $true
    try {
        Set-AgentOverride -AgentPod $agentPod -ContainerRef $benchServerRef -Tier "L1" -OutputName "set_bench_server_override_l1.txt"
        Set-AgentOverride -AgentPod $agentPod -ContainerRef $benchClientRef -Tier "L1" -OutputName "set_bench_client_override_l1.txt"
        Capture-AgentOverrides -AgentPod $agentPod -OutputName "overrides_l1_window.json"
        Start-Sleep -Seconds $OverrideSettleSeconds
        Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=220" |
            Set-Content -Path (Join-Path $OutputDir "enforcer_logs_after_bench_l1.txt")
        Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-agent --tail=220" -AllowExitCodes @(0, 1) |
            Set-Content -Path (Join-Path $OutputDir "agent_logs_after_bench_l1.txt")
        Capture-BenchmarkDiagnostics -ClientPod $benchClientPod -Label "l1" -ServiceHost $benchServiceHost
        Invoke-Benchmark -ClientPod $benchClientPod -Label "l1_service" -BenchmarkTarget $benchServiceHost
        Invoke-Benchmark -ClientPod $benchClientPod -Label "l1_service_ip" -BenchmarkTarget $benchServiceIp
        Invoke-Benchmark -ClientPod $benchClientPod -Label "l1_pod_ip" -BenchmarkTarget $benchServerPodIp
        $auditCursorBeforeL3 = Capture-AgentAuditWindow -StartCursor $auditCursorBeforeL1 -OutputPrefix "l1" -TargetRefs $benchmarkAuditTargetRefs

        Set-AgentOverride -AgentPod $agentPod -ContainerRef $benchClientRef -Tier "L3" -OutputName "set_bench_client_override_l3.txt"
        Capture-AgentOverrides -AgentPod $agentPod -OutputName "overrides_l3_window.json"
        Start-Sleep -Seconds $OverrideSettleSeconds
        Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=260" |
            Set-Content -Path (Join-Path $OutputDir "enforcer_logs_after_bench_l3.txt")
        Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-agent --tail=260" -AllowExitCodes @(0, 1) |
            Set-Content -Path (Join-Path $OutputDir "agent_logs_after_bench_l3.txt")
        Capture-BenchmarkDiagnostics -ClientPod $benchClientPod -Label "l3" -ServiceHost $benchServiceHost
        Invoke-Benchmark -ClientPod $benchClientPod -Label "l3_service" -BenchmarkTarget $benchServiceHost
        Invoke-Benchmark -ClientPod $benchClientPod -Label "l3_service_ip" -BenchmarkTarget $benchServiceIp
        Invoke-Benchmark -ClientPod $benchClientPod -Label "l3_pod_ip" -BenchmarkTarget $benchServerPodIp
        $auditCursorBeforeRestore = Capture-AgentAuditWindow -StartCursor $auditCursorBeforeL3 -OutputPrefix "l3" -TargetRefs $benchmarkAuditTargetRefs
    }
    finally {
        if ($benchmarkOverrideWindowStarted) {
            Restore-AgentOverride -AgentPod $agentPod -ContainerRef $benchClientRef -OriginalTier $benchClientOriginalOverride -OutputName "restore_bench_client_override.txt"
            Restore-AgentOverride -AgentPod $agentPod -ContainerRef $benchServerRef -OriginalTier $benchServerOriginalOverride -OutputName "restore_bench_server_override.txt"
            Capture-AgentOverrides -AgentPod $agentPod -OutputName "overrides_after_benchmark_restore.json"

            if (-not $benchClientOriginalOverride) {
                Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $benchClientRef -Tier "L1" -OutputName "send_bench_restore_l1.txt"
            }
        }
    }

    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $demoServerRef -Tier "L1" -OutputName "send_demo_server_l1.txt"
    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $demoClientRef -Tier "L1" -OutputName "send_demo_client_l1.txt"
    Start-Sleep -Seconds 2
    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=260" |
        Set-Content -Path (Join-Path $OutputDir "enforcer_logs_final.txt")
    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-agent --tail=260" -AllowExitCodes @(0, 1) |
        Set-Content -Path (Join-Path $OutputDir "agent_logs_final.txt")
    if ($auditCursorBeforeRestore) {
        $null = Capture-AgentAuditWindow -StartCursor $auditCursorBeforeRestore -OutputPrefix "restore" -TargetRefs $benchmarkAuditTargetRefs
    }

    Write-ProgressMarker -Path $progressPath -Message "starting summary build"
    $logLines = Get-Content -LiteralPath (Join-Path $OutputDir "enforcer_logs_final.txt")
    Write-ProgressMarker -Path $progressPath -Message "loaded final log lines"
    $l1Service = Get-MetricSummary -Path (Join-Path $OutputDir "l1_service_measurements.txt")
    $l1ServiceIp = Get-MetricSummary -Path (Join-Path $OutputDir "l1_service_ip_measurements.txt")
    $l1PodIp = Get-MetricSummary -Path (Join-Path $OutputDir "l1_pod_ip_measurements.txt")
    $l3Service = Get-MetricSummary -Path (Join-Path $OutputDir "l3_service_measurements.txt")
    $l3ServiceIp = Get-MetricSummary -Path (Join-Path $OutputDir "l3_service_ip_measurements.txt")
    $l3PodIp = Get-MetricSummary -Path (Join-Path $OutputDir "l3_pod_ip_measurements.txt")
    $fallbackLines = @($logLines | Where-Object { $_ -like "*Falling back to interface*" })
    $l1AuditCapture = Get-Content -LiteralPath (Join-Path $OutputDir "l1_audit_capture.json") | ConvertFrom-Json
    $l3AuditCapture = Get-Content -LiteralPath (Join-Path $OutputDir "l3_audit_capture.json") | ConvertFrom-Json
    $restoreAuditCapture = Get-Content -LiteralPath (Join-Path $OutputDir "restore_audit_capture.json") | ConvertFrom-Json
    $l1AuditSummary = Get-AuditRowsSummary -Path (Join-Path $OutputDir "l1_audit_rows.jsonl") -BenchClientRef $benchClientRef -BenchServerRef $benchServerRef
    $l3AuditSummary = Get-AuditRowsSummary -Path (Join-Path $OutputDir "l3_audit_rows.jsonl") -BenchClientRef $benchClientRef -BenchServerRef $benchServerRef
    $restoreAuditSummary = Get-AuditRowsSummary -Path (Join-Path $OutputDir "restore_audit_rows.jsonl") -BenchClientRef $benchClientRef -BenchServerRef $benchServerRef
    Write-ProgressMarker -Path $progressPath -Message "parsed benchmark summaries"

    $demoServerSummary = Select-ResolutionSummary -LogLines $logLines -ContainerRef $demoServerRef
    $demoClientSummary = Select-ResolutionSummary -LogLines $logLines -ContainerRef $demoClientRef
    $benchClientSummary = Select-ResolutionSummary -LogLines $logLines -ContainerRef $benchClientRef

    $summaryLines = @(
        "Phase 1D resolution validation summary",
        "",
        "demo_server.container_ref=$($demoServerSummary.container_ref)",
        "demo_server.resolved=$($demoServerSummary.resolved)",
        "demo_server.fallback=$($demoServerSummary.fallback)",
        "demo_server.resolved_line=$($demoServerSummary.resolved_line)",
        "demo_server.fallback_line=$($demoServerSummary.fallback_line)",
        "",
        "demo_client.container_ref=$($demoClientSummary.container_ref)",
        "demo_client.resolved=$($demoClientSummary.resolved)",
        "demo_client.fallback=$($demoClientSummary.fallback)",
        "demo_client.resolved_line=$($demoClientSummary.resolved_line)",
        "demo_client.fallback_line=$($demoClientSummary.fallback_line)",
        "",
        "bench_client.container_ref=$($benchClientSummary.container_ref)",
        "bench_client.resolved=$($benchClientSummary.resolved)",
        "bench_client.fallback=$($benchClientSummary.fallback)",
        "bench_client.resolved_line=$($benchClientSummary.resolved_line)",
        "bench_client.fallback_line=$($benchClientSummary.fallback_line)",
        "",
        "fallback_count=$($fallbackLines.Count)",
        "latest_fallback_line=$(if ($fallbackLines.Count -gt 0) { $fallbackLines[-1] } else { '' })",
        "",
        "benchmark_targets.service_host=$benchServiceHost",
        "benchmark_targets.service_ip=$benchServiceIp",
        "benchmark_targets.pod_ip=$benchServerPodIp",
        "benchmark_targets.override_settle_seconds=$OverrideSettleSeconds",
        "benchmark_targets.bench_client_original_override=$(if ($benchClientOriginalOverride) { $benchClientOriginalOverride } else { 'none' })",
        "benchmark_targets.bench_server_original_override=$(if ($benchServerOriginalOverride) { $benchServerOriginalOverride } else { 'none' })",
        "",
        "audit.l1.capture_mode=$($l1AuditCapture.capture_mode)",
        "audit.l1.captured_line_count=$($l1AuditCapture.captured_line_count)",
        "audit.l1.rows=$($l1AuditSummary.rows)",
        "audit.l1.operator_override_rows=$($l1AuditSummary.operator_override_rows)",
        "audit.l1.bench_client_rows=$($l1AuditSummary.bench_client_rows)",
        "audit.l1.bench_server_rows=$($l1AuditSummary.bench_server_rows)",
        "audit.l1.reasons=$($l1AuditSummary.reasons)",
        "audit.l1.new_tiers=$($l1AuditSummary.new_tiers)",
        "audit.l1.metrics_api_statuses=$($l1AuditSummary.metrics_api_statuses)",
        "audit.l1.telemetry_statuses=$($l1AuditSummary.telemetry_statuses)",
        "audit.l1.first_timestamp=$(if ($l1AuditSummary.first_timestamp) { $l1AuditSummary.first_timestamp } else { '' })",
        "audit.l1.last_timestamp=$(if ($l1AuditSummary.last_timestamp) { $l1AuditSummary.last_timestamp } else { '' })",
        "",
        "audit.l3.capture_mode=$($l3AuditCapture.capture_mode)",
        "audit.l3.captured_line_count=$($l3AuditCapture.captured_line_count)",
        "audit.l3.rows=$($l3AuditSummary.rows)",
        "audit.l3.operator_override_rows=$($l3AuditSummary.operator_override_rows)",
        "audit.l3.bench_client_rows=$($l3AuditSummary.bench_client_rows)",
        "audit.l3.bench_server_rows=$($l3AuditSummary.bench_server_rows)",
        "audit.l3.reasons=$($l3AuditSummary.reasons)",
        "audit.l3.new_tiers=$($l3AuditSummary.new_tiers)",
        "audit.l3.metrics_api_statuses=$($l3AuditSummary.metrics_api_statuses)",
        "audit.l3.telemetry_statuses=$($l3AuditSummary.telemetry_statuses)",
        "audit.l3.first_timestamp=$(if ($l3AuditSummary.first_timestamp) { $l3AuditSummary.first_timestamp } else { '' })",
        "audit.l3.last_timestamp=$(if ($l3AuditSummary.last_timestamp) { $l3AuditSummary.last_timestamp } else { '' })",
        "",
        "audit.restore.capture_mode=$($restoreAuditCapture.capture_mode)",
        "audit.restore.captured_line_count=$($restoreAuditCapture.captured_line_count)",
        "audit.restore.rows=$($restoreAuditSummary.rows)",
        "audit.restore.operator_override_rows=$($restoreAuditSummary.operator_override_rows)",
        "audit.restore.bench_client_rows=$($restoreAuditSummary.bench_client_rows)",
        "audit.restore.bench_server_rows=$($restoreAuditSummary.bench_server_rows)",
        "audit.restore.reasons=$($restoreAuditSummary.reasons)",
        "audit.restore.new_tiers=$($restoreAuditSummary.new_tiers)",
        "audit.restore.metrics_api_statuses=$($restoreAuditSummary.metrics_api_statuses)",
        "audit.restore.telemetry_statuses=$($restoreAuditSummary.telemetry_statuses)",
        "audit.restore.first_timestamp=$(if ($restoreAuditSummary.first_timestamp) { $restoreAuditSummary.first_timestamp } else { '' })",
        "audit.restore.last_timestamp=$(if ($restoreAuditSummary.last_timestamp) { $restoreAuditSummary.last_timestamp } else { '' })",
        "",
        "l1.service.samples=$($l1Service.samples)",
        "l1.service.avg_time_total_sec=$(Format-Decimal $l1Service.avg_time_total_sec)",
        "l1.service.avg_speed_bytes_per_sec=$(Format-Decimal $l1Service.avg_speed_bytes_per_sec)",
        "l1.service_ip.samples=$($l1ServiceIp.samples)",
        "l1.service_ip.avg_time_total_sec=$(Format-Decimal $l1ServiceIp.avg_time_total_sec)",
        "l1.service_ip.avg_speed_bytes_per_sec=$(Format-Decimal $l1ServiceIp.avg_speed_bytes_per_sec)",
        "l1.pod_ip.samples=$($l1PodIp.samples)",
        "l1.pod_ip.avg_time_total_sec=$(Format-Decimal $l1PodIp.avg_time_total_sec)",
        "l1.pod_ip.avg_speed_bytes_per_sec=$(Format-Decimal $l1PodIp.avg_speed_bytes_per_sec)",
        "",
        "l3.service.samples=$($l3Service.samples)",
        "l3.service.avg_time_total_sec=$(Format-Decimal $l3Service.avg_time_total_sec)",
        "l3.service.avg_speed_bytes_per_sec=$(Format-Decimal $l3Service.avg_speed_bytes_per_sec)",
        "l3.service_ip.samples=$($l3ServiceIp.samples)",
        "l3.service_ip.avg_time_total_sec=$(Format-Decimal $l3ServiceIp.avg_time_total_sec)",
        "l3.service_ip.avg_speed_bytes_per_sec=$(Format-Decimal $l3ServiceIp.avg_speed_bytes_per_sec)",
        "l3.pod_ip.samples=$($l3PodIp.samples)",
        "l3.pod_ip.avg_time_total_sec=$(Format-Decimal $l3PodIp.avg_time_total_sec)",
        "l3.pod_ip.avg_speed_bytes_per_sec=$(Format-Decimal $l3PodIp.avg_speed_bytes_per_sec)"
    )

    if ($l1Service.samples -gt 0 -and $l3Service.samples -gt 0) {
        $summaryLines += @(
            "",
            "comparison.service.speed_ratio_l3_vs_l1=$(Format-Decimal ($l3Service.avg_speed_bytes_per_sec / $l1Service.avg_speed_bytes_per_sec))",
            "comparison.service.time_ratio_l3_vs_l1=$(Format-Decimal ($l3Service.avg_time_total_sec / $l1Service.avg_time_total_sec))"
        )
    }
    Write-ProgressMarker -Path $progressPath -Message "assembled summary object"
    $summaryLines | Set-Content -Path (Join-Path $OutputDir "summary.txt")
    Write-ProgressMarker -Path $progressPath -Message "wrote summary.txt"

    Write-Host "Phase 1D resolution validation evidence collected in: $OutputDir"
}
finally {
    Write-ProgressMarker -Path $progressPath -Message "entering finally"
    if (Test-Path -LiteralPath $tempKey) {
        try {
            Remove-Item -LiteralPath $tempKey -Force -ErrorAction Stop
        }
        catch {
            Write-Warning "Could not remove temporary key copy: $tempKey"
        }
    }
    Write-ProgressMarker -Path $progressPath -Message "finished finally"
}
