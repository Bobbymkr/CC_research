param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$BenchmarkManifestPath = "C:\Users\Admin\OneDrive\Desktop\CC\CC_research\raasa\k8s\phase1b-network-benchmark.yaml",

    [string]$DemoManifestPath = "C:\Users\Admin\OneDrive\Desktop\CC\CC_research\raasa\k8s\test-network-pods.yaml",

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\phase1d_resolution_validation_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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
if (-not (Test-Path -LiteralPath $BenchmarkManifestPath)) {
    throw "Benchmark manifest not found: $BenchmarkManifestPath"
}
if (-not (Test-Path -LiteralPath $DemoManifestPath)) {
    throw "Demo manifest not found: $DemoManifestPath"
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
        param(
            [string]$ClientPod,
            [string]$Label,
            [string]$BenchmarkTarget
        )

        $outputPath = Join-Path $OutputDir "${Label}_measurements.txt"
        if (Test-Path -LiteralPath $outputPath) {
            Remove-Item -LiteralPath $outputPath -Force
        }

        for ($i = 1; $i -le 3; $i++) {
            $measurement = (Invoke-SSH "sudo k3s kubectl exec -n raasa-bench $ClientPod -- curl -sS -o /dev/null -w '%{time_total} %{speed_download}' http://${BenchmarkTarget}/payload.bin").Trim()
            Add-Content -Path $outputPath -Value $measurement
        }
    }

    function Capture-BenchmarkDiagnostics {
        param(
            [string]$ClientPod,
            [string]$Label,
            [string]$ServiceHost
        )

        $diagnosticPath = Join-Path $OutputDir "${Label}_dns_diagnostics.txt"
        $remoteCommand = @"
sudo k3s kubectl exec -n raasa-bench $ClientPod -- sh -lc '
echo "service_host=$ServiceHost"
echo "--- resolv.conf ---"
cat /etc/resolv.conf
echo "--- getent ---"
if command -v getent >/dev/null 2>&1; then getent hosts $ServiceHost || true; else echo "getent unavailable"; fi
echo "--- nslookup ---"
if command -v nslookup >/dev/null 2>&1; then nslookup $ServiceHost || true; else echo "nslookup unavailable"; fi
'
"@
        Invoke-SSH $remoteCommand | Set-Content -Path $diagnosticPath
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

    function Select-ResolutionSummary {
        param(
            [string[]]$LogLines,
            [string]$ContainerRef
        )

        $resolvedLine = $LogLines | Where-Object { $_ -like "*Resolved pod $ContainerRef to host interface*" } | Select-Object -Last 1
        $fallbackLine = $LogLines | Where-Object { $_ -like "*Falling back to interface*for $ContainerRef.*" } | Select-Object -Last 1

        return @{
            container_ref = $ContainerRef
            resolved = [bool]$resolvedLine
            resolved_line = if ($resolvedLine) { $resolvedLine } else { $null }
            fallback = [bool]$fallbackLine
            fallback_line = if ($fallbackLine) { $fallbackLine } else { $null }
        }
    }

    Copy-Remote -LocalPath $BenchmarkManifestPath -RemotePath "/tmp/phase1d-network-benchmark.yaml"
    Copy-Remote -LocalPath $DemoManifestPath -RemotePath "/tmp/phase1d-test-network-pods.yaml"

    Invoke-SSH "sudo k3s kubectl apply -f /tmp/phase1d-network-benchmark.yaml" |
        Set-Content -Path (Join-Path $OutputDir "kubectl_apply_benchmark.txt")
    Invoke-SSH "sudo k3s kubectl apply -f /tmp/phase1d-test-network-pods.yaml" |
        Set-Content -Path (Join-Path $OutputDir "kubectl_apply_demo.txt")

    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-bench-server -n raasa-bench --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_bench_server.txt")
    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-bench-client -n raasa-bench --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_bench_client.txt")
    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-net-server -n raasa-demo --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_demo_server.txt")
    Invoke-SSH "sudo k3s kubectl rollout status deployment/raasa-net-client -n raasa-demo --timeout=120s" |
        Set-Content -Path (Join-Path $OutputDir "rollout_demo_client.txt")

    $agentPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o jsonpath='{.items[0].metadata.name}'").Trim()
    $benchClientPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-bench -l app=raasa-bench-client -o jsonpath='{.items[0].metadata.name}'").Trim()
    $benchServerPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-bench -l app=raasa-bench-server -o jsonpath='{.items[0].metadata.name}'").Trim()
    $benchServerPodIp = (Invoke-SSH "sudo k3s kubectl get pod -n raasa-bench $benchServerPod -o jsonpath='{.status.podIP}'").Trim()
    $benchServiceIp = (Invoke-SSH "sudo k3s kubectl get svc -n raasa-bench raasa-bench-server -o jsonpath='{.spec.clusterIP}'").Trim()
    $benchServiceHost = "raasa-bench-server.raasa-bench.svc.cluster.local"
    $demoClientPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-demo -l app=raasa-net-client -o jsonpath='{.items[0].metadata.name}'").Trim()
    $demoServerPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-demo -l app=raasa-net-server -o jsonpath='{.items[0].metadata.name}'").Trim()
    if (-not $agentPod) {
        throw "Could not find RAASA agent pod."
    }
    if (-not $benchClientPod) {
        throw "Could not find benchmark client pod."
    }
    if (-not $benchServerPod) {
        throw "Could not find benchmark server pod."
    }
    if (-not $benchServerPodIp) {
        throw "Could not find benchmark server pod IP."
    }
    if (-not $benchServiceIp) {
        throw "Could not find benchmark service ClusterIP."
    }
    if (-not $demoClientPod) {
        throw "Could not find demo client pod."
    }
    if (-not $demoServerPod) {
        throw "Could not find demo server pod."
    }

    $benchClientRef = "raasa-bench/$benchClientPod"
    $demoClientRef = "raasa-demo/$demoClientPod"
    $demoServerRef = "raasa-demo/$demoServerPod"

    @(
        "Host=$TargetHost",
        "User=$User",
        "CollectedAtLocal=" + (Get-Date).ToString("o"),
        "AgentPod=$agentPod",
        "BenchClientRef=$benchClientRef",
        "BenchServerPod=$benchServerPod",
        "BenchServerPodIp=$benchServerPodIp",
        "BenchServiceHost=$benchServiceHost",
        "BenchServiceIp=$benchServiceIp",
        "DemoClientRef=$demoClientRef",
        "DemoServerRef=$demoServerRef"
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Invoke-SSH "sudo k3s kubectl get pods -A -o wide" |
        Set-Content -Path (Join-Path $OutputDir "pods_all_wide.txt")

    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $demoServerRef -Tier "L2" -OutputName "send_demo_server_l2.txt"
    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $demoClientRef -Tier "L2" -OutputName "send_demo_client_l2.txt"
    Start-Sleep -Seconds 3
    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=180" |
        Set-Content -Path (Join-Path $OutputDir "enforcer_logs_after_demo_l2.txt")

    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $benchClientRef -Tier "L1" -OutputName "send_bench_l1.txt"
    Start-Sleep -Seconds 3
    Capture-BenchmarkDiagnostics -ClientPod $benchClientPod -Label "l1" -ServiceHost $benchServiceHost
    Invoke-Benchmark -ClientPod $benchClientPod -Label "l1_service" -BenchmarkTarget $benchServiceHost
    Invoke-Benchmark -ClientPod $benchClientPod -Label "l1_service_ip" -BenchmarkTarget $benchServiceIp
    Invoke-Benchmark -ClientPod $benchClientPod -Label "l1_pod_ip" -BenchmarkTarget $benchServerPodIp

    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $benchClientRef -Tier "L3" -OutputName "send_bench_l3.txt"
    Start-Sleep -Seconds 3
    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=220" |
        Set-Content -Path (Join-Path $OutputDir "enforcer_logs_after_bench_l3.txt")
    Capture-BenchmarkDiagnostics -ClientPod $benchClientPod -Label "l3" -ServiceHost $benchServiceHost
    Invoke-Benchmark -ClientPod $benchClientPod -Label "l3_service" -BenchmarkTarget $benchServiceHost
    Invoke-Benchmark -ClientPod $benchClientPod -Label "l3_service_ip" -BenchmarkTarget $benchServiceIp
    Invoke-Benchmark -ClientPod $benchClientPod -Label "l3_pod_ip" -BenchmarkTarget $benchServerPodIp

    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $demoServerRef -Tier "L1" -OutputName "send_demo_server_l1.txt"
    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $demoClientRef -Tier "L1" -OutputName "send_demo_client_l1.txt"
    Send-EnforcementCommand -AgentPod $agentPod -ContainerRef $benchClientRef -Tier "L1" -OutputName "send_bench_restore_l1.txt"
    Start-Sleep -Seconds 2
    Invoke-SSH "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=260" |
        Set-Content -Path (Join-Path $OutputDir "enforcer_logs_final.txt")

    $logLines = Get-Content -LiteralPath (Join-Path $OutputDir "enforcer_logs_final.txt")
    $l1Service = Get-MetricSummary -Path (Join-Path $OutputDir "l1_service_measurements.txt")
    $l1ServiceIp = Get-MetricSummary -Path (Join-Path $OutputDir "l1_service_ip_measurements.txt")
    $l1PodIp = Get-MetricSummary -Path (Join-Path $OutputDir "l1_pod_ip_measurements.txt")
    $l3Service = Get-MetricSummary -Path (Join-Path $OutputDir "l3_service_measurements.txt")
    $l3ServiceIp = Get-MetricSummary -Path (Join-Path $OutputDir "l3_service_ip_measurements.txt")
    $l3PodIp = Get-MetricSummary -Path (Join-Path $OutputDir "l3_pod_ip_measurements.txt")

    $summary = @{
        demo_server = Select-ResolutionSummary -LogLines $logLines -ContainerRef $demoServerRef
        demo_client = Select-ResolutionSummary -LogLines $logLines -ContainerRef $demoClientRef
        bench_client = Select-ResolutionSummary -LogLines $logLines -ContainerRef $benchClientRef
        fallback_lines = @($logLines | Where-Object { $_ -like "*Falling back to interface*" })
        benchmark_targets = @{
            service_host = $benchServiceHost
            service_ip = $benchServiceIp
            pod_ip = $benchServerPodIp
        }
        l1 = @{
            service = $l1Service
            service_ip = $l1ServiceIp
            pod_ip = $l1PodIp
        }
        l3 = @{
            service = $l3Service
            service_ip = $l3ServiceIp
            pod_ip = $l3PodIp
        }
    }
    if ($l1Service.samples -gt 0 -and $l3Service.samples -gt 0) {
        $summary["comparison"] = @{
            service = @{
                speed_ratio_l3_vs_l1 = $l3Service.avg_speed_bytes_per_sec / $l1Service.avg_speed_bytes_per_sec
                time_ratio_l3_vs_l1 = $l3Service.avg_time_total_sec / $l1Service.avg_time_total_sec
            }
        }
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $OutputDir "summary.json")

    Write-Host "Phase 1D resolution validation evidence collected in: $OutputDir"
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
