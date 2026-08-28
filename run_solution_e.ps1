param(
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/solution_e/comparison/$runId"
}

Push-Location -LiteralPath $projectRoot
try {
    & .\run_solution_e_training.ps1 -OutputRoot "$OutputRoot\training"
    & .\run_solution_a.ps1 -Seed 5811 -Scenario nominal -StartYawDeg 20 -ContactSkillMode shadow -OutputRoot "$OutputRoot\a_shadow"
    & .\run_solution_a.ps1 -Seed 5811 -Scenario nominal -StartYawDeg 20 -ContactSkillMode shadow -OutputRoot "$OutputRoot\a_shadow_replay"
    & .\run_solution_b.ps1 -Seed 5812 -Scenario nominal -StartYawDeg -18 -ContactSkillMode shadow -OutputRoot "$OutputRoot\b_shadow"
    & .\run_solution_b.ps1 -Seed 5813 -Scenario slip_correction -StartYawDeg -18 -ContactSkillMode shadow -OutputRoot "$OutputRoot\b_slip_shadow"
    & .\run_solution_a.ps1 -Seed 5814 -Scenario emergency_stop -StartYawDeg 15 -ContactSkillMode shadow -OutputRoot "$OutputRoot\a_emergency_shadow"
    python tools\summarize_solution_e.py $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "Solution E shadow comparison gate failed" }
    Write-Output "Solution E shadow evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
}
finally {
    Get-CimInstance Win32_Process | Where-Object {
        ($_.ExecutablePath -like "C:\Users\jainl\is6*" -and $_.Name -in @("kit.exe", "isaac-sim.exe")) -or
        ($_.Name -eq "python.exe" -and $_.CommandLine -match "isaac_sim[\\/]")
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Pop-Location
}
