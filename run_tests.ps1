$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$ordinaryPython = (Get-Command python -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
$existingIsaac = @(Get-CimInstance Win32_Process | Where-Object {
    ($_.ExecutablePath -like "C:\Users\jainl\is6*" -and $_.Name -in @("kit.exe", "isaac-sim.exe")) -or
    ($_.Name -eq "python.exe" -and $_.CommandLine -match "isaac_sim[\\/]") -or
    ($_.ProcessId -ne $PID -and $_.Name -in @("pwsh.exe", "powershell.exe") -and
        $_.CommandLine -match "run_(solution_[abcde]|hybrid_comparison|tests|hardening|accuracy_matrix|speed_pose_matrix)\.ps1")
})
if ($existingIsaac.Count -gt 0) {
    throw "The release gate requires a clean Isaac state; found $($existingIsaac.Count) existing Isaac process(es)."
}
$ordinarySitePackages = (& $ordinaryPython -c "import sysconfig; print(sysconfig.get_paths()['purelib'])").Trim()
$isaacSitePackages = "C:\Users\jainl\is6\Lib\site-packages"
$unitPython = $isaacPython
$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:PYTHONPATH = "$ordinarySitePackages;$isaacSitePackages"
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
    Get-CimInstance Win32_Process | Where-Object {
        ($_.ExecutablePath -like "C:\Users\jainl\is6*" -and $_.Name -in @("kit.exe", "isaac-sim.exe")) -or
        ($_.Name -eq "python.exe" -and $_.CommandLine -match "isaac_sim[\\/]")
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Pop-Location
}
