$ErrorActionPreference = "Stop"
$page = Join-Path $PSScriptRoot "PROJECT_PAGE.html"
if (-not (Test-Path -LiteralPath $page)) {
    throw "Project page not found: $page"
}
Start-Process -FilePath $page
