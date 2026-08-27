param(
    [string]$OutputRoot = "",
    [switch]$IncludeSolutionB
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/speed_pose_matrix/$runId"
}

$cases = @(
    [ordered]@{ name = "slow_diagonal_right"; seed = 3101; speed = 0.06; y = -0.06; yaw = -35.0 },
    [ordered]@{ name = "nominal_longitudinal"; seed = 3102; speed = 0.10; y = 0.04; yaw = 0.0 },
    [ordered]@{ name = "medium_diagonal_left"; seed = 3103; speed = 0.14; y = -0.03; yaw = 32.0 },
    [ordered]@{ name = "fast_transverse"; seed = 3104; speed = 0.18; y = 0.05; yaw = 68.0 },
    [ordered]@{ name = "high_speed_transverse"; seed = 3105; speed = 0.22; y = -0.05; yaw = -72.0 }
)

Push-Location -LiteralPath $projectRoot
try {
    $summary = @()
    foreach ($case in $cases) {
        $caseRoot = "$OutputRoot/$($case.name)"
        & "$projectRoot\run_solution_a.ps1" -Seed $case.seed -Scenario nominal -BeltSpeedMps $case.speed -StartYM $case.y -StartYawDeg $case.yaw -OutputRoot $caseRoot
        if ($LASTEXITCODE -ne 0) { throw "Speed and pose case failed: $($case.name)" }
        $metrics = Get-Content -LiteralPath "$caseRoot/scene2_integrated_metrics.json" -Raw | ConvertFrom-Json
        $summary += [ordered]@{
            name = $case.name
            passed = [bool]$metrics.passed
            speed_mps = $metrics.belt_speed_mps
            start_y_m = $metrics.initial_pose.y_m
            start_yaw_deg = $metrics.initial_pose.yaw_deg
            grasp_class = $metrics.grasp.proposal.grasp_class.value
            grasp_confidence = $metrics.grasp.proposal.confidence
            intercept_timing_error_s = $metrics.interception.timing_error_s
            delivery_position_error_m = $metrics.delivery.measurement.position_error_m
            delivery_angle_error_rad = $metrics.delivery.measurement.angle_error_rad
            video = $metrics.recording.path
            overlay = $metrics.artifacts.segmentation
            trajectory = $metrics.artifacts.trajectory
        }
    }
    if ($IncludeSolutionB) {
        $caseRoot = "$OutputRoot/solution_b_fast_slip_correction"
        & "$projectRoot\run_solution_b.ps1" -Seed 3110 -Scenario slip_correction -BeltSpeedMps 0.16 -StartYM 0.03 -StartYawDeg 28.0 -OutputRoot $caseRoot
        if ($LASTEXITCODE -ne 0) { throw "Solution B speed and slip case failed" }
        $metrics = Get-Content -LiteralPath "$caseRoot/scene2_integrated_metrics.json" -Raw | ConvertFrom-Json
        $summary += [ordered]@{
            name = "solution_b_fast_slip_correction"
            passed = [bool]$metrics.passed
            speed_mps = $metrics.belt_speed_mps
            start_y_m = $metrics.initial_pose.y_m
            start_yaw_deg = $metrics.initial_pose.yaw_deg
            grasp_class = $metrics.grasp.proposal.grasp_class.value
            grasp_confidence = $metrics.grasp.proposal.confidence
            intercept_timing_error_s = $metrics.interception.timing_error_s
            delivery_position_error_m = $metrics.delivery.measurement.position_error_m
            delivery_angle_error_rad = $metrics.delivery.measurement.angle_error_rad
            video = $metrics.recording.path
            overlay = $metrics.artifacts.segmentation
            trajectory = $metrics.artifacts.trajectory
        }
    }
    $document = [ordered]@{
        passed = [bool](($summary | Where-Object { -not $_.passed }).Count -eq 0)
        generated_at = (Get-Date).ToString("o")
        criteria = [ordered]@{
            configured_speed_range_mps = @(0.04, 0.30)
            demonstrated_speed_range_mps = @(0.06, 0.22)
            demonstrated_lateral_range_m = @(-0.06, 0.05)
            demonstrated_yaw_range_deg = @(-72.0, 68.0)
            all_cases_require_yolo = $true
            all_cases_require_mask_interior_grasp = $true
            all_cases_require_bilateral_contact = $true
            all_cases_require_zero_motion_limit_violations = $true
        }
        cases = $summary
    }
    New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
    $document | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$OutputRoot/matrix_summary.json" -Encoding utf8
    if (-not $document.passed) { throw "One or more speed and pose cases failed" }
    Write-Output "Speed and pose matrix evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
}
finally {
    Get-Process -Name "kit", "isaac-sim" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "C:\Users\jainl\is6*" } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Pop-Location
}
