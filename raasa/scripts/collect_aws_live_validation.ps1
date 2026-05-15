param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "ubuntu",

    [string]$KeyPath = $env:RAASA_AWS_KEY_PATH,

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\\live_instance_validation_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
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

    $maliciousNamespace = "default"
    $maliciousPod = (Invoke-SSH "sudo k3s kubectl get pods -n default -l raasa.class=malicious -o jsonpath='{.items[0].metadata.name}'" 2>$null).Trim()
    if ([string]::IsNullOrWhiteSpace($maliciousPod)) {
        $maliciousCandidates = @(
            Invoke-SSH "sudo k3s kubectl get pods -A -l raasa.class=malicious -o jsonpath='{range .items[*]}{.metadata.namespace}{\"`t\"}{.metadata.name}{\"`n\"}{end}'"
        ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

        if ($maliciousCandidates.Count -eq 0) {
            throw "No running pod with label raasa.class=malicious was found. Reapply the phase-0 test pods or start a malicious workload before collecting live validation."
        }

        $firstCandidate = [string]$maliciousCandidates[0]
        $candidateParts = $firstCandidate -split "`t", 2
        if ($candidateParts.Count -ne 2) {
            throw "Could not parse malicious pod candidate row: $firstCandidate"
        }

        $maliciousNamespace = $candidateParts[0].Trim()
        $maliciousPod = $candidateParts[1].Trim()
    }

    $maliciousNode = (Invoke-SSH "sudo k3s kubectl get pod -n $maliciousNamespace $maliciousPod -o jsonpath='{.spec.nodeName}'").Trim()
    $agentPod = (Invoke-SSH "sudo k3s kubectl get pods -n raasa-system -l app=raasa-agent --field-selector spec.nodeName=$maliciousNode -o jsonpath='{.items[0].metadata.name}'").Trim()
    $maliciousUid = (Invoke-SSH "sudo k3s kubectl get pod -n $maliciousNamespace $maliciousPod -o jsonpath='{.metadata.uid}'").Trim()

    @(
        "Host=$TargetHost",
        "User=$User",
        "CollectedAtLocal=" + (Get-Date).ToString("o"),
        "AgentPod=$agentPod",
        "MaliciousNamespace=$maliciousNamespace",
        "MaliciousPod=$maliciousPod",
        "MaliciousNode=$maliciousNode",
        "MaliciousUid=$maliciousUid"
    ) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

    Invoke-SSH "date -u '+%Y-%m-%dT%H:%M:%SZ' && hostname && whoami && uname -a" |
        Set-Content -Path (Join-Path $OutputDir "host_identity.txt")

    Invoke-SSH "sudo k3s kubectl get pods -A -o wide" |
        Set-Content -Path (Join-Path $OutputDir "kubectl_get_pods_all_wide.txt")

    Invoke-SSH "sudo k3s kubectl get pods -A -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,UID:.metadata.uid'" |
        Set-Content -Path (Join-Path $OutputDir "kubectl_pod_uid_map.txt")

    Invoke-SSH "sudo k3s kubectl logs -n raasa-system -l app=raasa-agent --all-containers=true --tail=200" |
        Set-Content -Path (Join-Path $OutputDir "raasa_agent_all_containers_tail_200.txt")

    Invoke-SSH "sudo k3s kubectl logs -n kube-system deploy/metrics-server --tail=200" |
        Set-Content -Path (Join-Path $OutputDir "metrics_server_tail_200.txt")

    Invoke-SSH "sudo journalctl -u k3s -n 200 --no-pager" |
        Set-Content -Path (Join-Path $OutputDir "journalctl_k3s_tail_200.txt")

    Invoke-SSH "sudo k3s kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/$maliciousNamespace/pods/$maliciousPod" |
        Set-Content -Path (Join-Path $OutputDir "metrics_api_malicious_pod.json")

    Invoke-SSH "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-agent -- find /var/run/raasa -maxdepth 2 -type f | sort | sed -n '1,120p'" |
        Set-Content -Path (Join-Path $OutputDir "probe_volume_listing.txt")

    Invoke-SSH "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-agent -- cat /var/run/raasa/$maliciousUid/.cpu_usec" |
        Set-Content -Path (Join-Path $OutputDir "malicious_pod_cpu_usec.txt")

    Invoke-SSH "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-agent -- cat /var/run/raasa/$maliciousUid/syscall_rate" |
        Set-Content -Path (Join-Path $OutputDir "malicious_pod_syscall_rate.txt")

    Invoke-SSH "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-agent -- cat /var/run/raasa/$maliciousUid/.switches_current" |
        Set-Content -Path (Join-Path $OutputDir "malicious_pod_switches_current.txt")

    Invoke-SSH "sudo k3s kubectl exec -n raasa-system $agentPod -c raasa-agent -- cat /var/run/raasa/$maliciousUid/.pid_count" |
        Set-Content -Path (Join-Path $OutputDir "malicious_pod_pid_count.txt")

    Write-Host "Evidence collected in: $OutputDir"
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
