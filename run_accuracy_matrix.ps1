param(
    [string]$OutputRoot = "",
    [ValidateRange(1, 30)]
    [int]$Fps = 6,
    [switch]$CoreOnly,
    [switch]$Resume
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$auditPython = (Get-Command python -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python was not found at $isaacPython"
}
if (-not $OutputRoot) {
    $runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
    $OutputRoot = "results/accuracy_matrix/$runId"
}
if ([IO.Path]::IsPathRooted($OutputRoot)) {
    throw "OutputRoot must be a project-relative path"
}

$cases = @(
    [ordered]@{ name="core_a_slow_diagonal"; tier="core"; solution="a"; seed=4101; belt_speed_mps=0.06; start_y_m=-0.06; start_yaw_deg=-35.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35 },
    [ordered]@{ name="core_a_nominal"; tier="core"; solution="a"; seed=4102; belt_speed_mps=0.10; start_y_m=0.04; start_yaw_deg=0.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35; replay_group="a_nominal" },
    [ordered]@{ name="core_a_nominal_replay"; tier="core"; solution="a"; seed=4102; belt_speed_mps=0.10; start_y_m=0.04; start_yaw_deg=0.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35; replay_group="a_nominal" },
    [ordered]@{ name="core_a_medium_oblique"; tier="core"; solution="a"; seed=4103; belt_speed_mps=0.14; start_y_m=-0.03; start_yaw_deg=32.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35 },
    [ordered]@{ name="core_a_fast_transverse"; tier="core"; solution="a"; seed=4104; belt_speed_mps=0.18; start_y_m=0.05; start_yaw_deg=68.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35 },
    [ordered]@{ name="core_a_high_speed_transverse"; tier="core"; solution="a"; seed=4105; belt_speed_mps=0.22; start_y_m=-0.05; start_yaw_deg=-72.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35 },
    [ordered]@{ name="core_b_slow_diagonal"; tier="core"; solution="b"; seed=4201; belt_speed_mps=0.08; start_y_m=-0.04; start_yaw_deg=-25.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35 },
    [ordered]@{ name="core_b_nominal"; tier="core"; solution="b"; seed=4202; belt_speed_mps=0.10; start_y_m=0.03; start_yaw_deg=0.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35; replay_group="b_nominal" },
    [ordered]@{ name="core_b_nominal_replay"; tier="core"; solution="b"; seed=4202; belt_speed_mps=0.10; start_y_m=0.03; start_yaw_deg=0.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35; replay_group="b_nominal" },
    [ordered]@{ name="core_b_fast_oblique"; tier="core"; solution="b"; seed=4203; belt_speed_mps=0.18; start_y_m=0.04; start_yaw_deg=45.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35 },
    [ordered]@{ name="stress_a_limit_pose"; tier="stress"; solution="a"; seed=4301; belt_speed_mps=0.30; start_y_m=0.08; start_yaw_deg=85.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35 },
    [ordered]@{ name="stress_a_noisy"; tier="stress"; solution="a"; seed=4302; belt_speed_mps=0.16; start_y_m=-0.07; start_yaw_deg=55.0; perception_latency_ms=90.0; position_noise_mm=5.0; yaw_noise_deg=3.0 },
    [ordered]@{ name="stress_a_latency"; tier="stress"; solution="a"; seed=4303; belt_speed_mps=0.22; start_y_m=0.06; start_yaw_deg=-65.0; perception_latency_ms=140.0; position_noise_mm=2.0; yaw_noise_deg=1.0 },
    [ordered]@{ name="stress_b_high_speed"; tier="stress"; solution="b"; seed=4401; belt_speed_mps=0.26; start_y_m=0.07; start_yaw_deg=-75.0; perception_latency_ms=30.0; position_noise_mm=1.0; yaw_noise_deg=0.35 },
    [ordered]@{ name="stress_b_noisy"; tier="stress"; solution="b"; seed=4402; belt_speed_mps=0.16; start_y_m=-0.06; start_yaw_deg=55.0; perception_latency_ms=100.0; position_noise_mm=5.0; yaw_noise_deg=4.0 }
)
if ($CoreOnly) {
    $cases = @($cases | Where-Object { $_.tier -eq "core" })
}

$existingIsaac = @(Get-Process -Name "kit", "isaac-sim" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "C:\Users\jainl\is6*" })
if ($existingIsaac.Count -gt 0) {
    throw "Accuracy matrix requires a clean process state. Close the existing Isaac Sim process first."
}

$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:PYTHONPATH = "C:\Users\jainl\is6\Lib\site-packages"
New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot $OutputRoot) | Out-Null
$resolvedRoot = (Resolve-Path -LiteralPath (Join-Path $projectRoot $OutputRoot)).Path

Push-Location -LiteralPath $projectRoot
try {
    foreach ($case in $cases) {
        $caseOutputRoot = Join-Path $OutputRoot $case.name
        $caseRoot = Join-Path $projectRoot $caseOutputRoot
        New-Item -ItemType Directory -Force -Path $caseRoot | Out-Null
        $configPath = Join-Path $caseRoot "case_config.json"
        $metricsPath = Join-Path $caseRoot "scene2_integrated_metrics.json"
        $exitPath = Join-Path $caseRoot "process_exit_code.txt"
        $case | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding utf8
        if ($Resume -and (Test-Path -LiteralPath $metricsPath) -and (Test-Path -LiteralPath $exitPath)) {
            Write-Output "Skipping completed case $($case.name)"
            continue
        }

        $arguments = @(
            "isaac_sim\run_scene2_integrated.py",
            "--solution", $case.solution,
            "--seed", $case.seed,
            "--scenario", "nominal",
            "--belt-speed-mps", $case.belt_speed_mps,
            "--start-y-m", $case.start_y_m,
            "--start-yaw-deg", $case.start_yaw_deg,
            "--perception-latency-ms", $case.perception_latency_ms,
            "--position-noise-mm", $case.position_noise_mm,
            "--yaw-noise-deg", $case.yaw_noise_deg,
            "--output-root", $caseOutputRoot,
            "--fps", $Fps
        )
        $commandText = '"{0}" {1}' -f $isaacPython, (($arguments | ForEach-Object { '"{0}"' -f $_ }) -join " ")
        Set-Content -LiteralPath (Join-Path $caseRoot "command.txt") -Value $commandText -Encoding utf8
        Write-Output "Running $($case.name): solution $($case.solution.ToUpper()), speed $($case.belt_speed_mps) m/s, y $($case.start_y_m) m, yaw $($case.start_yaw_deg) deg"

        $process = Start-Process -FilePath $isaacPython -ArgumentList $arguments -Wait -PassThru -NoNewWindow `
            -RedirectStandardOutput (Join-Path $caseRoot "isaac_stdout.log") `
            -RedirectStandardError (Join-Path $caseRoot "isaac_stderr.log")
        $exitCode = $process.ExitCode
        Set-Content -LiteralPath $exitPath -Value $exitCode -Encoding ascii

        $orphans = @(Get-Process -Name "kit", "isaac-sim" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "C:\Users\jainl\is6*" })
        Set-Content -LiteralPath (Join-Path $caseRoot "orphan_process_count.txt") -Value $orphans.Count -Encoding ascii
        if ($orphans.Count -gt 0) {
            $orphans | Stop-Process -Force -ErrorAction SilentlyContinue
        }
        Write-Output "Finished $($case.name) with process exit code $exitCode"
    }

    & $auditPython tools\summarize_accuracy_matrix.py $resolvedRoot
    $summaryExitCode = $LASTEXITCODE
    Write-Output "Accuracy matrix evidence: $resolvedRoot"
    if ($summaryExitCode -ne 0) {
        throw "The core accuracy gate failed. See $resolvedRoot\accuracy_summary.json"
    }
}
finally {
    Get-Process -Name "kit", "isaac-sim" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "C:\Users\jainl\is6*" } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Pop-Location
}
