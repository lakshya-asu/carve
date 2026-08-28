from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _launcher_text(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


def test_primary_isaac_launchers_reject_concurrent_python_hosts() -> None:
    for name in (
        "run_solution_a.ps1",
        "run_solution_b.ps1",
        "run_solution_c.ps1",
        "run_solution_c_training.ps1",
        "run_hybrid_comparison.ps1",
        "run_tests.ps1",
    ):
        text = _launcher_text(name)
        assert "Get-CimInstance Win32_Process" in text, name
        assert '$_ .Name -eq "python.exe"'.replace("$_ ", "$_") in text, name
        assert 'CommandLine -match "isaac_sim[\\\\/]"' in text, name
        assert "requires a clean Isaac state" in text or "requires a clean Isaac" in text, name


def test_primary_isaac_launchers_reject_other_project_batch_hosts() -> None:
    for name in (
        "run_solution_a.ps1",
        "run_solution_b.ps1",
        "run_solution_c.ps1",
        "run_solution_c_training.ps1",
        "run_hybrid_comparison.ps1",
        "run_tests.ps1",
    ):
        text = _launcher_text(name)
        assert "ProcessId -ne $PID" in text, name
        assert '$_ .Name -in @("pwsh.exe", "powershell.exe")'.replace("$_ ", "$_") in text, name
        assert "hybrid_comparison" in text, name


def test_all_batch_launchers_cleanup_isaac_python_hosts() -> None:
    for name in (
        "run_solution_a.ps1",
        "run_solution_b.ps1",
        "run_solution_c.ps1",
        "run_solution_c_training.ps1",
        "run_solution_d.ps1",
        "run_solution_e.ps1",
        "run_hybrid_comparison.ps1",
        "run_tests.ps1",
    ):
        text = _launcher_text(name)
        cleanup = text[text.rfind("finally {") :]
        assert (
            "Get-CimInstance Win32_Process" in cleanup
            or "Get-ScopedIsaacProcesses" in cleanup
        ), name
        assert '$_ .Name -eq "python.exe"'.replace("$_ ", "$_") in text, name
        assert 'CommandLine -match "isaac_sim[\\\\/]"' in text, name
        assert "Stop-Process -Id $_.ProcessId -Force" in cleanup, name


def test_launchers_do_not_treat_telemetry_as_an_owned_simulator_process() -> None:
    for name in (
        "run_solution_a.ps1",
        "run_solution_b.ps1",
        "run_solution_c.ps1",
        "run_solution_c_training.ps1",
        "run_solution_d.ps1",
        "run_solution_e.ps1",
        "run_hybrid_comparison.ps1",
        "run_tests.ps1",
    ):
        text = _launcher_text(name)
        assert 'Name -match "^(kit|isaac-sim|omni)"' not in text, name
        assert '"kit.exe", "isaac-sim.exe"' in text, name


def test_solution_c_training_waits_for_each_isaac_process_to_release() -> None:
    text = _launcher_text("run_solution_c_training.ps1")
    assert "function Wait-ForIsaacRelease" in text
    assert "Start-Sleep -Milliseconds 250" in text
    assert "Wait-ForIsaacRelease" in text[text.index("foreach ($candidateIndex") :]
