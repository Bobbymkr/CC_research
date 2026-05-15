param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$ConfigPath = (Join-Path (Get-Location) "raasa\configs\config_tuned_small_linear_probe.yaml"),

    [string]$ConfigMapNamespace = "raasa-system",

    [string]$ConfigMapName = "raasa-config",

    [string]$DaemonSetName = "raasa-agent",

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\config_apply_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH to an untracked PEM file."
}
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Config not found: $ConfigPath"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath
$remoteConfig = "/tmp/raasa-config-" + [guid]::NewGuid().ToString() + ".yaml"

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

    Invoke-SSH "sudo k3s kubectl get configmap $ConfigMapName -n $ConfigMapNamespace -o yaml" |
        Set-Content -Path (Join-Path $OutputDir "configmap_before.yaml")

    Invoke-SSH "sudo k3s kubectl get daemonset $DaemonSetName -n $ConfigMapNamespace -o jsonpath='{.spec.template.spec.containers[*].image}'" |
        Set-Content -Path (Join-Path $OutputDir "daemonset_images_before.txt")

    Copy-Remote -LocalPath $ConfigPath -RemotePath $remoteConfig

    Invoke-SSH "sudo k3s kubectl create configmap $ConfigMapName -n $ConfigMapNamespace --from-file=config.yaml=$remoteConfig --dry-run=client -o yaml | sudo k3s kubectl apply -f -" |
        Set-Content -Path (Join-Path $OutputDir "configmap_apply.txt")

    Invoke-SSH "sudo k3s kubectl rollout restart daemonset/$DaemonSetName -n $ConfigMapNamespace" |
        Set-Content -Path (Join-Path $OutputDir "rollout_restart.txt")

    Invoke-SSH "sudo k3s kubectl rollout status daemonset/$DaemonSetName -n $ConfigMapNamespace --timeout=300s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_status.txt")

    Invoke-SSH "sudo k3s kubectl get configmap $ConfigMapName -n $ConfigMapNamespace -o yaml" |
        Set-Content -Path (Join-Path $OutputDir "configmap_after.yaml")

    Invoke-SSH "sudo k3s kubectl get pods -n $ConfigMapNamespace -l app=raasa-agent -o wide" |
        Set-Content -Path (Join-Path $OutputDir "pods_after_apply.txt")

    @(
        "Host=$TargetHost",
        "User=$User",
        "ConfigPath=$ConfigPath",
        "ConfigMapNamespace=$ConfigMapNamespace",
        "ConfigMapName=$ConfigMapName",
        "DaemonSetName=$DaemonSetName",
        "CollectedAtLocal=" + (Get-Date).ToString("o")
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Write-Host "Config apply evidence collected in: $OutputDir"
}
finally {
    try {
        Invoke-SSH "rm -f $remoteConfig" | Out-Null
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
