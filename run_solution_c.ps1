param(
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/solution_c/comparison/$runId"
}
$model = Join-Path $projectRoot "models\grasp_affordance_v2_matched\model.json"
if (-not (Test-Path -LiteralPath $model)) {
    & "$projectRoot\run_solution_c_training.ps1"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$existing = @(Get-CimInstance Win32_Process | Where-Object {
    ($_.ExecutablePath -like "C:\Users\jainl\is6*" -and $_.Name -in @("kit.exe", "isaac-sim.exe")) -or
    ($_.Name -eq "python.exe" -and $_.CommandLine -match "isaac_sim[\\/]") -or
    ($_.ProcessId -ne $PID -and $_.Name -in @("pwsh.exe", "powershell.exe") -and
        $_.CommandLine -match "run_(solution_[abcde]|hybrid_comparison|tests|hardening|accuracy_matrix|speed_pose_matrix)\.ps1")
})
if ($existing.Count -gt 0) { throw "Solution C requires a clean Isaac process state" }

Push-Location -LiteralPath $projectRoot
try {
    & "$projectRoot\run_solution_a.ps1" -Seed 4501 -Scenario nominal -BeltSpeedMps 0.14 -StartYM -0.03 -StartYawDeg 32 -OutputRoot "$OutputRoot/baseline_a"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & "$projectRoot\run_solution_c_a.ps1" -Seed 4501 -OutputRoot "$OutputRoot/learned_a"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & "$projectRoot\run_solution_c_a.ps1" -Seed 4501 -OutputRoot "$OutputRoot/learned_a_replay"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & "$projectRoot\run_solution_b.ps1" -Seed 4502 -Scenario nominal -BeltSpeedMps 0.16 -StartYM 0.03 -StartYawDeg 28 -OutputRoot "$OutputRoot/baseline_b"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & "$projectRoot\run_solution_c_b.ps1" -Seed 4502 -OutputRoot "$OutputRoot/learned_b"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & "$projectRoot\run_solution_c_b.ps1" -Seed 4502 -OutputRoot "$OutputRoot/learned_b_replay"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python tools\summarize_solution_c.py $OutputRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output "Solution C comparison evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
}
finally {
    Get-CimInstance Win32_Process | Where-Object {
        ($_.ExecutablePath -like "C:\Users\jainl\is6*" -and $_.Name -in @("kit.exe", "isaac-sim.exe")) -or
        ($_.Name -eq "python.exe" -and $_.CommandLine -match "isaac_sim[\\/]")
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Pop-Location
}
