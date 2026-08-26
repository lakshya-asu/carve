$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$unitPython = (Get-Command python -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
$env:OMNI_KIT_ACCEPT_EULA = "YES"
Push-Location -LiteralPath $projectRoot
try {
    & $unitPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $isaacPython isaac_sim\validate_setup.py --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $setupResult = Get-Content results\setup_validation.json -Raw | ConvertFrom-Json
    if (-not $setupResult.passed) { throw "Setup validation metrics reported failure" }
    & $isaacPython isaac_sim\run_cell.py --solution a --cycles 4 --seed 7 --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $metricsA = Get-Content results\isaac_a\metrics.json -Raw | ConvertFrom-Json
    if (-not $metricsA.passed) { throw "Solution A metrics reported failure" }
    & $isaacPython isaac_sim\run_cell.py --solution b --cycles 4 --seed 7 --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $metricsB = Get-Content results\isaac_b\metrics.json -Raw | ConvertFrom-Json
    if (-not $metricsB.passed) { throw "Solution B metrics reported failure" }
    & $isaacPython tools\audit_artifacts.py --root results --mode baseline --output results\artifact_audit.json
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
