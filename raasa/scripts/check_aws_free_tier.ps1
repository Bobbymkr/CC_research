param(
    [string]$Profile = "",
    [string]$Region = "us-east-1",
    [switch]$IncludeInventory,
    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\\aws_account_check_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-AwsBaseArgs {
    $args = @()
    if ($Profile) {
        $args += @("--profile", $Profile)
    }
    if ($Region) {
        $args += @("--region", $Region)
    }
    $args += "--no-cli-pager"
    return $args
}

function Invoke-AwsJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$CommandArgs,

        [Parameter(Mandatory = $true)]
        [string]$OutputPath,

        [switch]$AllowFailure
    )

    $fullArgs = @() + (Get-AwsBaseArgs) + $CommandArgs + @("--output", "json")
    $raw = & aws @fullArgs 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        $raw | Out-File -FilePath ($OutputPath + ".error.txt") -Encoding utf8
        if ($AllowFailure) {
            return $null
        }
        throw "AWS CLI command failed: aws $($CommandArgs -join ' ')"
    }

    $raw | Out-File -FilePath $OutputPath -Encoding utf8
    if (-not $raw) {
        return $null
    }
    return ($raw | ConvertFrom-Json)
}

function Get-ValueOrDefault {
    param(
        $Value,
        [string]$Default = "n/a"
    )

    if ($null -eq $Value -or $Value -eq "") {
        return $Default
    }
    return [string]$Value
}

function Convert-ToPercent {
    param(
        [double]$Numerator,
        [double]$Denominator
    )

    if ($Denominator -le 0) {
        return $null
    }
    return [math]::Round(($Numerator / $Denominator) * 100.0, 2)
}

function Add-MarkdownLine {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Text = ""
    )

    $Lines.Add($Text) | Out-Null
}

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "AWS CLI was not found on PATH. Install/configure AWS CLI first."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$summaryLines = New-Object 'System.Collections.Generic.List[string]'
$collectedAt = (Get-Date).ToString("o")
$awsVersion = (& aws --version) 2>&1
$awsVersion | Out-File -FilePath (Join-Path $OutputDir "aws_version.txt") -Encoding utf8

$identity = Invoke-AwsJson -CommandArgs @("sts", "get-caller-identity") -OutputPath (Join-Path $OutputDir "sts_get_caller_identity.json")
$plan = Invoke-AwsJson -CommandArgs @("freetier", "get-account-plan-state") -OutputPath (Join-Path $OutputDir "freetier_get_account_plan_state.json") -AllowFailure
$usage = Invoke-AwsJson -CommandArgs @("freetier", "get-free-tier-usage") -OutputPath (Join-Path $OutputDir "freetier_get_free_tier_usage.json") -AllowFailure

$usageRows = @()
if ($usage -and $usage.freeTierUsages) {
    foreach ($item in $usage.freeTierUsages) {
        $actual = if ($null -ne $item.actualUsageAmount) { [double]$item.actualUsageAmount } else { 0.0 }
        $forecast = if ($null -ne $item.forecastedUsageAmount) { [double]$item.forecastedUsageAmount } else { 0.0 }
        $limit = if ($null -ne $item.limit) { [double]$item.limit } else { 0.0 }
        $actualPct = Convert-ToPercent -Numerator $actual -Denominator $limit
        $forecastPct = Convert-ToPercent -Numerator $forecast -Denominator $limit

        $usageRows += [pscustomobject]@{
            service       = Get-ValueOrDefault $item.service
            region        = Get-ValueOrDefault $item.region
            freeTierType  = Get-ValueOrDefault $item.freeTierType
            usageType     = Get-ValueOrDefault $item.usageType
            operation     = Get-ValueOrDefault $item.operation
            actualUsage   = $actual
            forecastUsage = $forecast
            limit         = $limit
            unit          = Get-ValueOrDefault $item.unit
            actualPct     = $actualPct
            forecastPct   = $forecastPct
            description   = Get-ValueOrDefault $item.description
        }
    }

    $usageRows |
        Sort-Object @{ Expression = { if ($null -eq $_.forecastPct) { -1 } else { $_.forecastPct } } } -Descending |
        Export-Csv -NoTypeInformation -Path (Join-Path $OutputDir "freetier_usage_ranked.csv")
}

$inventorySummary = [ordered]@{}
if ($IncludeInventory) {
    $instances = Invoke-AwsJson -CommandArgs @("ec2", "describe-instances") -OutputPath (Join-Path $OutputDir "ec2_describe_instances.json") -AllowFailure
    $volumes = Invoke-AwsJson -CommandArgs @("ec2", "describe-volumes") -OutputPath (Join-Path $OutputDir "ec2_describe_volumes.json") -AllowFailure
    $addresses = Invoke-AwsJson -CommandArgs @("ec2", "describe-addresses") -OutputPath (Join-Path $OutputDir "ec2_describe_addresses.json") -AllowFailure
    $natGateways = Invoke-AwsJson -CommandArgs @("ec2", "describe-nat-gateways") -OutputPath (Join-Path $OutputDir "ec2_describe_nat_gateways.json") -AllowFailure
    $loadBalancers = Invoke-AwsJson -CommandArgs @("elbv2", "describe-load-balancers") -OutputPath (Join-Path $OutputDir "elbv2_describe_load_balancers.json") -AllowFailure
    $dbInstances = Invoke-AwsJson -CommandArgs @("rds", "describe-db-instances") -OutputPath (Join-Path $OutputDir "rds_describe_db_instances.json") -AllowFailure
    $eksClusters = Invoke-AwsJson -CommandArgs @("eks", "list-clusters") -OutputPath (Join-Path $OutputDir "eks_list_clusters.json") -AllowFailure

    $instanceCount = 0
    if ($instances -and $instances.Reservations) {
        foreach ($reservation in $instances.Reservations) {
            if ($reservation.Instances) {
                $instanceCount += @($reservation.Instances).Count
            }
        }
    }

    $inventorySummary["ec2Instances"] = $instanceCount
    $inventorySummary["ebsVolumes"] = if ($volumes) { @($volumes.Volumes).Count } else { 0 }
    $inventorySummary["elasticIps"] = if ($addresses) { @($addresses.Addresses).Count } else { 0 }
    $inventorySummary["natGateways"] = if ($natGateways) { @($natGateways.NatGateways).Count } else { 0 }
    $inventorySummary["loadBalancers"] = if ($loadBalancers) { @($loadBalancers.LoadBalancers).Count } else { 0 }
    $inventorySummary["rdsInstances"] = if ($dbInstances) { @($dbInstances.DBInstances).Count } else { 0 }
    $inventorySummary["eksClusters"] = if ($eksClusters) { @($eksClusters.clusters).Count } else { 0 }
}

Add-MarkdownLine -Lines $summaryLines -Text "# AWS Free Tier and Credit Check"
Add-MarkdownLine -Lines $summaryLines
Add-MarkdownLine -Lines $summaryLines -Text "- Collected at: `$collectedAt`"
Add-MarkdownLine -Lines $summaryLines -Text "- AWS CLI: `$awsVersion`"
Add-MarkdownLine -Lines $summaryLines -Text "- Profile: `$(if ($Profile) { $Profile } else { "default" })`"
Add-MarkdownLine -Lines $summaryLines -Text "- Region used for CLI calls: `$Region`"
Add-MarkdownLine -Lines $summaryLines

Add-MarkdownLine -Lines $summaryLines -Text "## Account"
Add-MarkdownLine -Lines $summaryLines
Add-MarkdownLine -Lines $summaryLines -Text "- Account ID: `$(Get-ValueOrDefault $identity.Account)`"
Add-MarkdownLine -Lines $summaryLines -Text "- ARN: `$(Get-ValueOrDefault $identity.Arn)`"
Add-MarkdownLine -Lines $summaryLines

Add-MarkdownLine -Lines $summaryLines -Text "## Free Tier Plan State"
Add-MarkdownLine -Lines $summaryLines
if ($plan) {
    $creditAmount = if ($plan.accountPlanRemainingCredits) { $plan.accountPlanRemainingCredits.amount } else { $null }
    $creditUnit = if ($plan.accountPlanRemainingCredits) { $plan.accountPlanRemainingCredits.unit } else { $null }
    Add-MarkdownLine -Lines $summaryLines -Text "- Plan type: `$(Get-ValueOrDefault $plan.accountPlanType)`"
    Add-MarkdownLine -Lines $summaryLines -Text "- Plan status: `$(Get-ValueOrDefault $plan.accountPlanStatus)`"
    Add-MarkdownLine -Lines $summaryLines -Text "- Remaining credits: `$(if ($null -ne $creditAmount) { "$creditAmount $creditUnit" } else { "n/a" })`"
    Add-MarkdownLine -Lines $summaryLines -Text "- Plan expiration: `$(Get-ValueOrDefault $plan.accountPlanExpirationDate)`"
} else {
    Add-MarkdownLine -Lines $summaryLines -Text "- Free Tier plan state could not be retrieved with the current account/CLI setup."
}
Add-MarkdownLine -Lines $summaryLines

Add-MarkdownLine -Lines $summaryLines -Text "## Free Tier Usage Snapshot"
Add-MarkdownLine -Lines $summaryLines
if ($usageRows.Count -gt 0) {
    Add-MarkdownLine -Lines $summaryLines -Text "| Service | Region | Type | Forecast % | Actual % | Limit | Unit |"
    Add-MarkdownLine -Lines $summaryLines -Text "|---|---|---|---:|---:|---:|---|"
    foreach ($row in ($usageRows | Sort-Object @{ Expression = { if ($null -eq $_.forecastPct) { -1 } else { $_.forecastPct } } } -Descending | Select-Object -First 20)) {
        $forecastPctText = if ($null -ne $row.forecastPct) { $row.forecastPct } else { "n/a" }
        $actualPctText = if ($null -ne $row.actualPct) { $row.actualPct } else { "n/a" }
        Add-MarkdownLine -Lines $summaryLines -Text "| $($row.service) | $($row.region) | $($row.freeTierType) | $forecastPctText | $actualPctText | $($row.limit) | $($row.unit) |"
    }
    Add-MarkdownLine -Lines $summaryLines
    Add-MarkdownLine -Lines $summaryLines -Text "Full ranked output is saved in `freetier_usage_ranked.csv`."
} else {
    Add-MarkdownLine -Lines $summaryLines -Text "- No Free Tier usage data was returned, or the API was unavailable for this account."
}
Add-MarkdownLine -Lines $summaryLines

if ($IncludeInventory) {
    Add-MarkdownLine -Lines $summaryLines -Text "## Resource Inventory Snapshot"
    Add-MarkdownLine -Lines $summaryLines
    foreach ($key in $inventorySummary.Keys) {
        Add-MarkdownLine -Lines $summaryLines -Text ("- {0}: {1}" -f $key, (Get-ValueOrDefault -Value $inventorySummary[$key] -Default "0"))
    }
    Add-MarkdownLine -Lines $summaryLines
}

Add-MarkdownLine -Lines $summaryLines -Text "## Interpretation Notes"
Add-MarkdownLine -Lines $summaryLines
Add-MarkdownLine -Lines $summaryLines -Text "- This script can show your Free Tier plan state, remaining credits when the API exposes them, and current tracked Free Tier usage."
Add-MarkdownLine -Lines $summaryLines -Text "- It does **not** prove that every AWS service is billable under credits; AWS credits still depend on plan type and credit eligibility terms."
Add-MarkdownLine -Lines $summaryLines -Text "- It does **not** replace service pricing review before a large stress test."
Add-MarkdownLine -Lines $summaryLines -Text "- For this RAASA project, the inventory snapshot helps verify whether an EC2/K3s testbed still exists before you reboot or scale it further."

$summaryLines | Set-Content -Path (Join-Path $OutputDir "summary.md")

Write-Host "Saved AWS account check to: $OutputDir"
Write-Host "Primary summary: $(Join-Path $OutputDir 'summary.md')"
