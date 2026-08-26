$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
$env:OMNI_KIT_ACCEPT_EULA = "YES"
Push-Location -LiteralPath $projectRoot
try {
    & $isaacPython isaac_sim\run_cell.py --solution b --cycles 4 --seed 7 --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $metrics = Get-Content results\isaac_b\metrics.json -Raw | ConvertFrom-Json
    if (-not $metrics.passed) { throw "Solution B metrics reported failure" }
}
finally {
    Pop-Location
}
