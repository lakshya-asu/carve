param(
    [string]$OutputRoot = "",
    [int[]]$FitSeeds = @(5001, 5002, 5003),
    [int[]]$HoldoutSeeds = @(5101, 5102)
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$python = (Get-Command python -ErrorAction Stop).Source

function Get-ScopedIsaacProcesses {
    return @(Get-CimInstance Win32_Process | Where-Object {
        ($_.ExecutablePath -like "C:\Users\jainl\is6*" -and $_.Name -in @("kit.exe", "isaac-sim.exe")) -or
        ($_.Name -eq "python.exe" -and $_.CommandLine -match "isaac_sim[\\/]")
    })
}

function Wait-ForIsaacRelease {
    param([int]$TimeoutSeconds = 15)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $remaining = @(Get-ScopedIsaacProcesses)
        if ($remaining.Count -eq 0) { return }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    $ids = (@(Get-ScopedIsaacProcesses) | ForEach-Object { $_.ProcessId }) -join ", "
    throw "Isaac process release timed out. Remaining process IDs: $ids"
}
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/solution_c/matched_training/$runId"
}
if ($FitSeeds.Count -lt 2 -or $HoldoutSeeds.Count -lt 1) {
    throw "Solution C needs at least two fit seeds and one held-out seed"
}
if (@($FitSeeds | Where-Object { $HoldoutSeeds -contains $_ }).Count -gt 0) {
    throw "Fit and held-out seeds must be disjoint"
}
$holdoutSeedMin = ($HoldoutSeeds | Measure-Object -Minimum).Minimum
if (($FitSeeds | Measure-Object -Maximum).Maximum -ge $holdoutSeedMin) {
    throw "Every fit seed must be lower than every held-out seed"
}
$existing = @(Get-ScopedIsaacProcesses) + @(Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $_.Name -in @("pwsh.exe", "powershell.exe") -and
    $_.CommandLine -match "run_(solution_[abcde]|hybrid_comparison|tests|hardening|accuracy_matrix|speed_pose_matrix)\.ps1"
})
if ($existing.Count -gt 0) { throw "Solution C training requires a clean Isaac process state" }

$profiles = @(
    @{ speed = 0.10; y = -0.05; yaw = -55.0 },
    @{ speed = 0.16; y = 0.00; yaw = -20.0 },
    @{ speed = 0.22; y = 0.05; yaw = 20.0 },
    @{ speed = 0.13; y = 0.025; yaw = 55.0 },
    @{ speed = 0.19; y = -0.025; yaw = 75.0 }
)
$allSeeds = @($FitSeeds) + @($HoldoutSeeds)
$trialsRoot = Join-Path $OutputRoot "trials"
$dataset = Join-Path $OutputRoot "grasp_affordance_dataset.jsonl"
$splitManifest = Join-Path $OutputRoot "grasp_affordance_split.json"
$candidateModel = Join-Path $OutputRoot "candidate_model.json"
$trainingSummary = Join-Path $OutputRoot "training_summary.json"
$heldoutSummary = Join-Path $OutputRoot "heldout_evaluation.json"
$publishedModel = Join-Path $projectRoot "models\grasp_affordance_v2_matched\model.json"

Push-Location -LiteralPath $projectRoot
try {
    for ($groupIndex = 0; $groupIndex -lt $allSeeds.Count; $groupIndex++) {
        $seed = $allSeeds[$groupIndex]
        $profile = $profiles[$groupIndex % $profiles.Count]
        foreach ($candidateIndex in 0..4) {
            $caseRoot = Join-Path $trialsRoot "seed${seed}_candidate${candidateIndex}"
            $metricsPath = Join-Path $caseRoot "scene2_integrated_metrics.json"
            if (Test-Path -LiteralPath $metricsPath) {
                $existingMetrics = Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
                if (
                    $existingMetrics.demo_kind -eq "complete Scene 2 rendered YOLO26 to FANUC contact delivery" -and
                    $existingMetrics.test_settings.grasp_candidate_index -eq $candidateIndex -and
                    $existingMetrics.grasp.affordance.mode -eq "forced_geometry_candidate" -and
                    $existingMetrics.motion.maximum_physics_step_error_s -le 1e-9
                ) {
                    Write-Output "Reusing complete matched trial seed=$seed candidate=$candidateIndex passed=$($existingMetrics.passed)"
                    continue
                }
            }
            New-Item -ItemType Directory -Path $caseRoot -Force | Out-Null
            $launcherLog = Join-Path $caseRoot "launcher_output.log"
            try {
                & "$projectRoot\run_solution_a.ps1" `
                    -Seed $seed `
                    -Scenario nominal `
                    -BeltSpeedMps $profile.speed `
                    -StartYM $profile.y `
                    -StartYawDeg $profile.yaw `
                    -GraspSelector geometric `
                    -GraspCandidateIndex $candidateIndex `
                    -OutputRoot $caseRoot `
                    -AllowExpectedFailure *> $launcherLog
            }
            catch {
                Get-Content -LiteralPath $launcherLog -Tail 40 -ErrorAction SilentlyContinue | Write-Output
                throw
            }
            Wait-ForIsaacRelease
            if (-not (Test-Path -LiteralPath $metricsPath)) {
                throw "Candidate $candidateIndex for seed $seed did not write metrics"
            }
            $metrics = Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
            if ($metrics.test_settings.grasp_candidate_index -ne $candidateIndex) {
                throw "Candidate $candidateIndex for seed $seed was not executed as requested"
            }
            if ($metrics.grasp.affordance.mode -ne "forced_geometry_candidate") {
                throw "Candidate $candidateIndex for seed $seed did not use the matched-trial path"
            }
            if ($metrics.motion.maximum_physics_step_error_s -gt 1e-9) {
                throw "Candidate $candidateIndex for seed $seed did not execute at measured 240 Hz"
            }
            Write-Output "Completed matched trial seed=$seed candidate=$candidateIndex passed=$($metrics.passed)"
        }
    }
    & $python tools\build_grasp_affordance_dataset.py --input-root $trialsRoot --output $dataset --manifest $splitManifest --holdout-seed-min $holdoutSeedMin
    if ($LASTEXITCODE -ne 0) { throw "Solution C matched dataset build failed" }
    & $python tools\train_grasp_affordance.py --dataset $dataset --model $candidateModel --summary $trainingSummary
    if ($LASTEXITCODE -ne 0) { throw "Solution C model fitting failed" }
    & $python tools\evaluate_grasp_affordance.py --dataset $dataset --model $candidateModel --output $heldoutSummary
    if ($LASTEXITCODE -ne 0) { throw "Solution C held-out candidate evaluation failed" }
    $evaluation = Get-Content -LiteralPath $heldoutSummary -Raw | ConvertFrom-Json
    if (-not $evaluation.passed) { throw "Solution C model did not pass held-out gates" }
    New-Item -ItemType Directory -Path (Split-Path -Parent $publishedModel) -Force | Out-Null
    Copy-Item -LiteralPath $candidateModel -Destination $publishedModel -Force
    Write-Output "Solution C dataset and evaluation: $(Resolve-Path -LiteralPath $OutputRoot)"
    Write-Output "Published Solution C model: $publishedModel"
}
finally {
    Get-ScopedIsaacProcesses | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Pop-Location
}
