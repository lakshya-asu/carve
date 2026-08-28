param(
    [int]$Seed = 2601,
    [ValidateSet("nominal", "failed_grasp", "cutter_unavailable", "buffer_timeout", "slip_correction", "emergency_stop", "stale_observation")]
    [string]$Scenario = "nominal",
    [ValidateRange(0.04, 0.30)]
    [double]$BeltSpeedMps = 0.10,
    [ValidateRange(-0.09, 0.09)]
    [double]$StartYM = 0.0,
    [ValidateRange(-85.0, 85.0)]
    [double]$StartYawDeg = 0.0,
    [ValidateRange(0.0, 150.0)]
    [double]$PerceptionLatencyMs = 30.0,
    [ValidateRange(0.0, 10.0)]
    [double]$PositionNoiseMm = 1.0,
    [ValidateRange(0.0, 8.0)]
    [double]$YawNoiseDeg = 0.35,
    [ValidateSet("geometric", "learned")]
    [string]$GraspSelector = "geometric",
    [string]$GraspModel = "models/grasp_affordance_v2_matched/model.json",
    [ValidateRange(0.0, 1.0)]
    [double]$GraspScoreMinMargin = 0.0,
    [ValidateRange(-1, 4)]
    [int]$GraspCandidateIndex = -1,
    [ValidateSet("off", "shadow")]
    [string]$ContactSkillMode = "off",
    [string]$ContactSkillModel = "models/contact_skill_v1/model.json",
    [ValidateSet("predict_once", "reactive")]
    [string]$InterceptionController = "predict_once",
    [ValidateSet("none", "belt_ramp", "encoder_bias", "latency_spike", "pose_disturbance")]
    [string]$InterceptionPerturbation = "none",
    [string]$OutputRoot = "",
    [switch]$AllowExpectedFailure
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$auditPython = (Get-Command python -ErrorAction Stop).Source
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
    throw "Solution B requires a clean Isaac state; found $($existingIsaac.Count) existing Isaac process(es)."
}
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/scene2_runs/solution_b_${Scenario}_seed${Seed}_$runId"
}

$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:PYTHONPATH = "C:\Users\jainl\is6\Lib\site-packages"
Push-Location -LiteralPath $projectRoot
try {
    $candidateArgs = @()
    if ($GraspCandidateIndex -ge 0) {
        $candidateArgs = @("--grasp-candidate-index", "$GraspCandidateIndex")
    }
    & $isaacPython isaac_sim\run_scene2_integrated.py --solution b --seed $Seed --scenario $Scenario --belt-speed-mps $BeltSpeedMps --start-y-m $StartYM --start-yaw-deg $StartYawDeg --perception-latency-ms $PerceptionLatencyMs --position-noise-mm $PositionNoiseMm --yaw-noise-deg $YawNoiseDeg --grasp-selector $GraspSelector --grasp-model $GraspModel --grasp-score-min-margin $GraspScoreMinMargin @candidateArgs --contact-skill-mode $ContactSkillMode --contact-skill-model $ContactSkillModel --interception-controller $InterceptionController --interception-perturbation $InterceptionPerturbation --output-root $OutputRoot --fps 12
    if ($LASTEXITCODE -ne 0 -and -not $AllowExpectedFailure) { throw "Isaac Sim process failed with exit code $LASTEXITCODE" }
    $metricsPath = Join-Path $OutputRoot "scene2_integrated_metrics.json"
    if (-not (Test-Path -LiteralPath $metricsPath)) { throw "Integrated metrics were not written" }
    $metrics = Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
    if (-not $metrics.passed -and -not $AllowExpectedFailure) { throw "Solution B metrics reported failure: $($metrics.error)" }
    if ($Scenario -in @("nominal", "slip_correction") -and $metrics.passed) {
        & $auditPython tools\audit_scene2_integrated.py $metricsPath --solution b --output (Join-Path $OutputRoot "integrated_audit.json")
        if ($LASTEXITCODE -ne 0) { throw "Solution B artifact audit failed" }
    }
    Write-Output "Solution B evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
}
finally {
    Get-CimInstance Win32_Process | Where-Object {
        ($_.ExecutablePath -like "C:\Users\jainl\is6*" -and $_.Name -in @("kit.exe", "isaac-sim.exe")) -or
        ($_.Name -eq "python.exe" -and $_.CommandLine -match "isaac_sim[\\/]")
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Pop-Location
}
