$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$unitPython = (Get-Command python -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
$env:OMNI_KIT_ACCEPT_EULA = "YES"
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
    & $isaacPython isaac_sim\run_cell.py --solution a --cycles 4 --seed 7 --headless --output-root $fullRunRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $failureA = Join-Path $fullRunPath "isaac_a\failure.json"
    if (Test-Path -LiteralPath $failureA) { throw "Solution A wrote a simulator failure file at $failureA" }
    $metricsAPath = Join-Path $fullRunPath "isaac_a\metrics.json"
    if (-not (Test-Path -LiteralPath $metricsAPath)) { throw "Solution A did not write fresh metrics" }
    $metricsA = Get-Content $metricsAPath -Raw | ConvertFrom-Json
    if (-not $metricsA.passed) { throw "Solution A metrics reported failure" }
    & $isaacPython isaac_sim\run_cell.py --solution b --cycles 4 --seed 7 --headless --output-root $fullRunRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $failureB = Join-Path $fullRunPath "isaac_b\failure.json"
    if (Test-Path -LiteralPath $failureB) { throw "Solution B wrote a simulator failure file at $failureB" }
    $metricsBPath = Join-Path $fullRunPath "isaac_b\metrics.json"
    if (-not (Test-Path -LiteralPath $metricsBPath)) { throw "Solution B did not write fresh metrics" }
    $metricsB = Get-Content $metricsBPath -Raw | ConvertFrom-Json
    if (-not $metricsB.passed) { throw "Solution B metrics reported failure" }
    & $isaacPython tools\audit_artifacts.py --root $fullRunRoot --mode baseline --output "$fullRunRoot/artifact_audit.json"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
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
    Write-Output "Complete suite evidence: $fullRunPath"
}
finally {
    Pop-Location
}
