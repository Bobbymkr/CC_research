param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\\deep_diagnose_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

function Invoke-SSH {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TempKey,

        [Parameter(Mandatory = $true)]
        [string]$RemoteCommand
    )

    & "C:\WINDOWS\System32\OpenSSH\ssh.exe" `
        -n `
        -i $TempKey `
        -o StrictHostKeyChecking=no `
        -o UserKnownHostsFile=NUL `
        -o LogLevel=ERROR `
        "$User@$TargetHost" `
        $RemoteCommand
}

function Save-RemoteOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TempKey,

        [Parameter(Mandatory = $true)]
        [string]$RemoteCommand,

        [Parameter(Mandatory = $true)]
        [string]$FileName
    )

    Invoke-SSH -TempKey $TempKey -RemoteCommand $RemoteCommand |
        Set-Content -Path (Join-Path $OutputDir $FileName)
}

if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found. Pass -KeyPath or set RAASA_AWS_KEY_PATH to an untracked PEM file."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tempKey = New-RestrictedKeyCopy -SourcePath $KeyPath

try {
    $agentPod = (Invoke-SSH -TempKey $tempKey -RemoteCommand "sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent -o jsonpath='{.items[0].metadata.name}'").Trim()
    if (-not $agentPod) {
        throw "Could not resolve raasa-agent pod name."
    }

    $metricsServerPod = (Invoke-SSH -TempKey $tempKey -RemoteCommand "sudo k3s kubectl get pods -n kube-system -l k8s-app=metrics-server -o jsonpath='{.items[0].metadata.name}'").Trim()
    if (-not $metricsServerPod) {
        throw "Could not resolve metrics-server pod name."
    }

    $enforcerSocketCheckCommand = "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-enforcer -- sh -lc 'id; if [ -S /var/run/raasa/ipc/enforcer.sock ]; then echo sock_exists=yes; else echo sock_exists=no; fi; ls -la /var/run/raasa /var/run/raasa/ipc'"
    $agentSocketCheckCommand = "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-agent -- sh -lc 'id; if [ -S /var/run/raasa/ipc/enforcer.sock ]; then echo sock_exists=yes; else echo sock_exists=no; fi; ls -la /var/run/raasa /var/run/raasa/ipc'"
    $enforcerPsCommand = "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-enforcer -- sh -lc 'if command -v ps >/dev/null 2>&1; then ps -ef; else echo ps-not-found; cat /proc/1/comm; fi'"

    @(
        "Host=$TargetHost",
        "User=$User",
        "CollectedAtLocal=" + (Get-Date).ToString("o"),
        "AgentPod=$agentPod",
        "MetricsServerPod=$metricsServerPod"
    ) | Set-Content -Path (Join-Path $OutputDir "meta.txt")

    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl get pod -n raasa-system $agentPod -o yaml" -FileName "agent_pod.yaml"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl describe pod -n raasa-system $agentPod" -FileName "agent_pod.describe.txt"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl get daemonset -n raasa-system raasa-agent -o yaml" -FileName "daemonset_live.yaml"

    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-agent --tail=200" -FileName "raasa_agent.log"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl logs -n raasa-system $agentPod -c raasa-enforcer --tail=200" -FileName "raasa_enforcer.log"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl logs -n raasa-system $agentPod -c syscall-probe --tail=200" -FileName "syscall_probe.log"

    Save-RemoteOutput -TempKey $tempKey -RemoteCommand $enforcerSocketCheckCommand -FileName "enforcer_socket_check.txt"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand $enforcerPsCommand -FileName "enforcer_ps.txt"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand $agentSocketCheckCommand -FileName "agent_socket_check.txt"

    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl get pods -n kube-system -l k8s-app=metrics-server -o yaml" -FileName "metrics_server_pods.yaml"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl describe deployment -n kube-system metrics-server" -FileName "metrics_server_deploy.describe.txt"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl describe pod -n kube-system $metricsServerPod" -FileName "metrics_server_pod.describe.txt"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl get apiservice v1beta1.metrics.k8s.io -o yaml" -FileName "metrics_apiservice.yaml"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl top nodes" -FileName "kubectl_top_nodes.txt"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl top pods -A" -FileName "kubectl_top_pods_all.txt"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes" -FileName "metrics_nodes_raw.json"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods" -FileName "metrics_pods_raw.json"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo k3s kubectl logs -n kube-system $metricsServerPod --tail=200" -FileName "metrics_server_tail_200.txt"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo sh -lc 'if [ -f /run/flannel/subnet.env ]; then cat /run/flannel/subnet.env; else echo subnet_env_missing; fi'" -FileName "flannel_subnet_env.txt"
    Save-RemoteOutput -TempKey $tempKey -RemoteCommand "sudo journalctl -u k3s -n 200 --no-pager" -FileName "k3s_journal_tail_200.txt"

    Write-Host "Deep diagnosis collected in: $OutputDir"
}
finally {
    try {
        Remove-Item -LiteralPath $tempKey -Force -ErrorAction Stop
    }
    catch {
        Write-Warning "Could not remove temporary key copy: $tempKey"
    }
}
