param(
    [int]$Seed = 2601,
    [ValidateSet("nominal", "failed_grasp", "cutter_unavailable", "buffer_timeout", "slip_correction", "emergency_stop", "stale_observation")]
    [string]$Scenario = "nominal",
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$auditPython = (Get-Command python -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/scene2_runs/solution_b_${Scenario}_seed${Seed}_$runId"
}

$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:PYTHONPATH = "C:\Users\jainl\is6\Lib\site-packages"
Push-Location -LiteralPath $projectRoot
try {
    & $isaacPython isaac_sim\run_scene2_integrated.py --solution b --seed $Seed --scenario $Scenario --output-root $OutputRoot --fps 12
    if ($LASTEXITCODE -ne 0) { throw "Isaac Sim process failed with exit code $LASTEXITCODE" }
    $metricsPath = Join-Path $OutputRoot "scene2_integrated_metrics.json"
    if (-not (Test-Path -LiteralPath $metricsPath)) { throw "Integrated metrics were not written" }
    $metrics = Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
    if (-not $metrics.passed) { throw "Solution B metrics reported failure: $($metrics.error)" }
    if ($Scenario -in @("nominal", "slip_correction")) {
        & $auditPython tools\audit_scene2_integrated.py $metricsPath --solution b --output (Join-Path $OutputRoot "integrated_audit.json")
        if ($LASTEXITCODE -ne 0) { throw "Solution B artifact audit failed" }
    }
    Write-Output "Solution B evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
}
finally {
    Get-Process -Name "kit", "isaac-sim" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "C:\Users\jainl\is6*" } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Pop-Location
}
