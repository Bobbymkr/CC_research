param(
    [string]$ClusterName = "",

    [string]$KubeconfigPath = $env:RAASA_EKS_KUBECONFIG,

    [string]$Context = $env:RAASA_EKS_CONTEXT,

    [string]$OutputDir = (Join-Path (Get-Location) ("AWS_Results_26_april\eks_live_validation_" + (Get-Date -Format "yyyy_MM_dd_HHmmss")))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,

        [Parameter(Mandatory = $true)]
        [string]$ErrorContext,

        [int]$TimeoutSeconds = 300,

        [int[]]$AllowExitCodes = @(0)
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
            throw "$ErrorContext timed out after $TimeoutSeconds seconds."
        }

        $process.WaitForExit()
        $process.Refresh()
        $exitCode = [int]$process.ExitCode

        $output = @()
        if (Test-Path -LiteralPath $stdoutPath) { $output += Get-Content -LiteralPath $stdoutPath }
        if (Test-Path -LiteralPath $stderrPath) { $output += Get-Content -LiteralPath $stderrPath }

        if ($exitCode -notin $AllowExitCodes) {
            $joined = ($output -join [Environment]::NewLine).Trim()
            if ($joined) {
                throw "$ErrorContext failed with exit code $exitCode.`n$joined"
            }
            throw "$ErrorContext failed with exit code $exitCode."
        }

        return [pscustomobject]@{
            ExitCode = $exitCode
            Output = @($output)
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Get-KubectlBaseArgs {
    $args = @()
    if (-not [string]::IsNullOrWhiteSpace($KubeconfigPath)) {
        $args += @("--kubeconfig", $KubeconfigPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($Context)) {
        $args += @("--context", $Context)
    }
    return $args
}

function Invoke-KubectlCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$KubectlArgs,

        [Parameter(Mandatory = $true)]
        [string]$ErrorContext,

        [int]$TimeoutSeconds = 300,

        [int[]]$AllowExitCodes = @(0)
    )

    return Invoke-NativeCapture `
        -FilePath "kubectl" `
        -ArgumentList ((Get-KubectlBaseArgs) + $KubectlArgs) `
        -ErrorContext $ErrorContext `
        -TimeoutSeconds $TimeoutSeconds `
        -AllowExitCodes $AllowExitCodes
}

function Save-KubectlOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$KubectlArgs,

        [Parameter(Mandatory = $true)]
        [string]$FileName,

        [int]$TimeoutSeconds = 180,

        [int[]]$AllowExitCodes = @(0)
    )

    $result = Invoke-KubectlCapture -KubectlArgs $KubectlArgs -ErrorContext ("kubectl " + ($KubectlArgs -join " ")) -TimeoutSeconds $TimeoutSeconds -AllowExitCodes $AllowExitCodes
    $result.Output | Set-Content -Path (Join-Path $OutputDir $FileName)
}

function Get-KubectlString {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$KubectlArgs,

        [int]$TimeoutSeconds = 120
    )

    return ((Invoke-KubectlCapture -KubectlArgs $KubectlArgs -ErrorContext ("kubectl " + ($KubectlArgs -join " ")) -TimeoutSeconds $TimeoutSeconds).Output -join "").Trim()
}

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw "kubectl was not found on PATH."
}
if (-not [string]::IsNullOrWhiteSpace($KubeconfigPath) -and -not (Test-Path -LiteralPath $KubeconfigPath)) {
    throw "Kubeconfig path not found: $KubeconfigPath"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$currentContext = Get-KubectlString -KubectlArgs @("config", "current-context")
if ([string]::IsNullOrWhiteSpace($currentContext)) {
    throw "Could not resolve the current kubectl context."
}
if ([string]::IsNullOrWhiteSpace($ClusterName)) {
    $ClusterName = $currentContext
}

$agentPod = Get-KubectlString -KubectlArgs @("get", "pods", "-n", "raasa-system", "-l", "app=raasa-agent", "-o", "jsonpath={.items[0].metadata.name}")
$maliciousPod = Get-KubectlString -KubectlArgs @("get", "pods", "-n", "default", "-l", "raasa.class=malicious", "-o", "jsonpath={.items[0].metadata.name}")
$maliciousUid = if ($maliciousPod) {
    Get-KubectlString -KubectlArgs @("get", "pod", "-n", "default", $maliciousPod, "-o", "jsonpath={.metadata.uid}")
}
else {
    ""
}

if ([string]::IsNullOrWhiteSpace($agentPod)) {
    throw "Could not resolve the RAASA agent pod in raasa-system."
}
if ([string]::IsNullOrWhiteSpace($maliciousPod) -or [string]::IsNullOrWhiteSpace($maliciousUid)) {
    throw "Could not resolve the default malicious phase-0 pod and UID."
}

@(
    "ClusterName=$ClusterName",
    "Context=$currentContext",
    "KubeconfigPath=$(if ([string]::IsNullOrWhiteSpace($KubeconfigPath)) { '<current kubectl default>' } else { $KubeconfigPath })",
    "CollectedAtLocal=" + (Get-Date).ToString("o"),
    "AgentPod=$agentPod",
    "MaliciousPod=$maliciousPod",
    "MaliciousUid=$maliciousUid"
) | Set-Content -Path (Join-Path $OutputDir "collection_metadata.txt")

Save-KubectlOutput -KubectlArgs @("version") -FileName "kubectl_version.txt" -TimeoutSeconds 120
Save-KubectlOutput -KubectlArgs @("cluster-info") -FileName "cluster_info.txt" -TimeoutSeconds 120
Save-KubectlOutput -KubectlArgs @("get", "nodes", "-o", "wide") -FileName "kubectl_get_nodes_wide.txt" -TimeoutSeconds 120
Save-KubectlOutput -KubectlArgs @("get", "pods", "-A", "-o", "wide") -FileName "kubectl_get_pods_all_wide.txt" -TimeoutSeconds 120
Save-KubectlOutput -KubectlArgs @("get", "pods", "-A", "-o", "custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,UID:.metadata.uid,NODE:.spec.nodeName") -FileName "kubectl_pod_uid_map.txt" -TimeoutSeconds 120
Save-KubectlOutput -KubectlArgs @("get", "daemonset", "raasa-agent", "-n", "raasa-system", "-o", "wide") -FileName "daemonset_status.txt" -TimeoutSeconds 120
Save-KubectlOutput -KubectlArgs @("get", "pods", "-n", "raasa-system", "-l", "app=raasa-agent", "-o", "wide") -FileName "raasa_agent_pods_wide.txt" -TimeoutSeconds 120
Save-KubectlOutput -KubectlArgs @("logs", "-n", "raasa-system", "-l", "app=raasa-agent", "--all-containers=true", "--tail=200") -FileName "raasa_agent_all_containers_tail_200.txt" -TimeoutSeconds 180 -AllowExitCodes @(0, 1)
Save-KubectlOutput -KubectlArgs @("logs", "-n", "kube-system", "deploy/metrics-server", "--tail=200") -FileName "metrics_server_tail_200.txt" -TimeoutSeconds 180 -AllowExitCodes @(0, 1)
Save-KubectlOutput -KubectlArgs @("get", "--raw", "/apis/metrics.k8s.io/v1beta1/namespaces/default/pods/$maliciousPod") -FileName "metrics_api_malicious_pod.json" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
Save-KubectlOutput -KubectlArgs @("exec", "-n", "raasa-system", $agentPod, "-c", "raasa-agent", "--", "sh", "-c", "find /var/run/raasa -maxdepth 2 -type f | sort | sed -n '1,120p'") -FileName "probe_volume_listing.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
Save-KubectlOutput -KubectlArgs @("exec", "-n", "raasa-system", $agentPod, "-c", "raasa-agent", "--", "cat", "/var/run/raasa/$maliciousUid/.cpu_usec") -FileName "malicious_pod_cpu_usec.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
Save-KubectlOutput -KubectlArgs @("exec", "-n", "raasa-system", $agentPod, "-c", "raasa-agent", "--", "cat", "/var/run/raasa/$maliciousUid/syscall_rate") -FileName "malicious_pod_syscall_rate.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
Save-KubectlOutput -KubectlArgs @("exec", "-n", "raasa-system", $agentPod, "-c", "raasa-agent", "--", "cat", "/var/run/raasa/$maliciousUid/.switches_current") -FileName "malicious_pod_switches_current.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)
Save-KubectlOutput -KubectlArgs @("exec", "-n", "raasa-system", $agentPod, "-c", "raasa-agent", "--", "cat", "/var/run/raasa/$maliciousUid/.pid_count") -FileName "malicious_pod_pid_count.txt" -TimeoutSeconds 120 -AllowExitCodes @(0, 1)

Write-Host "EKS live validation evidence collected in: $OutputDir"
