param(
    [string]$OutputRoot = "results/scene2_real_pickup",
    [int]$Fps = 12
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"

& $isaacPython "$projectRoot\isaac_sim\record_scene2_real_pickup_demo.py" `
    --output-root $OutputRoot `
    --fps $Fps
$pythonExitCode = $LASTEXITCODE
if ($pythonExitCode -ne 0) {
    exit $pythonExitCode
}

$metricsPath = Join-Path $projectRoot (Join-Path $OutputRoot "scene2_real_pickup_metrics.json")
if (-not (Test-Path -LiteralPath $metricsPath)) {
    Write-Host "Pickup gate failed: metrics file was not created."
    exit 1
}

$metrics = Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
if ($metrics.passed -ne $true) {
    Write-Host "Pickup gate failed. See $metricsPath"
    exit 1
}

Write-Host "Pickup gate passed. Evidence: $metricsPath"
exit 0
