$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacRoot = "C:\Users\jainl\is6"
$isaacPython = Join-Path $isaacRoot "Scripts\python.exe"
$weights = Join-Path $projectRoot "models\yolo26_meat_reference\weights\best.pt"
if (-not (Test-Path -LiteralPath $weights)) {
    throw "Trained YOLO checkpoint is missing. Run setup_yolo.ps1 and train_yolo.ps1 first."
}
$existing = @(Get-Process | Where-Object {
    try {
        $_.Path -and $_.Path.StartsWith($isaacRoot, [System.StringComparison]::OrdinalIgnoreCase)
    }
    catch {
        $false
    }
})
if ($existing.Count -ne 0) {
    $ids = ($existing | Select-Object -ExpandProperty Id) -join ", "
    throw "YOLO tests require a clean Isaac process state. Existing process IDs: $ids"
}
$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:PYTHONPATH = Join-Path $projectRoot "third_party\python"
$env:YOLO_CONFIG_DIR = Join-Path $projectRoot "results\yolo\config"
Push-Location -LiteralPath $projectRoot
try {
    & $isaacPython tools\train_yolo26.py --dataset results\yolo\dataset_v2\dataset.yaml --epochs 30 --seed 2601 --validate-only
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $training = Get-Content results\yolo\training_summary.json -Raw | ConvertFrom-Json
    if (-not $training.passed) { throw "YOLO validation reported failure" }
    & $isaacPython isaac_sim\run_cell.py --solution a --cycles 4 --seed 2601 --vision-model yolo26 --yolo-weights models\yolo26_meat_reference\weights\best.pt --output-root results\yolo\test_suite_a --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $metricsA = Get-Content results\yolo\test_suite_a\isaac_a\metrics.json -Raw | ConvertFrom-Json
    if (-not $metricsA.passed) { throw "YOLO Solution A metrics reported failure" }
    & $isaacPython isaac_sim\run_cell.py --solution b --cycles 4 --seed 2601 --vision-model yolo26 --yolo-weights models\yolo26_meat_reference\weights\best.pt --output-root results\yolo\test_suite_b --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $metricsB = Get-Content results\yolo\test_suite_b\isaac_b\metrics.json -Raw | ConvertFrom-Json
    if (-not $metricsB.passed) { throw "YOLO Solution B metrics reported failure" }
}
finally {
    Pop-Location
}
