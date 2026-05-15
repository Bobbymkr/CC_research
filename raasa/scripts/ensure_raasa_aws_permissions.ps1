param(
    [string]$AdminProfile = "",

    [string]$ValidationProfile = "raasa-gpu",

    [string]$Region = "us-east-1",

    [string]$TargetUserName = "raasa-codex-gpu-launcher",

    [string]$InstanceId = "i-02186b4ff024635db",

    [string]$PolicyName = "RAASAValidationEc2SsmFreeTier",

    [switch]$Apply,

    [switch]$Validate,

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\iam_permissions_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-AwsBaseArgs {
    param(
        [string]$Profile,
        [switch]$NoRegion
    )

    $args = @()
    if (-not [string]::IsNullOrWhiteSpace($Profile)) {
        $args += @("--profile", $Profile)
    }
    if (-not $NoRegion -and -not [string]::IsNullOrWhiteSpace($Region)) {
        $args += @("--region", $Region)
    }
    $args += "--no-cli-pager"
    return $args
}

function Invoke-Aws {
    param(
        [string]$Profile,
        [string[]]$CommandArgs,
        [switch]$NoRegion,
        [switch]$AllowFailure
    )

    $fullArgs = @() + (Get-AwsBaseArgs -Profile $Profile -NoRegion:$NoRegion) + $CommandArgs
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & aws @fullArgs 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "aws $($CommandArgs -join ' ') failed with exit code $exitCode.`n$($output -join [Environment]::NewLine)"
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = @($output)
    }
}

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "aws CLI was not found on PATH."
}
if ([string]::IsNullOrWhiteSpace($TargetUserName)) {
    throw "TargetUserName is required."
}
if ([string]::IsNullOrWhiteSpace($InstanceId)) {
    throw "InstanceId is required."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$identityResult = Invoke-Aws -Profile $AdminProfile -CommandArgs @("sts", "get-caller-identity", "--output", "json")
$identity = ($identityResult.Output -join [Environment]::NewLine) | ConvertFrom-Json
$accountId = [string]$identity.Account

$policy = [ordered]@{
    Version = "2012-10-17"
    Statement = @(
        [ordered]@{
            Sid      = "DescribeRaasaEc2Inventory"
            Effect   = "Allow"
            Action   = @(
                "ec2:DescribeAddresses",
                "ec2:DescribeImages",
                "ec2:DescribeInstanceStatus",
                "ec2:DescribeInstances",
                "ec2:DescribeKeyPairs",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeVolumes"
            )
            Resource = "*"
        },
        [ordered]@{
            Sid      = "StartAndStopKnownRaasaInstance"
            Effect   = "Allow"
            Action   = @(
                "ec2:StartInstances",
                "ec2:StopInstances"
            )
            Resource = "arn:aws:ec2:$Region`:$accountId`:instance/$InstanceId"
        },
        [ordered]@{
            Sid      = "ReadSsmAndFreeTierStatus"
            Effect   = "Allow"
            Action   = @(
                "freetier:GetAccountPlanState",
                "freetier:GetFreeTierUsage",
                "ssm:DescribeInstanceInformation",
                "sts:DecodeAuthorizationMessage",
                "sts:GetCallerIdentity"
            )
            Resource = "*"
        },
        [ordered]@{
            Sid      = "InspectOwnIamUserForDiagnostics"
            Effect   = "Allow"
            Action   = @(
                "iam:GetUser",
                "iam:ListAttachedUserPolicies",
                "iam:ListUserPolicies"
            )
            Resource = "arn:aws:iam::$accountId`:user/$TargetUserName"
        }
    )
}

$policyPath = Join-Path $OutputDir "$PolicyName.json"
$policy | ConvertTo-Json -Depth 16 | Set-Content -Path $policyPath -Encoding utf8

$summaryPath = Join-Path $OutputDir "summary.md"
@(
    "# RAASA AWS Permission Bootstrap",
    "",
    ("- Generated at: {0}" -f (Get-Date -Format o)),
    ("- Admin/caller ARN: {0}" -f $identity.Arn),
    ("- Target user: {0}" -f $TargetUserName),
    ("- Validation profile: {0}" -f $ValidationProfile),
    ("- Region: {0}" -f $Region),
    ("- Instance ID: {0}" -f $InstanceId),
    ("- Inline policy file: {0}" -f $policyPath),
    "",
    "## Apply Command",
    "",
    ("Run this with credentials that can call iam:PutUserPolicy on {0}:" -f $TargetUserName),
    "",
    "````powershell",
    ("powershell -ExecutionPolicy Bypass -File raasa/scripts/ensure_raasa_aws_permissions.ps1 -AdminProfile <admin-profile> -ValidationProfile {0} -Region {1} -TargetUserName {2} -InstanceId {3} -Apply -Validate" -f $ValidationProfile, $Region, $TargetUserName, $InstanceId),
    "````",
    "",
    "Equivalent AWS CLI call:",
    "",
    "````powershell",
    ("aws --profile <admin-profile> iam put-user-policy --user-name {0} --policy-name {1} --policy-document file://{2}" -f $TargetUserName, $PolicyName, $policyPath),
    "````"
) | Set-Content -Path $summaryPath -Encoding utf8

Write-Host "Wrote policy: $policyPath"
Write-Host "Wrote summary: $summaryPath"

if ($Apply) {
    Write-Host "Applying inline policy $PolicyName to IAM user $TargetUserName..."
    Invoke-Aws -Profile $AdminProfile -NoRegion -CommandArgs @(
        "iam",
        "put-user-policy",
        "--user-name",
        $TargetUserName,
        "--policy-name",
        $PolicyName,
        "--policy-document",
        "file://$policyPath"
    ) | Out-Null
    Write-Host "Applied inline policy."
}

if ($Validate) {
    Write-Host "Validating profile $ValidationProfile..."

    $checks = @(
        [pscustomobject]@{
            Name = "caller identity"
            Args = @("sts", "get-caller-identity", "--output", "json")
        },
        [pscustomobject]@{
            Name = "EC2 describe instance"
            Args = @("ec2", "describe-instances", "--instance-ids", $InstanceId, "--output", "json")
        },
        [pscustomobject]@{
            Name = "EC2 start dry run"
            Args = @("ec2", "start-instances", "--instance-ids", $InstanceId, "--dry-run", "--output", "json")
            DryRunSuccessText = "DryRunOperation"
        },
        [pscustomobject]@{
            Name = "Free Tier plan state"
            Args = @("freetier", "get-account-plan-state", "--output", "json")
        },
        [pscustomobject]@{
            Name = "SSM instance information"
            Args = @("ssm", "describe-instance-information", "--output", "json")
        }
    )

    $results = @()
    foreach ($check in $checks) {
        $result = Invoke-Aws -Profile $ValidationProfile -CommandArgs $check.Args -AllowFailure
        $text = ($result.Output -join [Environment]::NewLine)
        $ok = $result.ExitCode -eq 0
        if (-not $ok -and $check.PSObject.Properties.Name -contains "DryRunSuccessText") {
            $ok = $text -match [regex]::Escape($check.DryRunSuccessText)
        }

        $results += [pscustomobject]@{
            check = $check.Name
            ok = $ok
            exit_code = $result.ExitCode
            output = $text
        }
    }

    $results | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $OutputDir "validation_results.json") -Encoding utf8
    $results | Format-Table check, ok, exit_code -AutoSize

    $failed = @($results | Where-Object { -not $_.ok })
    if ($failed.Count -gt 0) {
        throw "One or more validation checks failed. See $OutputDir\validation_results.json."
    }
}
