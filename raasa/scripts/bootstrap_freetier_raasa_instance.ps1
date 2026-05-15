param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$RemoteDir = "/home/ubuntu/CC_research",

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\bootstrap_freetier_instance_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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
        [string]$OutputPath,

        [int]$TimeoutSeconds = 900
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
            throw "$FilePath timed out after $TimeoutSeconds seconds."
        }
        $process.WaitForExit()
        $process.Refresh()

        $output = @()
        if (Test-Path -LiteralPath $stdoutPath) { $output += Get-Content -LiteralPath $stdoutPath }
        if (Test-Path -LiteralPath $stderrPath) { $output += Get-Content -LiteralPath $stderrPath }
        $output | Set-Content -Path $OutputPath
        $exitCode = if ($null -ne $process.ExitCode) { [int]$process.ExitCode } else { 0 }
        if ($exitCode -ne 0) {
            throw "$FilePath failed with exit code $exitCode. See $OutputPath"
        }
        return @($output)
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH."
}
if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) {
    throw "tar.exe was not found on PATH."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath
$archive = Join-Path $env:TEMP ("raasa-source-" + [guid]::NewGuid().ToString() + ".tar.gz")

try {
    $tarOutput = Join-Path $OutputDir "create_archive.txt"
    $testFiles = Get-ChildItem -LiteralPath "tests" -Filter "*.py" -File |
        ForEach-Object { "tests/$($_.Name)" }
    $tarArgs = @(
        "-czf", $archive,
        "--exclude=raasa/__pycache__",
        "--exclude=raasa/*/__pycache__",
        "--exclude=raasa/logs",
        "--exclude=raasa/runtime",
        "--exclude=*.pem",
        "requirements.txt",
        "pyproject.toml",
        "pytest.ini",
        "README.md",
        "bootstrap_k8s_ebpf.sh",
        "raasa"
    ) + @($testFiles)
    Invoke-NativeCapture -FilePath "tar.exe" -ArgumentList $tarArgs -OutputPath $tarOutput -TimeoutSeconds 600 | Out-Null

    $sshBaseArgs = @(
        "-i", $tempKey,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        "-o", "LogLevel=ERROR"
    )

    Invoke-NativeCapture `
        -FilePath "C:\WINDOWS\System32\OpenSSH\ssh.exe" `
        -ArgumentList ($sshBaseArgs + @("$User@$TargetHost", "date -u '+%Y-%m-%dT%H:%M:%SZ'; hostname; uname -a")) `
        -OutputPath (Join-Path $OutputDir "ssh_preflight.txt") `
        -TimeoutSeconds 60 | Out-Null

    Invoke-NativeCapture `
        -FilePath "C:\WINDOWS\System32\OpenSSH\scp.exe" `
        -ArgumentList ($sshBaseArgs + @($archive, "${User}@${TargetHost}:/home/ubuntu/raasa-source.tar.gz")) `
        -OutputPath (Join-Path $OutputDir "scp_source.txt") `
        -TimeoutSeconds 900 | Out-Null

    $remoteCommand = @"
set -euo pipefail
rm -rf '$RemoteDir'
mkdir -p '$RemoteDir'
tar -xzf /home/ubuntu/raasa-source.tar.gz -C '$RemoteDir'
cd '$RemoteDir'
chmod +x raasa/scripts/aws_k3s_setup.sh
./raasa/scripts/aws_k3s_setup.sh
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl get pods -A -o wide
"@

    Invoke-NativeCapture `
        -FilePath "C:\WINDOWS\System32\OpenSSH\ssh.exe" `
        -ArgumentList ($sshBaseArgs + @("$User@$TargetHost", $remoteCommand)) `
        -OutputPath (Join-Path $OutputDir "remote_bootstrap.txt") `
        -TimeoutSeconds 2400 | Out-Null

    @(
        "TargetHost=$TargetHost",
        "User=$User",
        "RemoteDir=$RemoteDir",
        "CollectedAtLocal=" + (Get-Date).ToString("o")
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Write-Host "Bootstrap evidence collected in: $OutputDir"
}
finally {
    Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempKey -Force -ErrorAction SilentlyContinue
}
