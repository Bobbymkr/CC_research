param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$ManifestPath = "C:\Users\Admin\OneDrive\Desktop\CC\CC_research\raasa\k8s\phase1b-network-benchmark.yaml",

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\phase1c_pod_specific_validation_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
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

    function Invoke-Benchmark {
        param([string]$Label)

        $clientPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-bench -l app=raasa-bench-client -o jsonpath='{.items[0].metadata.name}'").Trim()
        if (-not $clientPod) {
            throw "Could not find benchmark client pod."
        }

        $outputPath = Join-Path $OutputDir "${Label}_measurements.txt"
        if (Test-Path -LiteralPath $outputPath) {
            Remove-Item -LiteralPath $outputPath -Force
        }

        for ($i = 1; $i -le 3; $i++) {
            $measurement = (Invoke-SSH "sudo k3s kubectl exec -n raasa-bench $clientPod -- curl -sS -o /dev/null -w '%{time_total} %{speed_download}' http://raasa-bench-server.raasa-bench.svc.cluster.local/payload.bin").Trim()
            Add-Content -Path $outputPath -Value $measurement
        }
    }

    function Send-EnforcementCommand {
        param(
            [string]$AgentPod,
            [string]$ContainerRef,
            [string]$Tier,
            [string]$OutputName
        )

        $localScript = Join-Path $env:TEMP ("raasa-send-enforcement-" + [guid]::NewGuid().ToString() + ".py")
        @'
from raasa.core.ipc import UnixSocketClient
import os
import sys

payload = {
    "container_id": os.environ["CONTAINER_REF"],
    "tier": os.environ["TARGET_TIER"],
}
ok = UnixSocketClient().send_command(payload)
print("OK" if ok else "ERR")
raise SystemExit(0 if ok else 1)
'@ | Set-Content -Path $localScript

        try {
            Copy-Remote -LocalPath $localScript -RemotePath "/tmp/raasa-send-enforcement.py"
            Invoke-SSH "CONTAINER_REF='$ContainerRef' TARGET_TIER='$Tier' cat /tmp/raasa-send-enforcement.py | sudo k3s kubectl exec -i -n raasa-system $AgentPod -c raasa-agent -- env CONTAINER_REF='$ContainerRef' TARGET_TIER='$Tier' python -" |
                Set-Content -Path (Join-Path $OutputDir $OutputName)
        }
        finally {
            if (Test-Path -LiteralPath $localScript) {
                Remove-Item -LiteralPath $localScript -Force -ErrorAction SilentlyContinue
            }
        }
    }

    function Get-MetricSummary {
        param([string]$Path)

        $rows = @()
        foreach ($line in Get-Content -LiteralPath $Path) {
            $parts = $line.Trim() -split "\s+"
            if ($parts.Length -ne 2) {
                continue
            }
            $rows += [pscustomobject]@{
                time_total_sec = [double]$parts[0]
                speed_bytes_per_sec = [double]$parts[1]
            }
        }

        if ($rows.Count -eq 0) {
            return @{
                samples = 0
                raw = @()
            }
        }

        return @{
            samples = $rows.Count
            avg_time_total_sec = ($rows | Measure-Object -Property time_total_sec -Average).Average
            avg_speed_bytes_per_sec = ($rows | Measure-Object -Property speed_bytes_per_sec -Average).Average
            raw = @($rows)
        }
    }

    Copy-Remote -LocalPath $ManifestPath -RemotePath "/tmp/phase1c-network-benchmark.yaml"
    Invoke-SSH "sudo k3s kubectl apply -f /tmp/phase1c-network-benchmark.yaml" |
        Set-Content -Path (Join-Path $OutputDir "kubectl_apply.txt")

    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-bench-server -n raasa-bench --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_server.txt")
    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-bench-client -n raasa-bench --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_client.txt")

    $agentPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o jsonpath='{.items[0].metadata.name}'").Trim()
    $clientPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-bench -l app=raasa-bench-client -o jsonpath='{.items[0].metadata.name}'").Trim()
    if (-not $agentPod) {
        throw "Could not find RAASA agent pod."
    }
    if (-not $clientPod) {
        throw "Could not find benchmark client pod."
    }
    $containerRef = "raasa-bench/$clientPod"

    @(
        "Host=$TargetHost",
        "User=$User",
        "CollectedAtLocal=" + (Get-Date).ToString("o"),
        "ManifestPath=$ManifestPath",
        "AgentPod=$agentPod",
        "ContainerRef=$containerRef"
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Invoke-SSH "sudo k3s kubectl get pods -n raasa-bench -o wide" |
        Set-Content -Path (Join-Path $OutputDir "bench_pods.txt")

    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $containerRef -Tier "L1" -OutputName "send_l1.txt"
    Start-Sleep -Seconds 3
    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=120" |
        Set-Content -Path (Join-Path $OutputDir "enforcer_logs_after_l1.txt")
    Invoke-Benchmark -Label "l1"

    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $containerRef -Tier "L3" -OutputName "send_l3.txt"
    Start-Sleep -Seconds 3
    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=160" |
        Set-Content -Path (Join-Path $OutputDir "enforcer_logs_after_l3.txt")
    Invoke-Benchmark -Label "l3"

    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $containerRef -Tier "L1" -OutputName "send_restore_l1.txt"
    Start-Sleep -Seconds 2
    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=200" |
        Set-Content -Path (Join-Path $OutputDir "enforcer_logs_final.txt")

    $l1 = Get-MetricSummary -Path (Join-Path $OutputDir "l1_measurements.txt")
    $l3 = Get-MetricSummary -Path (Join-Path $OutputDir "l3_measurements.txt")
    $summary = @{
        l1 = $l1
        l3 = $l3
    }
    if ($l1.samples -gt 0 -and $l3.samples -gt 0) {
        $summary.comparison = @{
            speed_ratio_l3_vs_l1 = $l3.avg_speed_bytes_per_sec / $l1.avg_speed_bytes_per_sec
            time_ratio_l3_vs_l1 = $l3.avg_time_total_sec / $l1.avg_time_total_sec
        }
    }
    $summary | ConvertTo-Json -Depth 6 | Set-Content -Path (Join-Path $OutputDir "summary.json")

    Write-Host "Phase 1C pod-specific validation evidence collected in: $OutputDir"
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
