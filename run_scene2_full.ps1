param(
    [int]$Seed = 2601,
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/scene2_full/$runId"
}

Push-Location -LiteralPath $projectRoot
try {
    & "$projectRoot\validate_setup.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Setup validation failed" }
    & "$projectRoot\run_solution_a.ps1" -Seed $Seed -Scenario nominal -OutputRoot "$OutputRoot/solution_a"
    if ($LASTEXITCODE -ne 0) { throw "Solution A failed" }
    & "$projectRoot\run_solution_b.ps1" -Seed $Seed -Scenario nominal -OutputRoot "$OutputRoot/solution_b"
    if ($LASTEXITCODE -ne 0) { throw "Solution B failed" }

    $a = Get-Content "$OutputRoot/solution_a/scene2_integrated_metrics.json" -Raw | ConvertFrom-Json
    $b = Get-Content "$OutputRoot/solution_b/scene2_integrated_metrics.json" -Raw | ConvertFrom-Json
    $summary = [ordered]@{
        passed = [bool]($a.passed -and $b.passed)
        seed = $Seed
        solution_a_metrics = "$OutputRoot/solution_a/scene2_integrated_metrics.json"
        solution_b_metrics = "$OutputRoot/solution_b/scene2_integrated_metrics.json"
        solution_a_position_error_m = $a.delivery.measurement.position_error_m
        solution_b_position_error_m = $b.delivery.measurement.position_error_m
        solution_a_video = $a.recording.path
        solution_b_video = $b.recording.path
    }
    $summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$OutputRoot/summary.json" -Encoding utf8
    if (-not $summary.passed) { throw "The combined Scene 2 gate failed" }
    Write-Output "Complete Scene 2 evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
}
finally {
    Pop-Location
}
