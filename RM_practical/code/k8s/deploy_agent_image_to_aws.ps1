param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$ImageTag = "raasa/agent:phase1c",

    [string]$DaemonSetNamespace = "raasa-system",

    [string]$DaemonSetName = "raasa-agent",

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\deploy_agent_image_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, "Read", "Allow")

    $acl.SetOwner($owner)
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $tempPath -AclObject $acl

    return $tempPath
}

if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH to an untracked PEM file."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath
$imageTar = Join-Path $env:TEMP ("raasa-agent-image-" + [guid]::NewGuid().ToString() + ".tar")

try {
    function Invoke-SSH {
        param([string]$RemoteCommand)

        & "C:\WINDOWS\System32\OpenSSH\ssh.exe" `
            -n `
            -i $tempKey `
            -o StrictHostKeyChecking=no `
            -o UserKnownHostsFile=NUL `
            -o LogLevel=ERROR `
            "$User@$TargetHost" `
            $RemoteCommand
    }

    function Copy-Remote {
        param(
            [string]$LocalPath,
            [string]$RemotePath
        )

        & "C:\WINDOWS\System32\OpenSSH\scp.exe" `
            -i $tempKey `
            -o StrictHostKeyChecking=no `
            -o UserKnownHostsFile=NUL `
            -o LogLevel=ERROR `
            $LocalPath `
            "${User}@${TargetHost}:$RemotePath"
    }

    docker save -o $imageTar $ImageTag
    $remoteTar = "/tmp/" + [IO.Path]::GetFileName($imageTar)
    Copy-Remote -LocalPath $imageTar -RemotePath $remoteTar

    Invoke-SSH "sudo k3s ctr images import $remoteTar" |
        Set-Content -Path (Join-Path $OutputDir "ctr_import.txt")

    Invoke-SSH "sudo k3s kubectl set image daemonset/$DaemonSetName -n $DaemonSetNamespace raasa-agent=$ImageTag raasa-enforcer=$ImageTag" |
        Set-Content -Path (Join-Path $OutputDir "set_image.txt")

    Invoke-SSH "sudo k3s kubectl rollout restart daemonset/$DaemonSetName -n $DaemonSetNamespace" |
        Set-Content -Path (Join-Path $OutputDir "rollout_restart.txt")

    Invoke-SSH "sudo k3s kubectl rollout status daemonset/$DaemonSetName -n $DaemonSetNamespace --timeout=300s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_status.txt")

    Invoke-SSH "sudo k3s kubectl get pods -n $DaemonSetNamespace -l app=raasa-agent -o wide" |
        Set-Content -Path (Join-Path $OutputDir "pods_after_deploy.txt")

    @(
        "Host=$TargetHost",
        "User=$User",
        "ImageTag=$ImageTag",
        "CollectedAtLocal=" + (Get-Date).ToString("o")
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Write-Host "Deployment evidence collected in: $OutputDir"
}
finally {
    if (Test-Path -LiteralPath $imageTar) {
        Remove-Item -LiteralPath $imageTar -Force -ErrorAction SilentlyContinue
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
