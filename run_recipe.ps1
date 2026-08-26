param(
    [ValidateSet("beef_center_cut_tenderloin", "pork_boneless_loin", "chicken_breast_fillet")]
    [string]$Recipe = "beef_center_cut_tenderloin",

    [ValidateSet("a", "b")]
    [string]$Solution = "a",

    [int]$Cycles = 4,

    [int]$Seed = 7
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
if ($Cycles -lt 1) {
    throw "Cycles must be at least one"
}
$outputRoot = "results/recipes/$Recipe/solution_$Solution"
$metricsPath = Join-Path $projectRoot "$outputRoot/isaac_$Solution/metrics.json"
$env:OMNI_KIT_ACCEPT_EULA = "YES"
Push-Location -LiteralPath $projectRoot
try {
    & $isaacPython isaac_sim\run_cell.py `
        --solution $Solution `
        --cycles $Cycles `
        --seed $Seed `
        --recipe $Recipe `
        --output-root $outputRoot `
        --headless
    if ($LASTEXITCODE -ne 0) {
        $failurePath = Join-Path $projectRoot "$outputRoot/isaac_$Solution/failure.json"
        if (Test-Path -LiteralPath $failurePath) {
            $failure = Get-Content -LiteralPath $failurePath -Raw | ConvertFrom-Json
            throw "Isaac recipe run failed: $($failure.error)"
        }
        throw "Isaac recipe run exited with code $LASTEXITCODE"
    }
    if (-not (Test-Path -LiteralPath $metricsPath)) {
        $failurePath = Join-Path $projectRoot "$outputRoot/isaac_$Solution/failure.json"
        if (Test-Path -LiteralPath $failurePath) {
            $failure = Get-Content -LiteralPath $failurePath -Raw | ConvertFrom-Json
            throw "Isaac recipe run did not produce metrics: $($failure.error)"
        }
        throw "Isaac recipe run did not produce metrics at $metricsPath"
    }
    $metrics = Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
    if (-not $metrics.passed) { throw "Recipe run metrics reported failure" }
    if ($metrics.product_recipe.recipe_id -ne $Recipe) { throw "Recipe evidence does not match the requested recipe" }
    Write-Host "Recipe run passed: $Recipe, Solution $($Solution.ToUpper())"
    Write-Host "Metrics: $metricsPath"
}
finally {
    Pop-Location
}
