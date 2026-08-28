param(
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/solution_d/comparison/$runId"
}

$cases = @(
    @{ Solution = "a"; Perturbation = "belt_ramp"; Seed = 4611 },
    @{ Solution = "a"; Perturbation = "encoder_bias"; Seed = 4612 },
    @{ Solution = "a"; Perturbation = "latency_spike"; Seed = 4613 },
    @{ Solution = "a"; Perturbation = "pose_disturbance"; Seed = 4614 },
    @{ Solution = "b"; Perturbation = "belt_ramp"; Seed = 4711 },
    @{ Solution = "b"; Perturbation = "encoder_bias"; Seed = 4712 },
    @{ Solution = "b"; Perturbation = "latency_spike"; Seed = 4713 },
    @{ Solution = "b"; Perturbation = "pose_disturbance"; Seed = 4714 }
)

Push-Location -LiteralPath $projectRoot
try {
    foreach ($case in $cases) {
        foreach ($controller in "predict_once", "reactive") {
            $suffix = if ($controller -eq "predict_once") { "baseline" } else { "reactive" }
            $name = "$($case.Solution)_$($case.Perturbation)_$suffix"
            $launcher = if ($case.Solution -eq "a") { ".\run_solution_d_a.ps1" } else { ".\run_solution_d_b.ps1" }
            & $launcher -Controller $controller -Perturbation $case.Perturbation -Seed $case.Seed -OutputRoot "$OutputRoot/$name"
        }
    }
    foreach ($solution in "a", "b") {
        $seed = if ($solution -eq "a") { 4614 } else { 4714 }
        $launcher = if ($solution -eq "a") { ".\run_solution_d_a.ps1" } else { ".\run_solution_d_b.ps1" }
        & $launcher -Controller reactive -Perturbation pose_disturbance -Seed $seed -OutputRoot "$OutputRoot/${solution}_pose_disturbance_reactive_replay"
    }
    python tools\summarize_solution_d.py $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "Solution D comparison gate failed" }
    Write-Output "Solution D comparison evidence: $(Resolve-Path -LiteralPath $OutputRoot)"
}
finally {
    Get-CimInstance Win32_Process | Where-Object {
        ($_.ExecutablePath -like "C:\Users\jainl\is6*" -and $_.Name -in @("kit.exe", "isaac-sim.exe")) -or
        ($_.Name -eq "python.exe" -and $_.CommandLine -match "isaac_sim[\\/]")
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Pop-Location
}
