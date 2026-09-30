[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$PipelineArgs)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$wsRoot = Split-Path -Parent $scriptDir

try {
    # Prerequisite: framework submodule must be initialized.
    if (-not (Test-Path -LiteralPath (Join-Path $wsRoot 'agentic-pipelines\AGENTS.md'))) {
        Write-Host 'bootstrap: running git submodule update --init --recursive'
        Push-Location $wsRoot
        try { & git submodule update --init --recursive } finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) { throw "git submodule update exited with $LASTEXITCODE" }
    }

    # Prerequisite: declared pipeline dependencies must be present in the
    # ignored host-local directory (never system Python).
    $frameworkBootstrap = Join-Path $wsRoot 'agentic-pipelines\scripts\bootstrap_pipeline_environment.py'
    Write-Host 'bootstrap: checking declared pipeline dependencies (host-local, ignored dir)'
    & python $frameworkBootstrap --host-root $wsRoot --requirements requirements-pipeline.txt --requirements agentic-pipelines/requirements.txt --check-module yaml --check-module pypdf
    if ($LASTEXITCODE -ne 0) { throw "bootstrap_pipeline_environment.py exited with $LASTEXITCODE" }

    # Preflight is required only when an LLM stage will invoke local inference.
    # The pipeline is currently deterministic-only, so preflight runs only when
    # an operator-created api.yaml exists; deterministic commands never require
    # API configuration.
    $apiYaml = Join-Path $wsRoot 'api.yaml'
    if (Test-Path -LiteralPath $apiYaml) {
        Write-Host 'bootstrap: api.yaml present; running pipeline preflight'
        & python 'agentic-pipelines\scripts\pipeline.py' preflight --api-config api.yaml --pipeline 'pipeline.yaml'
        if ($LASTEXITCODE -ne 0) { throw "pipeline preflight exited with $LASTEXITCODE" }
    } else {
        Write-Host 'bootstrap: no api.yaml (deterministic-only pipeline); skipping preflight'
    }

    # Delegate to the host main entrypoint exactly once, preserving its exit status.
    Write-Host 'bootstrap: prerequisites ready; starting host pipeline'
    & python (Join-Path $scriptDir 'pareto_pipeline.py') @PipelineArgs
    exit $LASTEXITCODE
}
catch [System.Management.Automation.PipelineStoppedException] {
    Write-Error 'bootstrap: interrupted'
    exit 130
}
catch {
    Write-Error "bootstrap: $($_.Exception.Message)"
    exit 1
}