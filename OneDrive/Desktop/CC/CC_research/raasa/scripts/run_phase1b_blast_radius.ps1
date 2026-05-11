param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = (Join-Path (Get-Location) "raasa-key-1.pem"),

    [string]$ManifestPath = "C:\Users\Admin\OneDrive\Desktop\CC\CC_research\raasa\k8s\phase1b-network-benchmark.yaml",

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\phase1b_blast_radius_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

if (-not (Test-Path -LiteralPath $KeyPath)) {
    throw "Key not found: $KeyPath"
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

    $agentPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o jsonpath='{.items[0].metadata.name}'").Trim()
    if (-not $agentPod) {
        throw "Could not find RAASA agent pod."
    }

    function Set-QdiscRate {
        param([string]$Rate)

        Invoke-SSH "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-enforcer -- sh -lc 'tc qdisc del dev cni0 root >/dev/null 2>&1 || true; tc qdisc add dev cni0 root tbf rate $Rate burst 32kbit latency 400ms; tc -s qdisc show dev cni0'"
    }

    function Get-QdiscStats {
        Invoke-SSH "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-enforcer -- sh -lc 'tc -s qdisc show dev cni0'"
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

    Copy-Remote -LocalPath $ManifestPath -RemotePath "/tmp/phase1b-network-benchmark.yaml"
    Invoke-SSH "sudo k3s kubectl apply -f /tmp/phase1b-network-benchmark.yaml" |
        Set-Content -Path (Join-Path $OutputDir "kubectl_apply.txt")

    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-bench-server -n raasa-bench --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_server.txt")
    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-bench-client -n raasa-bench --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_client.txt")

    Invoke-SSH "sudo k3s kubectl get pods -n raasa-bench -o wide" |
        Set-Content -Path (Join-Path $OutputDir "bench_pods.txt")

    @(
        "Host=$TargetHost",
        "User=$User",
        "CollectedAtLocal=" + (Get-Date).ToString("o"),
        "ManifestPath=$ManifestPath",
        "AgentPod=$agentPod"
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Set-QdiscRate -Rate "1000mbit" | Set-Content -Path (Join-Path $OutputDir "qdisc_l1.txt")
    Invoke-Benchmark -Label "l1"
    Get-QdiscStats | Set-Content -Path (Join-Path $OutputDir "qdisc_l1_post_benchmark.txt")

    Set-QdiscRate -Rate "1mbit" | Set-Content -Path (Join-Path $OutputDir "qdisc_l3.txt")
    Invoke-Benchmark -Label "l3"
    Get-QdiscStats | Set-Content -Path (Join-Path $OutputDir "qdisc_l3_post_benchmark.txt")

    Set-QdiscRate -Rate "1000mbit" | Set-Content -Path (Join-Path $OutputDir "qdisc_restored.txt")

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

    Write-Host "Phase 1B blast-radius evidence collected in: $OutputDir"
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
