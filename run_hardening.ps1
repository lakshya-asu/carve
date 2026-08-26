param(
    [int[]]$Seeds = @(7, 31, 101, 509, 1001),
    [int]$Cycles = 6,
    [switch]$Resume
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacRoot = "C:\Users\jainl\is6"
$isaacPython = Join-Path $isaacRoot "Scripts\python.exe"
$resultRoot = Join-Path $projectRoot "results\hardening"
$logRoot = Join-Path $resultRoot "logs"

if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
if ($Cycles -lt 6) {
    throw "Hardening requires at least six cycles so every integrated scenario runs"
}

function Get-IsaacProcess {
    Get-Process | Where-Object {
        try {
            $_.Path -and $_.Path.StartsWith($isaacRoot, [System.StringComparison]::OrdinalIgnoreCase)
        }
        catch {
            $false
        }
    }
}

$existing = @(Get-IsaacProcess)
if ($existing.Count -ne 0) {
    $ids = ($existing | Select-Object -ExpandProperty Id) -join ", "
    throw "Hardening requires a clean Isaac process state. Existing process IDs: $ids"
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$env:OMNI_KIT_ACCEPT_EULA = "YES"
Push-Location -LiteralPath $projectRoot
try {
    foreach ($seed in $Seeds) {
        foreach ($solution in @("a", "b")) {
            $seedLabel = "seed_{0:D4}" -f $seed
            $relativeOutput = "results\hardening\$seedLabel"
            $logStem = "solution_{0}_{1}" -f $solution, $seedLabel
            $stdout = Join-Path $logRoot "$logStem.stdout.log"
            $stderr = Join-Path $logRoot "$logStem.stderr.log"
            $attempt = 1
            while ((Test-Path -LiteralPath $stdout) -or (Test-Path -LiteralPath $stderr)) {
                $stdout = Join-Path $logRoot ("{0}.attempt_{1}.stdout.log" -f $logStem, $attempt)
                $stderr = Join-Path $logRoot ("{0}.attempt_{1}.stderr.log" -f $logStem, $attempt)
                $attempt += 1
            }
            $metricsPath = Join-Path $projectRoot "$relativeOutput\isaac_$solution\metrics.json"
            if ($Resume -and (Test-Path -LiteralPath $metricsPath)) {
                $existingMetrics = Get-Content $metricsPath -Raw | ConvertFrom-Json
                if (
                    $existingMetrics.passed -and
                    $existingMetrics.seed -eq $seed -and
                    $existingMetrics.cycles -eq $Cycles -and
                    $existingMetrics.scenario_profile -eq "hardening"
                ) {
                    continue
                }
            }
            $batchStarted = Get-Date
            $arguments = @(
                "isaac_sim\run_cell.py",
                "--solution", $solution,
                "--cycles", $Cycles,
                "--seed", $seed,
                "--scenario-profile", "hardening",
                "--output-root", $relativeOutput,
                "--headless"
            )
            try {
                & $isaacPython @arguments 1> $stdout 2> $stderr
                $exitCode = $LASTEXITCODE
                if ($exitCode -ne 0) {
                    throw "Solution $solution seed $seed failed with exit code $exitCode. See $stdout and $stderr"
                }
                if (-not (Test-Path -LiteralPath $metricsPath)) {
                    throw "Solution $solution seed $seed did not produce metrics. See $stdout and $stderr"
                }
                $metrics = Get-Content $metricsPath -Raw | ConvertFrom-Json
                if (-not $metrics.passed) {
                    throw "Solution $solution seed $seed metrics reported failure. See $metricsPath"
                }
            }
            finally {
                $orphaned = @(
                    Get-IsaacProcess | Where-Object {
                        $_.StartTime -ge $batchStarted.AddSeconds(-2)
                    }
                )
                foreach ($item in $orphaned) {
                    Stop-Process -Id $item.Id -Force -ErrorAction SilentlyContinue
                }
                if ($orphaned.Count -ne 0) {
                    throw "Batch left $($orphaned.Count) Isaac process or processes. They were closed and the batch is failed."
                }
            }
        }
    }
    $seedList = ($Seeds -join ",")
    & $isaacPython tools\audit_artifacts.py `
        --root results\hardening `
        --mode hardening `
        --expected-seeds $seedList `
        --output results\hardening\summary.json
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
