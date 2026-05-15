param(
    [Parameter(Mandatory = $true)]
    [string]$ControlPlaneHost,

    [Parameter(Mandatory = $true)]
    [string[]]$WorkerHosts,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$RemoteDir = "/home/ubuntu/CC_research",

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\bootstrap_freetier_multinode_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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
if ($WorkerHosts.Count -ne 2) {
    throw "WorkerHosts must contain exactly two public IPs."
}
if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) {
    throw "tar.exe was not found on PATH."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath
$archive = Join-Path $env:TEMP ("raasa-source-" + [guid]::NewGuid().ToString() + ".tar.gz")
$allHosts = @($ControlPlaneHost) + @($WorkerHosts)

try {
    function Invoke-SSH {
        param(
            [Parameter(Mandatory = $true)]
            [string]$TargetHost,

            [Parameter(Mandatory = $true)]
            [string]$RemoteCommand,

            [string]$OutputFileName = "",

            [int]$TimeoutSeconds = 900
        )

        $outputPath = if ($OutputFileName) { Join-Path $OutputDir $OutputFileName } else { Join-Path $OutputDir ("ssh_" + [guid]::NewGuid().ToString() + ".txt") }
        $args = @(
            "-i", $tempKey,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=NUL",
            "-o", "LogLevel=ERROR",
            "$User@$TargetHost",
            $RemoteCommand
        )
        return Invoke-NativeCapture -FilePath "C:\WINDOWS\System32\OpenSSH\ssh.exe" -ArgumentList $args -OutputPath $outputPath -TimeoutSeconds $TimeoutSeconds
    }

    function Copy-Remote {
        param(
            [Parameter(Mandatory = $true)]
            [string]$TargetHost,

            [Parameter(Mandatory = $true)]
            [string]$LocalPath,

            [Parameter(Mandatory = $true)]
            [string]$RemotePath,

            [string]$OutputFileName = "",

            [int]$TimeoutSeconds = 900
        )

        $outputPath = if ($OutputFileName) { Join-Path $OutputDir $OutputFileName } else { Join-Path $OutputDir ("scp_" + [guid]::NewGuid().ToString() + ".txt") }
        $args = @(
            "-i", $tempKey,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=NUL",
            "-o", "LogLevel=ERROR",
            $LocalPath,
            "${User}@${TargetHost}:$RemotePath"
        )
        Invoke-NativeCapture -FilePath "C:\WINDOWS\System32\OpenSSH\scp.exe" -ArgumentList $args -OutputPath $outputPath -TimeoutSeconds $TimeoutSeconds | Out-Null
    }

    function Get-HostLabel {
        param([string]$TargetHost)

        if ($TargetHost -eq $ControlPlaneHost) { return "control-plane" }
        if ($TargetHost -eq $WorkerHosts[0]) { return "worker-a" }
        return "worker-b"
    }

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
    Invoke-NativeCapture -FilePath "tar.exe" -ArgumentList $tarArgs -OutputPath (Join-Path $OutputDir "create_archive.txt") -TimeoutSeconds 600 | Out-Null

    foreach ($targetHost in $allHosts) {
        $label = Get-HostLabel -TargetHost $targetHost
        Invoke-SSH -TargetHost $targetHost -RemoteCommand "date -u '+%Y-%m-%dT%H:%M:%SZ'; hostname; uname -a" -OutputFileName "${label}_ssh_preflight.txt" -TimeoutSeconds 90 | Out-Null
        Copy-Remote -TargetHost $targetHost -LocalPath $archive -RemotePath "/home/ubuntu/raasa-source.tar.gz" -OutputFileName "${label}_scp_source.txt" -TimeoutSeconds 900
        $extractCommand = @"
set -euo pipefail
rm -rf '$RemoteDir'
mkdir -p '$RemoteDir'
tar -xzf /home/ubuntu/raasa-source.tar.gz -C '$RemoteDir'
"@
        Invoke-SSH -TargetHost $targetHost -RemoteCommand $extractCommand -OutputFileName "${label}_extract_source.txt" -TimeoutSeconds 180 | Out-Null
    }

    $controlPlaneSetup = @"
set -euo pipefail
sudo apt-get update
sudo apt-get install -y docker.io containerd bc jq build-essential curl
sudo systemctl enable --now docker
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC='server --disable traefik --write-kubeconfig-mode 644' sh -
sleep 20
sudo k3s kubectl wait --for=condition=Ready node --all --timeout=180s
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown `$(id -u):`$(id -g) ~/.kube/config
export KUBECONFIG="`$HOME/.kube/config"
cd '$RemoteDir'
sudo docker build -t raasa/agent:1.0.0 -f raasa/k8s/Dockerfile .
sudo docker build -t raasa/ebpf-probe:1.0.0 -f raasa/k8s/Dockerfile.ebpf .
sudo docker save -o /tmp/raasa-agent-1.0.0.tar raasa/agent:1.0.0
sudo docker save -o /tmp/raasa-ebpf-probe-1.0.0.tar raasa/ebpf-probe:1.0.0
sudo k3s ctr images import /tmp/raasa-agent-1.0.0.tar
sudo k3s ctr images import /tmp/raasa-ebpf-probe-1.0.0.tar
printf 'private_ip=%s\n' "`$(hostname -I | awk '{print `$1}')"
printf 'node_token=%s\n' "`$(sudo cat /var/lib/rancher/k3s/server/node-token)"
"@
    $controlPlaneSetupLines = Invoke-SSH -TargetHost $ControlPlaneHost -RemoteCommand $controlPlaneSetup -OutputFileName "control_plane_setup.txt" -TimeoutSeconds 3600
    $setupMap = @{}
    foreach ($line in $controlPlaneSetupLines) {
        if ($line -match '^(?<key>[^=]+)=(?<value>.*)$') {
            $setupMap[$matches.key] = $matches.value
        }
    }
    $controlPlanePrivateIp = [string]$setupMap["private_ip"]
    $nodeToken = [string]$setupMap["node_token"]
    if ([string]::IsNullOrWhiteSpace($controlPlanePrivateIp) -or [string]::IsNullOrWhiteSpace($nodeToken)) {
        throw "Failed to capture control-plane private IP or node token. See control_plane_setup.txt."
    }

    for ($index = 0; $index -lt $WorkerHosts.Count; $index++) {
        $workerHost = $WorkerHosts[$index]
        $workerLabel = if ($index -eq 0) { "worker-a" } else { "worker-b" }
        $workerJoinUrl = "https://$($controlPlanePrivateIp):6443"
        $workerSetup = @"
set -euo pipefail
sudo apt-get update
sudo apt-get install -y docker.io containerd bc jq build-essential curl
sudo systemctl enable --now docker
curl -sfL https://get.k3s.io | K3S_URL='$workerJoinUrl' K3S_TOKEN='$nodeToken' sh -
sleep 20
sudo systemctl enable --now k3s-agent
cd '$RemoteDir'
sudo docker build -t raasa/agent:1.0.0 -f raasa/k8s/Dockerfile .
sudo docker build -t raasa/ebpf-probe:1.0.0 -f raasa/k8s/Dockerfile.ebpf .
sudo docker save -o /tmp/raasa-agent-1.0.0.tar raasa/agent:1.0.0
sudo docker save -o /tmp/raasa-ebpf-probe-1.0.0.tar raasa/ebpf-probe:1.0.0
sudo k3s ctr images import /tmp/raasa-agent-1.0.0.tar
sudo k3s ctr images import /tmp/raasa-ebpf-probe-1.0.0.tar
hostname
"@
        Invoke-SSH -TargetHost $workerHost -RemoteCommand $workerSetup -OutputFileName "${workerLabel}_setup.txt" -TimeoutSeconds 3600 | Out-Null
    }

    $clusterFinalize = @"
set -euo pipefail
export KUBECONFIG="`$HOME/.kube/config"
kubectl wait --for=condition=Ready node --all --timeout=240s
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch -n kube-system deployment metrics-server --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]' >/dev/null 2>&1 || true
kubectl rollout status deployment/metrics-server -n kube-system --timeout=240s
kubectl apply -f '$RemoteDir/raasa/k8s/daemonset.yaml'
kubectl rollout status daemonset/raasa-agent -n raasa-system --timeout=360s
kubectl apply -f '$RemoteDir/raasa/k8s/phase0-test-pods.yaml'
kubectl wait --for=condition=Ready pod -l app=raasa-test -n default --timeout=240s
kubectl get nodes -o wide
echo '---'
kubectl get pods -A -o wide
"@
    $clusterFinalizeLines = Invoke-SSH -TargetHost $ControlPlaneHost -RemoteCommand $clusterFinalize -OutputFileName "cluster_finalize.txt" -TimeoutSeconds 2400
    $clusterFinalizeLines | Set-Content -Path (Join-Path $OutputDir "cluster_topology.txt")

    Invoke-SSH -TargetHost $ControlPlaneHost -RemoteCommand "export KUBECONFIG='`$HOME/.kube/config'; kubectl get daemonset raasa-agent -n raasa-system -o wide" -OutputFileName "daemonset_after_bootstrap.txt" -TimeoutSeconds 120 | Out-Null
    Invoke-SSH -TargetHost $ControlPlaneHost -RemoteCommand "export KUBECONFIG='`$HOME/.kube/config'; kubectl get pods -n raasa-system -l app=raasa-agent -o wide" -OutputFileName "raasa_agent_pods.txt" -TimeoutSeconds 120 | Out-Null

    @(
        "ControlPlaneHost=$ControlPlaneHost",
        "WorkerHostA=$($WorkerHosts[0])",
        "WorkerHostB=$($WorkerHosts[1])",
        "ControlPlanePrivateIp=$controlPlanePrivateIp",
        "RemoteDir=$RemoteDir",
        "CollectedAtLocal=" + (Get-Date).ToString("o")
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Write-Host "Multi-node bootstrap evidence collected in: $OutputDir"
}
finally {
    Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempKey -Force -ErrorAction SilentlyContinue
}
