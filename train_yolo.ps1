$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:PYTHONPATH = Join-Path $projectRoot "third_party\python"
$env:YOLO_CONFIG_DIR = Join-Path $projectRoot "results\yolo\config"
Push-Location -LiteralPath $projectRoot
try {
    & $isaacPython isaac_sim\generate_yolo_dataset.py --samples 240 --seed 2601 --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $datasetResult = Get-Content results\yolo\dataset_v2\dataset_metadata.json -Raw | ConvertFrom-Json
    if (-not $datasetResult.passed) { throw "Isaac YOLO dataset generation reported failure" }
    & $isaacPython tools\train_yolo26.py --epochs 30 --seed 2601
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
