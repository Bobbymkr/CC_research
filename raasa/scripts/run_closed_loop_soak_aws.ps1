param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [int]$Cycles = 3,

    [int]$CooldownSeconds = 20,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$ClosedLoopScriptPath = "C:\Users\Admin\OneDrive\Desktop\CC\CC_research\raasa\scripts\closed_loop_test.sh",

    [string]$AuditPodRef = "default/raasa-test-benign-compute",

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\closed_loop_soak_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

if ($Cycles -lt 1) {
    throw "Cycles must be at least 1."
}
if ($CooldownSeconds -lt 0) {
    throw "CooldownSeconds must be >= 0."
}
if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH to an untracked PEM file."
}
if (-not (Test-Path -LiteralPath $ClosedLoopScriptPath)) {
    throw "Closed loop script not found: $ClosedLoopScriptPath"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath
$summaryPath = Join-Path $OutputDir "summary.md"

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
        "# Closed Loop Soak Summary",
        "",
        "- Host: $TargetHost",
        "- Cycles requested: $Cycles",
        "- Cooldown seconds: $CooldownSeconds",
        "- Collected at: $(Get-Date -Format o)",
        ""
    ) | Set-Content -Path $summaryPath

    Copy-Remote -LocalPath $ClosedLoopScriptPath -RemotePath "/tmp/closed_loop_test.sh"
    Invoke-SSH -RemoteCommand "sed -i 's/\r$//' /tmp/closed_loop_test.sh && chmod +x /tmp/closed_loop_test.sh" -TimeoutSeconds 60 | Out-Null

    $results = @()

    for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
        $cycleLabel = "cycle_{0:D2}" -f $cycle
        $cycleOutput = Join-Path $OutputDir "${cycleLabel}_closed_loop_output.txt"
        $auditRowsPath = Join-Path $OutputDir "${cycleLabel}_benign_audit_rows.jsonl"
        $auditMetaPath = Join-Path $OutputDir "${cycleLabel}_benign_audit_capture.json"
        $auditStateBefore = Get-RemoteAuditState -PodRef $AuditPodRef

        $output = Invoke-SSH -RemoteCommand "bash /tmp/closed_loop_test.sh" -TimeoutSeconds 360 -AllowExitCodes @(0, 1)
        $output | Set-Content -Path $cycleOutput

        $joined = ($output -join [Environment]::NewLine)
        $passed = $joined -match "4 passed, 0 failed"
        $results += [pscustomobject]@{
            cycle = $cycle
            passed = $passed
        }

        Invoke-SSH -RemoteCommand "sudo k3s kubectl get pods -A -o wide" -TimeoutSeconds 120 |
            Set-Content -Path (Join-Path $OutputDir "${cycleLabel}_pods_all_wide.txt")
        Invoke-SSH -RemoteCommand "sudo k3s kubectl top nodes" -TimeoutSeconds 120 -AllowExitCodes @(0, 1) |
            Set-Content -Path (Join-Path $OutputDir "${cycleLabel}_top_nodes.txt")
        Invoke-SSH -RemoteCommand "sudo k3s kubectl top pods -A" -TimeoutSeconds 120 -AllowExitCodes @(0, 1) |
            Set-Content -Path (Join-Path $OutputDir "${cycleLabel}_top_pods.txt")
        Invoke-SSH -RemoteCommand "sudo k3s kubectl logs -n raasa-system -l app=raasa-agent --all-containers=true --tail=200" -TimeoutSeconds 120 -AllowExitCodes @(0, 1) |
            Set-Content -Path (Join-Path $OutputDir "${cycleLabel}_raasa_tail.txt")
        Invoke-SSH -RemoteCommand "sudo k3s kubectl logs -n kube-system deploy/metrics-server --tail=120" -TimeoutSeconds 120 -AllowExitCodes @(0, 1) |
            Set-Content -Path (Join-Path $OutputDir "${cycleLabel}_metrics_server_tail.txt")

        $auditStateAfter = Get-RemoteAuditState -PodRef $AuditPodRef
        $allAuditLines = Get-RemoteAuditLines -AgentPod $auditStateAfter.AgentPod -LogFile $auditStateAfter.LogFile -PodRef $AuditPodRef

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

        $deltaAuditLines | Set-Content -Path $auditRowsPath
        [ordered]@{
            cycle = $cycle
            pod_ref = $AuditPodRef
            capture_mode = $captureMode
            captured_line_count = @($deltaAuditLines).Count
            state_before = $auditStateBefore
            state_after = $auditStateAfter
        } | ConvertTo-Json -Depth 6 | Set-Content -Path $auditMetaPath

        Add-Content -Path $summaryPath -Value "- Cycle $($cycle): $(if ($passed) { 'PASS' } else { 'FAIL' })"

        if ($cycle -lt $Cycles -and $CooldownSeconds -gt 0) {
            Start-Sleep -Seconds $CooldownSeconds
        }
    }

    $passCount = @($results | Where-Object { $_.passed }).Count
    Add-Content -Path $summaryPath -Value ""
    Add-Content -Path $summaryPath -Value "- Total passing cycles: $passCount / $Cycles"

    Save-RemoteOutput -RemoteCommand "date -u '+%Y-%m-%dT%H:%M:%SZ' && hostname && uname -a" -FileName "final_host_identity.txt" -TimeoutSeconds 60
    Save-RemoteOutput -RemoteCommand "sudo k3s kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods" -FileName "final_metrics_pods_raw.json" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)

    Write-Host "Closed-loop soak evidence collected in: $OutputDir"
}
finally {
    if (Test-Path -LiteralPath $tempKey) {
        try {
            Remove-Item -LiteralPath $tempKey -Force -ErrorAction Stop
        }
        catch {
            Write-Warning "Could not remove temporary key copy: $tempKey"
        }
    }
}
