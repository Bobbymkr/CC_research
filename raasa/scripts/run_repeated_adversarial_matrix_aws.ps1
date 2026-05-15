param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [int]$Runs = 5,

    [int]$DurationSeconds = 60,

    [int]$ReadyTimeoutSeconds = 120,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [switch]$QuiesceBackgroundWorkloads,

    [string]$MatrixScriptPath = (Join-Path (Get-Location) "raasa\scripts\run_adversarial_matrix_aws.ps1"),

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\adversarial_matrix_repeated_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Runs -lt 1) {
    throw "Runs must be at least 1."
}
if ($DurationSeconds -lt 30) {
    throw "DurationSeconds must be at least 30."
}
if (-not (Test-Path -LiteralPath $MatrixScriptPath)) {
    throw "Matrix script not found: $MatrixScriptPath"
}
if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH to an untracked PEM file."
}

function Convert-ToResultArray {
    param([object]$ParsedJson)

    if ($null -eq $ParsedJson) {
        return @()
    }
    if ($ParsedJson.PSObject.Properties.Name -contains "value") {
        return @($ParsedJson.value)
    }
    return @($ParsedJson)
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$summaryPath = Join-Path $OutputDir "summary.md"
$runRecords = @()
$workloadAggregate = @{}

@(
    "# Repeated Adversarial Matrix Summary",
    "",
    "- Host: $TargetHost",
    "- Runs requested: $Runs",
    "- Duration seconds per workload: $DurationSeconds",
    "- Background workloads quiesced per run: $QuiesceBackgroundWorkloads",
    "- Collected at: $(Get-Date -Format o)",
    ""
) | Set-Content -Path $summaryPath

for ($run = 1; $run -le $Runs; $run++) {
    $runLabel = "run_{0:D2}" -f $run
    $runDir = Join-Path $OutputDir $runLabel
    $consolePath = Join-Path $OutputDir "${runLabel}_console.txt"

    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $MatrixScriptPath,
        "-TargetHost", $TargetHost,
        "-DurationSeconds", [string]$DurationSeconds,
        "-ReadyTimeoutSeconds", [string]$ReadyTimeoutSeconds,
        "-User", $User,
        "-KeyPath", $KeyPath,
        "-OutputDir", $runDir
    )
    if ($QuiesceBackgroundWorkloads) {
        $arguments += "-QuiesceBackgroundWorkloads"
    }

    $consoleOutput = @(& powershell @arguments 2>&1)
    $exitCode = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }
    $consoleOutput | Set-Content -Path $consolePath

    $resultsPath = Join-Path $runDir "results.json"
    $matrixResults = @()
    if (Test-Path -LiteralPath $resultsPath) {
        $parsed = Get-Content -LiteralPath $resultsPath -Raw | ConvertFrom-Json
        $matrixResults = Convert-ToResultArray -ParsedJson $parsed
    }

    $workloadTotal = @($matrixResults).Count
    $workloadPassCount = @($matrixResults | Where-Object { [bool]$_.passed }).Count
    $runPassed = $exitCode -eq 0 -and $workloadTotal -gt 0 -and $workloadPassCount -eq $workloadTotal

    foreach ($result in $matrixResults) {
        $name = [string]$result.workload
        if (-not $workloadAggregate.ContainsKey($name)) {
            $workloadAggregate[$name] = [pscustomobject][ordered]@{
                workload = $name
                runs = 0
                passes = 0
                total_l3_count = 0
            }
        }
        $workloadAggregate[$name].runs = [int]$workloadAggregate[$name].runs + 1
        if ([bool]$result.passed) {
            $workloadAggregate[$name].passes = [int]$workloadAggregate[$name].passes + 1
        }
        if ($null -ne $result.l3_count) {
            $workloadAggregate[$name].total_l3_count = [int]$workloadAggregate[$name].total_l3_count + [int]$result.l3_count
        }
    }

    $runRecords += [pscustomobject][ordered]@{
        run = $run
        label = $runLabel
        passed = $runPassed
        exit_code = $exitCode
        workload_pass_count = $workloadPassCount
        workload_total = $workloadTotal
        evidence_dir = $runDir
    }

    Add-Content -Path $summaryPath -Value "## $runLabel"
    Add-Content -Path $summaryPath -Value "- Result: $(if ($runPassed) { 'PASS' } else { 'FAIL' })"
    Add-Content -Path $summaryPath -Value "- Exit code: $exitCode"
    Add-Content -Path $summaryPath -Value "- Workloads passing: $workloadPassCount / $workloadTotal"
    Add-Content -Path $summaryPath -Value "- Evidence: $runDir"
    Add-Content -Path $summaryPath -Value ""
}

$passedRuns = @($runRecords | Where-Object { [bool]$_.passed }).Count
$aggregateRows = @($workloadAggregate.Values | Sort-Object workload)

Add-Content -Path $summaryPath -Value "## Overall"
Add-Content -Path $summaryPath -Value "- Passing runs: $passedRuns / $Runs"
Add-Content -Path $summaryPath -Value ""

foreach ($row in $aggregateRows) {
    Add-Content -Path $summaryPath -Value "- $($row.workload): $($row.passes) / $($row.runs) runs passed, total L3 count $($row.total_l3_count)"
}

[ordered]@{
    runs_requested = $Runs
    passing_runs = $passedRuns
    duration_seconds = $DurationSeconds
    quiesce_background_workloads = [bool]$QuiesceBackgroundWorkloads
    run_records = $runRecords
    workload_aggregate = $aggregateRows
} | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $OutputDir "results.json")

if ($passedRuns -ne $Runs) {
    throw "Repeated adversarial matrix had failing run(s): $passedRuns / $Runs passed. Evidence: $OutputDir"
}

Write-Host "Repeated adversarial matrix evidence collected in: $OutputDir"
