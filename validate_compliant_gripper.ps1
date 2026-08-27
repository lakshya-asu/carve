$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python launcher was not found at $isaacPython"
}

$env:OMNI_KIT_ACCEPT_EULA = "YES"
& $isaacPython "$projectRoot\isaac_sim\run_scene2.py" --headless --output-root results/scene2_compliance
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
$result = Get-Content "$projectRoot\results\scene2_compliance\scene2_validation.json" -Raw | ConvertFrom-Json
if (-not $result.passed -or -not $result.compliant_gripper.passed) {
    throw "The Scene 2.0 compliant gripper metrics reported failure"
}
