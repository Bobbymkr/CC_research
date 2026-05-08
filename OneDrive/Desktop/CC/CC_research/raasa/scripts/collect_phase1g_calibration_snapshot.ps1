param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = (Join-Path (Get-Location) "raasa-key-1.pem"),

    [int]$WarmupSeconds = 25,

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\phase1g_calibration_snapshot_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

if (-not (Test-Path -LiteralPath $KeyPath)) {
    throw "Key not found: $KeyPath"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath

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

    if ($WarmupSeconds -gt 0) {
        Start-Sleep -Seconds $WarmupSeconds
    }

    $agentPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o jsonpath='{.items[0].metadata.name}'").Trim()
    $latestLog = (Invoke-SSH "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-agent -- sh -lc 'ls -t /app/raasa/logs/run_*.jsonl 2>/dev/null | head -n 1'").Trim()

    @(
        "Host=$TargetHost",
        "User=$User",
        "WarmupSeconds=$WarmupSeconds",
        "AgentPod=$agentPod",
        "LatestLog=$latestLog",
        "CollectedAtLocal=" + (Get-Date).ToString("o")
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Invoke-SSH "sudo k3s kubectl get configmap raasa-config -n raasa-system -o yaml" |
        Set-Content -Path (Join-Path $OutputDir "configmap_live.yaml")

    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-agent --tail=80" |
        Set-Content -Path (Join-Path $OutputDir "agent_stdout_tail_80.txt")

    if ($latestLog) {
        Invoke-SSH "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-agent -- python -m raasa.core.review status --log $latestLog" |
            Set-Content -Path (Join-Path $OutputDir "review_status.txt")

        Invoke-SSH "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-agent -- python -m raasa.core.review audit --log $latestLog --limit 40" |
            Set-Content -Path (Join-Path $OutputDir "review_audit_tail_40.txt")
    }

    Write-Host "Calibration snapshot collected in: $OutputDir"
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
