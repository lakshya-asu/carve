$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$report = Join-Path $projectRoot "SCENE_DESIGN_REPORT.html"

Push-Location $projectRoot
try {
    python tools\validate_scene_report.py
    if ($LASTEXITCODE -ne 0) {
        throw "Scene report validation failed."
    }
    python tools\audit_report_language.py --fail-on-style
    if ($LASTEXITCODE -ne 0) {
        throw "Report language validation failed."
    }
    Start-Process -FilePath $report
}
finally {
    Pop-Location
}
