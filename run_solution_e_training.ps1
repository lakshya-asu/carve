param(
    [string]$OutputRoot = "results/solution_e/training/latest"
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
    python tools\build_contact_skill_dataset.py `
        --root results\solution_c\comparison\20260827_deterministic `
        --root results\solution_d\comparison\20260827_recovery `
        --root results\full_suite `
        --output "$OutputRoot\dataset.jsonl"
    if ($LASTEXITCODE -ne 0) { throw "Route E dataset build failed" }
    python tools\train_contact_skill.py "$OutputRoot\dataset.jsonl" --output models\contact_skill_v1\model.json
    if ($LASTEXITCODE -ne 0) { throw "Route E shadow model fit failed" }
    Copy-Item -LiteralPath models\contact_skill_v1\training_summary.json -Destination "$OutputRoot\training_summary.json" -Force
    Write-Output "Solution E training evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
}
finally {
    Pop-Location
}
