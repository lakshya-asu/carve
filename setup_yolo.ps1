$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$vendorRoot = Join-Path $projectRoot "third_party\python"
$configRoot = Join-Path $projectRoot "results\yolo\config"
$modelRoot = Join-Path $projectRoot "models"
New-Item -ItemType Directory -Force -Path $vendorRoot, $configRoot, $modelRoot | Out-Null
& $isaacPython -m pip install `
    --target $vendorRoot `
    --no-deps `
    --no-cache-dir `
    ultralytics==8.4.129 `
    ultralytics-thop==2.1.6 `
    polars==1.44.1 `
    polars-runtime-32==1.44.1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$env:PYTHONPATH = $vendorRoot
$env:YOLO_CONFIG_DIR = $configRoot
Push-Location -LiteralPath $modelRoot
try {
    & $isaacPython -c "from ultralytics import YOLO; model=YOLO('yolo26n-seg.pt'); print(model.ckpt_path)"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
