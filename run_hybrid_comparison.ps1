param(
    [string]$OutputRoot = "",
    [ValidateSet("a", "b")]
    [string[]]$Flows = @("a", "b"),
    [ValidateSet("S0", "S1", "S2", "S3", "S4")]
    [string[]]$Stacks = @("S0", "S1", "S2", "S3"),
    [int]$Seed = 4801,
    [ValidateSet("none", "belt_ramp", "encoder_bias", "latency_spike", "pose_disturbance")]
    [string]$Perturbation = "pose_disturbance",
    [ValidateRange(0.04, 0.30)]
    [double]$BeltSpeedMps = 0.16,
    [ValidateRange(-0.09, 0.09)]
    [double]$StartYM = 0.02,
    [ValidateRange(-85.0, 85.0)]
    [double]$StartYawDeg = 35.0,
    [switch]$PlanOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/hybrid_comparison/$runId"
}
$existing = @(Get-CimInstance Win32_Process | Where-Object {
    ($_.ExecutablePath -like "C:\Users\jainl\is6*" -and $_.Name -in @("kit.exe", "isaac-sim.exe")) -or
    ($_.Name -eq "python.exe" -and $_.CommandLine -match "isaac_sim[\\/]") -or
    ($_.ProcessId -ne $PID -and $_.Name -in @("pwsh.exe", "powershell.exe") -and
        $_.CommandLine -match "run_(solution_[abcde]|hybrid_comparison|tests|hardening|accuracy_matrix|speed_pose_matrix)\.ps1")
})
if ($existing.Count -gt 0) { throw "Hybrid comparison requires a clean Isaac process state" }

Push-Location -LiteralPath $projectRoot
try {
    python tools\create_hybrid_manifest.py $OutputRoot --flows $Flows --stacks $Stacks --seed $Seed --perturbation $Perturbation --belt-speed-mps $BeltSpeedMps --start-y-m $StartYM --start-yaw-deg $StartYawDeg
    if ($LASTEXITCODE -ne 0) { throw "Hybrid experiment manifest creation failed" }
    if ($PlanOnly) {
        Write-Output "Hybrid experiment plan: $(Resolve-Path -LiteralPath (Join-Path $OutputRoot 'experiment_manifest.json'))"
        return
    }
    $manifest = Get-Content -LiteralPath (Join-Path $OutputRoot "experiment_manifest.json") -Raw | ConvertFrom-Json
    foreach ($case in $manifest.cases) {
        if (-not $case.required_for_gate) { continue }
        $launcher = if ($case.flow -eq "a") { ".\run_solution_a.ps1" } else { ".\run_solution_b.ps1" }
        $caseRoot = Join-Path $OutputRoot $case.result_directory
        & $launcher `
            -Seed $case.seed `
            -Scenario nominal `
            -BeltSpeedMps $case.belt_speed_mps `
            -StartYM $case.start_y_m `
            -StartYawDeg $case.start_yaw_deg `
            -GraspSelector $case.grasp_selector `
            -GraspModel models/grasp_affordance_v2_matched/model.json `
            -InterceptionController $case.interception_controller `
            -InterceptionPerturbation $case.interception_perturbation `
            -OutputRoot $caseRoot `
            -AllowExpectedFailure
    }
    python tools\summarize_hybrid_comparison.py $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "Hybrid comparison gate failed" }
    Write-Output "Hybrid comparison evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
}
finally {
    Get-CimInstance Win32_Process | Where-Object {
        ($_.ExecutablePath -like "C:\Users\jainl\is6*" -and $_.Name -in @("kit.exe", "isaac-sim.exe")) -or
        ($_.Name -eq "python.exe" -and $_.CommandLine -match "isaac_sim[\\/]")
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Pop-Location
}
