$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
$env:OMNI_KIT_ACCEPT_EULA = "YES"
Push-Location -LiteralPath $projectRoot
try {
    & $isaacPython isaac_sim\validate_setup.py --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $result = Get-Content results\setup_validation.json -Raw | ConvertFrom-Json
    if (-not $result.passed) { throw "Setup validation metrics reported failure" }
}
finally {
    Pop-Location
}
