$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$weights = Join-Path $projectRoot "models\yolo26_meat_reference\weights\best.pt"
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
if (-not (Test-Path -LiteralPath $weights)) {
    throw "Trained YOLO checkpoint is missing. Run setup_yolo.ps1 and train_yolo.ps1 first."
}
$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:PYTHONPATH = Join-Path $projectRoot "third_party\python"
$env:YOLO_CONFIG_DIR = Join-Path $projectRoot "results\yolo\config"
Push-Location -LiteralPath $projectRoot
try {
    & $isaacPython isaac_sim\run_cell.py `
        --solution b `
        --cycles 4 `
        --seed 2601 `
        --vision-model yolo26 `
        --yolo-weights models\yolo26_meat_reference\weights\best.pt `
        --output-root results\yolo\recorded_demo `
        --headless `
        --record-video `
        --record-fps 12
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $metrics = Get-Content results\yolo\recorded_demo\isaac_b\metrics.json -Raw | ConvertFrom-Json
    if (-not $metrics.passed) { throw "Recorded YOLO Isaac demo metrics reported failure" }
    if (-not (Test-Path -LiteralPath $metrics.recording.path)) { throw "Recorded demo video is missing" }
    Write-Host "Recorded demo: $($metrics.recording.path)"
}
finally {
    Pop-Location
}
