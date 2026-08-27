$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$unitPython = (Get-Command python -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:PYTHONPATH = "C:\Users\jainl\is6\Lib\site-packages"
$runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
$fullRunRoot = "results/full_suite/$runId"
$fullRunPath = Join-Path $projectRoot $fullRunRoot
Push-Location -LiteralPath $projectRoot
try {
    & $unitPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $isaacPython isaac_sim\validate_setup.py --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $setupResult = Get-Content results\setup_validation.json -Raw | ConvertFrom-Json
    if (-not $setupResult.passed) { throw "Setup validation metrics reported failure" }
    & "$projectRoot\validate_scene2_ros.ps1" --output-root "$fullRunRoot/scene2"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $scene2Failure = Join-Path $fullRunPath "scene2\scene2_failure.json"
    if (Test-Path -LiteralPath $scene2Failure) { throw "Scene 2.0 wrote a simulator failure file at $scene2Failure" }
    $scene2MetricsPath = Join-Path $fullRunPath "scene2\scene2_validation.json"
    if (-not (Test-Path -LiteralPath $scene2MetricsPath)) { throw "Scene 2.0 did not write fresh metrics" }
    $scene2Result = Get-Content $scene2MetricsPath -Raw | ConvertFrom-Json
    if (-not $scene2Result.passed) { throw "Scene 2.0 metrics reported failure" }
    if (-not $scene2Result.compliant_gripper.passed) { throw "Scene 2.0 compliant gripper metrics reported failure" }
    if (-not $scene2Result.ros2.passed) { throw "Scene 2.0 ROS metrics reported failure" }
    & "$projectRoot\run_solution_a.ps1" -Seed 2601 -Scenario nominal -OutputRoot "$fullRunRoot/integrated_solution_a"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & "$projectRoot\run_solution_b.ps1" -Seed 2601 -Scenario nominal -OutputRoot "$fullRunRoot/integrated_solution_b"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output "Complete suite evidence: $fullRunPath"
}
finally {
    Pop-Location
}
