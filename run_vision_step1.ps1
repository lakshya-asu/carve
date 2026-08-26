param(
    [int]$Samples = 200,
    [int]$FramesPerScene = 4,
    [int]$Seed = 2601,
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacRoot = "C:\Users\jainl\is6"
$isaacPython = Join-Path $isaacRoot "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
$existing = @(Get-Process | Where-Object {
    try {
        $_.Path -and $_.Path.StartsWith($isaacRoot, [System.StringComparison]::OrdinalIgnoreCase)
    }
    catch {
        $false
    }
})
if ($existing.Count -ne 0) {
    $ids = ($existing | Select-Object -ExpandProperty Id) -join ", "
    throw "Vision generation requires a clean Isaac process state. Existing process IDs: $ids"
}
if ([string]::IsNullOrWhiteSpace($Output)) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $Output = "results\yolo\audits\dataset_v3_$stamp"
}
$env:OMNI_KIT_ACCEPT_EULA = "YES"
Push-Location -LiteralPath $projectRoot
try {
    & $isaacPython isaac_sim\generate_yolo_dataset.py `
        --samples $Samples `
        --frames-per-scene $FramesPerScene `
        --seed $Seed `
        --output $Output `
        --preview-count 18 `
        --save-depth `
        --headless
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $isaacPython tools\audit_yolo_dataset.py --dataset $Output
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $metadata = Get-Content (Join-Path $Output "dataset_metadata.json") -Raw | ConvertFrom-Json
    if (-not $metadata.passed) { throw "Vision dataset gates reported failure" }
    Write-Host "Vision Step 1 passed. Dataset: $Output"
}
finally {
    Pop-Location
}
