param(
    [int]$Seed = 4501,
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/solution_c/runs/solution_a_seed${Seed}_$runId"
}
& "$PSScriptRoot\run_solution_a.ps1" -Seed $Seed -Scenario nominal -BeltSpeedMps 0.14 -StartYM -0.03 -StartYawDeg 32 `
    -GraspSelector learned -GraspModel models/grasp_affordance_v2_matched/model.json -OutputRoot $OutputRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$metrics = Get-Content (Join-Path $OutputRoot "scene2_integrated_metrics.json") -Raw | ConvertFrom-Json
if ($metrics.grasp.affordance.mode -ne "learned" -or $metrics.grasp.affordance.fallback_used) {
    throw "Solution C A did not execute the learned scorer"
}
if ($metrics.grasp.affordance.candidates.Count -lt 3) { throw "Solution C A did not rank several safe candidates" }
Write-Output "Solution C A evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
