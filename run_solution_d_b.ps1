param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("predict_once", "reactive")]
    [string]$Controller,
    [Parameter(Mandatory = $true)]
    [ValidateSet("belt_ramp", "encoder_bias", "latency_spike", "pose_disturbance")]
    [string]$Perturbation,
    [int]$Seed = 4701,
    [double]$BeltSpeedMps = 0.16,
    [double]$StartYM = 0.025,
    [double]$StartYawDeg = -22.0,
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot
)

$ErrorActionPreference = "Stop"
$allowBaselineFailure = $Controller -eq "predict_once"
& "$PSScriptRoot\run_solution_b.ps1" `
    -Seed $Seed `
    -Scenario nominal `
    -BeltSpeedMps $BeltSpeedMps `
    -StartYM $StartYM `
    -StartYawDeg $StartYawDeg `
    -GraspSelector geometric `
    -InterceptionController $Controller `
    -InterceptionPerturbation $Perturbation `
    -OutputRoot $OutputRoot `
    -AllowExpectedFailure:$allowBaselineFailure
if ($LASTEXITCODE -ne 0 -and -not $allowBaselineFailure) { throw "Solution D B reactive process failed" }
$metrics = Get-Content -LiteralPath (Join-Path $OutputRoot "scene2_integrated_metrics.json") -Raw | ConvertFrom-Json
if ($metrics.passed -and $metrics.grasp.affordance.mode -ne "geometric") {
    throw "Solution D B did not retain the geometric paired-comparison selector"
}
if ($metrics.reactive_interception -and $metrics.reactive_interception.controller -ne $Controller) {
    throw "Solution D B controller evidence does not match the requested controller"
}
if ($Controller -eq "reactive" -and (-not $metrics.passed -or $metrics.reactive_interception.updates.Count -lt 1)) {
    throw "Solution D B produced no reactive update decision"
}
