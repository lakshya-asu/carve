param(
    [int]$Seed = 2601,
    [ValidateSet("nominal", "failed_grasp", "cutter_unavailable", "emergency_stop", "stale_observation")]
    [string]$Scenario = "nominal",
    [ValidateRange(0.04, 0.30)]
    [double]$BeltSpeedMps = 0.10,
    [ValidateRange(-0.09, 0.09)]
    [double]$StartYM = 0.0,
    [ValidateRange(-85.0, 85.0)]
    [double]$StartYawDeg = 0.0,
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
    $OutputRoot = "results/scene2_runs/solution_a_${Scenario}_seed${Seed}_$runId"
}

$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:PYTHONPATH = "C:\Users\jainl\is6\Lib\site-packages"
Push-Location -LiteralPath $projectRoot
try {
    & $isaacPython isaac_sim\run_scene2_integrated.py --solution a --seed $Seed --scenario $Scenario --belt-speed-mps $BeltSpeedMps --start-y-m $StartYM --start-yaw-deg $StartYawDeg --output-root $OutputRoot --fps 12
    if ($LASTEXITCODE -ne 0) { throw "Isaac Sim process failed with exit code $LASTEXITCODE" }
    $metricsPath = Join-Path $OutputRoot "scene2_integrated_metrics.json"
    if (-not (Test-Path -LiteralPath $metricsPath)) { throw "Integrated metrics were not written" }
    $metrics = Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
    if (-not $metrics.passed) { throw "Solution A metrics reported failure: $($metrics.error)" }
    if ($Scenario -eq "nominal") {
        & $auditPython tools\audit_scene2_integrated.py $metricsPath --solution a --output (Join-Path $OutputRoot "integrated_audit.json")
        if ($LASTEXITCODE -ne 0) { throw "Solution A artifact audit failed" }
    }
    Write-Output "Solution A evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
}
finally {
    Get-Process -Name "kit", "isaac-sim" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "C:\Users\jainl\is6*" } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Pop-Location
}
