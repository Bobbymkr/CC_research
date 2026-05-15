param(
    [string]$ClusterName = "",

    [string]$KubeconfigPath = $env:RAASA_EKS_KUBECONFIG,

    [string]$Context = $env:RAASA_EKS_CONTEXT,

    [int]$Cycles = 2,

    [int]$CooldownSeconds = 20,

    [int]$ReadyTimeoutSeconds = 240,

    [string]$AuditPodRef = "default/raasa-test-benign-compute",

    [string]$Phase0ManifestPath = (Join-Path (Get-Location) "raasa\k8s\phase0-test-pods.yaml"),

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\closed_loop_smoke_eks_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

function Get-AgentPod {
    return (Get-KubectlString -KubectlArgs @("get", "pods", "-n", "raasa-system", "-l", "app=raasa-agent", "-o", "jsonpath={.items[0].metadata.name}"))
}

function Get-Phase0Pod {
    param([Parameter(Mandatory = $true)][string]$Selector)
    return (Get-KubectlString -KubectlArgs @("get", "pods", "-n", "default", "-l", $Selector, "-o", "jsonpath={.items[0].metadata.name}"))
}

function Get-LatestAuditLog {
    param([Parameter(Mandatory = $true)][string]$AgentPod)

    return (Get-KubectlString -KubectlArgs @("exec", "-n", "raasa-system", $AgentPod, "-c", "raasa-agent", "--", "sh", "-c", "ls /app/raasa/logs/*.jsonl 2>/dev/null | tail -1") -AllowExitCodes @(0, 1))
}

function Get-Tier {
    param([Parameter(Mandatory = $true)][string]$PodName)

    $agentPod = Get-AgentPod
    if ([string]::IsNullOrWhiteSpace($agentPod)) {
        return "UNKNOWN"
    }

    $logFile = Get-LatestAuditLog -AgentPod $agentPod
    if ([string]::IsNullOrWhiteSpace($logFile)) {
        return "UNKNOWN"
    }

    $podRef = "default/$PodName"
    $line = Get-KubectlString -KubectlArgs @(
        "exec", "-n", "raasa-system", $agentPod, "-c", "raasa-agent", "--",
        "env", "TARGET_LOG=$logFile", "POD_REF=$podRef", "sh", "-c", 'grep -F "$POD_REF" "$TARGET_LOG" | tail -1'
    ) -AllowExitCodes @(0, 1)
    if ([string]::IsNullOrWhiteSpace($line)) {
        return "UNKNOWN"
    }

    try {
        $record = $line | ConvertFrom-Json
        return [string]$record.new_tier
    }
    catch {
        return "UNKNOWN"
    }
}

function Install-Stress {
    param([Parameter(Mandatory = $true)][string]$PodName)

    Invoke-KubectlCapture `
        -KubectlArgs @("exec", "-n", "default", $PodName, "--", "sh", "-c", "which stress-ng >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq stress-ng)") `
        -ErrorContext "Install stress-ng in $PodName" `
        -TimeoutSeconds 300 `
        -AllowExitCodes @(0, 1) | Out-Null
}

function Wait-ForTier {
    param(
        [Parameter(Mandatory = $true)][string]$PodName,
        [Parameter(Mandatory = $true)][string]$TargetTier,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    $elapsed = 0
    $current = "UNKNOWN"
    while ($elapsed -lt $TimeoutSeconds) {
        $current = Get-Tier -PodName $PodName
        if ($current -eq $TargetTier) {
            return [pscustomobject]@{ Matched = $true; Tier = $current }
        }
        Start-Sleep -Seconds 3
        $elapsed += 3
    }

    $current = Get-Tier -PodName $PodName
    return [pscustomobject]@{ Matched = ($current -eq $TargetTier); Tier = $current }
}

function Wait-ForL2WithoutL3 {
    param(
        [Parameter(Mandatory = $true)][string]$PodName,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    $elapsed = 0
    $observedL2 = $false
    $current = "UNKNOWN"

    while ($elapsed -lt $TimeoutSeconds) {
        $current = Get-Tier -PodName $PodName
        if ($current -eq "L3") {
            return [pscustomobject]@{ Matched = $false; Tier = $current; HitL3 = $true }
        }
        if ($current -eq "L2") {
            $observedL2 = $true
        }
        Start-Sleep -Seconds 3
        $elapsed += 3
    }

    $current = Get-Tier -PodName $PodName
    return [pscustomobject]@{
        Matched = ($current -eq "L2" -or $observedL2)
        Tier = $current
        HitL3 = ($current -eq "L3")
    }
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

function Add-CycleLine {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Text
    )

    $Lines.Add($Text) | Out-Null
}

if ($Cycles -lt 1) {
    throw "Cycles must be at least 1."
}
if ($CooldownSeconds -lt 0) {
    throw "CooldownSeconds must be >= 0."
}
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw "kubectl was not found on PATH."
}
if (-not [string]::IsNullOrWhiteSpace($KubeconfigPath) -and -not (Test-Path -LiteralPath $KubeconfigPath)) {
    throw "Kubeconfig path not found: $KubeconfigPath"
}
if (-not (Test-Path -LiteralPath $Phase0ManifestPath)) {
    throw "Phase0 manifest not found: $Phase0ManifestPath"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$currentContext = Get-KubectlString -KubectlArgs @("config", "current-context")
if ([string]::IsNullOrWhiteSpace($ClusterName)) {
    $ClusterName = $currentContext
}

@(
    "# Closed Loop EKS Smoke Summary",
    "",
    "- Cluster: $ClusterName",
    "- Context: $currentContext",
    "- Cycles requested: $Cycles",
    "- Cooldown seconds: $CooldownSeconds",
    "- Audit pod ref: $AuditPodRef",
    "- Collected at: $(Get-Date -Format o)",
    ""
) | Set-Content -Path (Join-Path $OutputDir "summary.md")

Save-KubectlOutput -KubectlArgs @("apply", "-f", $Phase0ManifestPath) -FileName "phase0_apply.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
Save-KubectlOutput -KubectlArgs @("wait", "--for=condition=Ready", "pod", "-l", "app=raasa-test", "-n", "default", "--timeout=${ReadyTimeoutSeconds}s") -FileName "phase0_wait_ready.txt" -TimeoutSeconds ($ReadyTimeoutSeconds + 60) -AllowExitCodes @(0, 1)

$results = @()
for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
    $cycleLabel = "cycle_{0:D2}" -f $cycle
    $cycleLines = New-Object 'System.Collections.Generic.List[string]'

    $agentPod = Get-AgentPod
    $benignPod = Get-Phase0Pod -Selector "app=raasa-test,raasa.class=benign,raasa.expected_tier=L2"
    $maliciousPod = Get-Phase0Pod -Selector "app=raasa-test,raasa.class=malicious,raasa.expected_tier=L3"
    if ([string]::IsNullOrWhiteSpace($agentPod) -or [string]::IsNullOrWhiteSpace($benignPod) -or [string]::IsNullOrWhiteSpace($maliciousPod)) {
        throw "Could not resolve the RAASA agent pod or one of the phase-0 test pods."
    }

    Install-Stress -PodName $benignPod
    Install-Stress -PodName $maliciousPod

    $auditStateBefore = Get-AuditState -PodRef $AuditPodRef

    Add-CycleLine -Lines $cycleLines -Text "Cluster: $ClusterName"
    Add-CycleLine -Lines $cycleLines -Text "Context: $currentContext"
    Add-CycleLine -Lines $cycleLines -Text "Cycle: $cycle"
    Add-CycleLine -Lines $cycleLines -Text "Agent pod: $agentPod"
    Add-CycleLine -Lines $cycleLines -Text "Benign pod: $benignPod"
    Add-CycleLine -Lines $cycleLines -Text "Malicious pod: $maliciousPod"
    Add-CycleLine -Lines $cycleLines -Text ""

    Start-Sleep -Seconds 10
    $passCount = 0
    $failCount = 0

    $t1Tier = Get-Tier -PodName $maliciousPod
    if ($t1Tier -eq "L3") {
        Add-CycleLine -Lines $cycleLines -Text "PASS T1 malicious pod held at L3"
        $passCount += 1
    }
    else {
        Add-CycleLine -Lines $cycleLines -Text "FAIL T1 malicious pod tier was $t1Tier, expected L3"
        $failCount += 1
    }

    $t2Baseline = Get-Tier -PodName $benignPod
    Invoke-KubectlCapture `
        -KubectlArgs @("exec", "-n", "default", $benignPod, "--", "sh", "-c", "nohup stress-ng --cpu 2 --cpu-load 95 --timeout 45s >/tmp/raasa-stress.log 2>&1 &") `
        -ErrorContext "Launch heavy stress in $benignPod" `
        -TimeoutSeconds 120 `
        -AllowExitCodes @(0, 1) | Out-Null
    $t2Result = Wait-ForL2WithoutL3 -PodName $benignPod -TimeoutSeconds 45
    if ($t2Result.Matched -and -not $t2Result.HitL3) {
        Add-CycleLine -Lines $cycleLines -Text "PASS T2 benign pod escalated from $t2Baseline to L2 without L3"
        $passCount += 1
    }
    else {
        Add-CycleLine -Lines $cycleLines -Text "FAIL T2 benign pod tier was $($t2Result.Tier), expected L2 without L3"
        $failCount += 1
    }

    $t3Result = Wait-ForTier -PodName $benignPod -TargetTier "L1" -TimeoutSeconds 120
    if ($t3Result.Matched) {
        Add-CycleLine -Lines $cycleLines -Text "PASS T3 benign pod de-escalated back to L1"
        $passCount += 1
    }
    else {
        Add-CycleLine -Lines $cycleLines -Text "FAIL T3 benign pod tier was $($t3Result.Tier), expected L1"
        $failCount += 1
    }

    Invoke-KubectlCapture `
        -KubectlArgs @("exec", "-n", "default", $benignPod, "--", "sh", "-c", "nohup stress-ng --cpu 1 --cpu-load 30 --timeout 20s >/tmp/raasa-stress-fp.log 2>&1 &") `
        -ErrorContext "Launch moderate stress in $benignPod" `
        -TimeoutSeconds 120 `
        -AllowExitCodes @(0, 1) | Out-Null
    Start-Sleep -Seconds 25
    $t4Tier = Get-Tier -PodName $benignPod
    if ($t4Tier -eq "L1" -or $t4Tier -eq "L2") {
        Add-CycleLine -Lines $cycleLines -Text "PASS T4 benign pod stayed at $t4Tier under moderate load"
        $passCount += 1
    }
    else {
        Add-CycleLine -Lines $cycleLines -Text "FAIL T4 benign pod tier was $t4Tier under moderate load"
        $failCount += 1
    }

    Add-CycleLine -Lines $cycleLines -Text ""
    Add-CycleLine -Lines $cycleLines -Text "$passCount passed, $failCount failed"
    $cycleLines | Set-Content -Path (Join-Path $OutputDir "${cycleLabel}_closed_loop_output.txt")

    Save-KubectlOutput -KubectlArgs @("get", "pods", "-A", "-o", "wide") -FileName "${cycleLabel}_pods_all_wide.txt" -TimeoutSeconds 120
    Save-KubectlOutput -KubectlArgs @("top", "nodes") -FileName "${cycleLabel}_top_nodes.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-KubectlOutput -KubectlArgs @("top", "pods", "-A") -FileName "${cycleLabel}_top_pods.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
    Save-KubectlOutput -KubectlArgs @("logs", "-n", "raasa-system", "-l", "app=raasa-agent", "--all-containers=true", "--tail=200") -FileName "${cycleLabel}_raasa_tail.txt" -TimeoutSeconds 180 -AllowExitCodes @(0, 1)
    Save-KubectlOutput -KubectlArgs @("logs", "-n", "kube-system", "deploy/metrics-server", "--tail=120") -FileName "${cycleLabel}_metrics_server_tail.txt" -TimeoutSeconds 180 -AllowExitCodes @(0, 1)

    $auditStateAfter = Get-AuditState -PodRef $AuditPodRef
    $allAuditLines = Get-AuditLines -AgentPod $auditStateAfter.AgentPod -LogFile $auditStateAfter.LogFile -PodRef $AuditPodRef
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

    $deltaAuditLines | Set-Content -Path (Join-Path $OutputDir "${cycleLabel}_benign_audit_rows.jsonl")
    [ordered]@{
        cycle = $cycle
        pod_ref = $AuditPodRef
        capture_mode = $captureMode
        captured_line_count = @($deltaAuditLines).Count
        state_before = $auditStateBefore
        state_after = $auditStateAfter
    } | ConvertTo-Json -Depth 6 | Set-Content -Path (Join-Path $OutputDir "${cycleLabel}_benign_audit_capture.json")

    $cyclePassed = ($failCount -eq 0)
    $results += [pscustomobject]@{
        cycle = $cycle
        passed = $cyclePassed
        pass_count = $passCount
        fail_count = $failCount
    }

    Add-Content -Path (Join-Path $OutputDir "summary.md") -Value "- Cycle ${cycle}: $(if ($cyclePassed) { 'PASS' } else { 'FAIL' }) ($passCount passed, $failCount failed)"
    if ($cycle -lt $Cycles -and $CooldownSeconds -gt 0) {
        Start-Sleep -Seconds $CooldownSeconds
    }
}

$passCycles = @($results | Where-Object { $_.passed }).Count
Add-Content -Path (Join-Path $OutputDir "summary.md") -Value ""
Add-Content -Path (Join-Path $OutputDir "summary.md") -Value "- Total passing cycles: $passCycles / $Cycles"

$results | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $OutputDir "results.json")
Save-KubectlOutput -KubectlArgs @("get", "--raw", "/apis/metrics.k8s.io/v1beta1/pods") -FileName "final_metrics_pods_raw.json" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)

if ($passCycles -ne $Cycles) {
    throw "Closed-loop EKS smoke had failing cycle(s): $passCycles / $Cycles passed. Evidence: $OutputDir"
}

Write-Host "Closed-loop EKS smoke evidence collected in: $OutputDir"
