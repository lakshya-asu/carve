$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python launcher was not found at $isaacPython"
}

$env:OMNI_KIT_ACCEPT_EULA = "YES"
& $isaacPython "$projectRoot\isaac_sim\run_scene2.py" --no-headless --keep-open-seconds 600 @args
exit $LASTEXITCODE
