param(
    [int]$Seed = 4502,
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/solution_c/runs/solution_b_seed${Seed}_$runId"
}
& "$PSScriptRoot\run_solution_b.ps1" -Seed $Seed -Scenario nominal -BeltSpeedMps 0.16 -StartYM 0.03 -StartYawDeg 28 `
    -GraspSelector learned -GraspModel models/grasp_affordance_v2_matched/model.json -OutputRoot $OutputRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$metrics = Get-Content (Join-Path $OutputRoot "scene2_integrated_metrics.json") -Raw | ConvertFrom-Json
if ($metrics.grasp.affordance.mode -ne "learned" -or $metrics.grasp.affordance.fallback_used) {
    throw "Solution C B did not execute the learned scorer"
}
if ($metrics.grasp.affordance.candidates.Count -lt 3) { throw "Solution C B did not rank several safe candidates" }
Write-Output "Solution C B evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
