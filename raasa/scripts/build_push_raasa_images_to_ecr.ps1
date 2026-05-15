param(
    [string]$Region = "us-east-1",

    [string]$Profile = "",

    [string]$AgentImageTag = "raasa/agent:1.0.0",

    [string]$ProbeImageTag = "raasa/ebpf-probe:1.0.0",

    [string]$AgentRepositoryName = "raasa-agent",

    [string]$ProbeRepositoryName = "raasa-ebpf-probe",

    [switch]$BuildLocalImages,

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\build_push_ecr_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

        [int[]]$AllowExitCodes = @(0),

        [int]$TimeoutSeconds = 1800
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
            throw "$ErrorContext failed with exit code $exitCode.`n$($output -join [Environment]::NewLine)"
        }

        return @($output)
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Get-AwsBaseArgs {
    $args = @("--region", $Region)
    if ($Profile) {
        $args = @("--profile", $Profile) + $args
    }
    $args += "--no-cli-pager"
    return $args
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker was not found on PATH."
}
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "aws CLI was not found on PATH."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$identity = & aws @(Get-AwsBaseArgs) sts get-caller-identity --output json | ConvertFrom-Json
$accountId = [string]$identity.Account
if ([string]::IsNullOrWhiteSpace($accountId)) {
    throw "Could not resolve AWS account ID."
}

if ($BuildLocalImages) {
    Invoke-NativeCapture -FilePath "docker" -ArgumentList @("build", "-t", $AgentImageTag, "-f", "raasa/k8s/Dockerfile", ".") -ErrorContext "Build agent image" -TimeoutSeconds 3600 | Set-Content -Path (Join-Path $OutputDir "docker_build_agent.txt")
    Invoke-NativeCapture -FilePath "docker" -ArgumentList @("build", "-t", $ProbeImageTag, "-f", "raasa/k8s/Dockerfile.ebpf", ".") -ErrorContext "Build eBPF probe image" -TimeoutSeconds 3600 | Set-Content -Path (Join-Path $OutputDir "docker_build_probe.txt")
}

$agentRepoUri = "${accountId}.dkr.ecr.${Region}.amazonaws.com/$AgentRepositoryName"
$probeRepoUri = "${accountId}.dkr.ecr.${Region}.amazonaws.com/$ProbeRepositoryName"
$agentTargetTag = "$agentRepoUri:1.0.0"
$probeTargetTag = "$probeRepoUri:1.0.0"

& aws @(Get-AwsBaseArgs) ecr describe-repositories --repository-names $AgentRepositoryName --output json 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    & aws @(Get-AwsBaseArgs) ecr create-repository --repository-name $AgentRepositoryName --image-tag-mutability MUTABLE --output json | Set-Content -Path (Join-Path $OutputDir "create_agent_repo.json")
}
& aws @(Get-AwsBaseArgs) ecr describe-repositories --repository-names $ProbeRepositoryName --output json 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    & aws @(Get-AwsBaseArgs) ecr create-repository --repository-name $ProbeRepositoryName --image-tag-mutability MUTABLE --output json | Set-Content -Path (Join-Path $OutputDir "create_probe_repo.json")
}

$registry = "${accountId}.dkr.ecr.${Region}.amazonaws.com"
$loginPassword = & aws @(Get-AwsBaseArgs) ecr get-login-password
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($loginPassword)) {
    throw "Failed to get ECR login password."
}
$loginPassword | docker login --username AWS --password-stdin $registry | Set-Content -Path (Join-Path $OutputDir "docker_login.txt")

Invoke-NativeCapture -FilePath "docker" -ArgumentList @("tag", $AgentImageTag, $agentTargetTag) -ErrorContext "Tag agent image" | Set-Content -Path (Join-Path $OutputDir "docker_tag_agent.txt")
Invoke-NativeCapture -FilePath "docker" -ArgumentList @("tag", $ProbeImageTag, $probeTargetTag) -ErrorContext "Tag probe image" | Set-Content -Path (Join-Path $OutputDir "docker_tag_probe.txt")
Invoke-NativeCapture -FilePath "docker" -ArgumentList @("push", $agentTargetTag) -ErrorContext "Push agent image" -TimeoutSeconds 3600 | Set-Content -Path (Join-Path $OutputDir "docker_push_agent.txt")
Invoke-NativeCapture -FilePath "docker" -ArgumentList @("push", $probeTargetTag) -ErrorContext "Push probe image" -TimeoutSeconds 3600 | Set-Content -Path (Join-Path $OutputDir "docker_push_probe.txt")

@(
    '# RAASA ECR Push Summary',
    '',
    ('- Region: {0}' -f $Region),
    ('- Account ID: {0}' -f $accountId),
    ('- Agent image source: {0}' -f $AgentImageTag),
    ('- Probe image source: {0}' -f $ProbeImageTag),
    ('- Agent image target: {0}' -f $agentTargetTag),
    ('- Probe image target: {0}' -f $probeTargetTag),
    '',
    'Set these before create_credit_gated_eks_cluster.sh:',
    '',
    '```powershell',
    ('$env:RAASA_AGENT_IMAGE_URI = ''{0}''' -f $agentTargetTag),
    ('$env:RAASA_PROBE_IMAGE_URI = ''{0}''' -f $probeTargetTag),
    '```'
) | Set-Content -Path (Join-Path $OutputDir 'summary.md')

Write-Host "ECR push evidence collected in: $OutputDir"
