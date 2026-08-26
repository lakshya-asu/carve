$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacRoot = "C:\Users\jainl\is6"
$isaacPython = Join-Path $isaacRoot "Scripts\python.exe"
$weights = Join-Path $projectRoot "models\yolo26_meat_reference\weights\best.pt"
if (-not (Test-Path -LiteralPath $weights)) {
    throw "Trained YOLO checkpoint is missing. Run setup_yolo.ps1 and train_yolo.ps1 first."
}
$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:PYTHONPATH = Join-Path $projectRoot "third_party\python"
$env:YOLO_CONFIG_DIR = Join-Path $projectRoot "results\yolo\config"
Push-Location -LiteralPath $projectRoot
try {
    & $isaacPython isaac_sim\run_cell.py `
        --solution a `
        --cycles 4 `
        --seed 2601 `
        --vision-model yolo26 `
        --yolo-weights models\yolo26_meat_reference\weights\best.pt `
        --output-root results\yolo\solution_a `
        --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $metrics = Get-Content results\yolo\solution_a\isaac_a\metrics.json -Raw | ConvertFrom-Json
    if (-not $metrics.passed) { throw "YOLO Solution A metrics reported failure" }
}
finally {
    Pop-Location
}
