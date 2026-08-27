param(
    [string]$Distro = "humble"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspace = Join-Path $projectRoot "ros2_ws"
$linuxWorkspace = (& C:\Windows\System32\wsl.exe wslpath -a ($workspace -replace '\\','/')).Trim()
$probe = "test -f /opt/ros/$Distro/setup.bash && command -v colcon >/dev/null && test -d '$linuxWorkspace'"

& C:\Windows\System32\wsl.exe bash -lc $probe
if ($LASTEXITCODE -ne 0) {
    Write-Host "BLOCKED: ROS 2 $Distro and colcon are required in the existing WSL environment. Nothing was installed." -ForegroundColor Red
    exit 2
}

$command = "set -e; source /opt/ros/$Distro/setup.bash; cd '$linuxWorkspace'; colcon build --symlink-install; source install/setup.bash; ros2 pkg executables carve_moveit_config; ros2 pkg executables carve_moveit_demo"
& C:\Windows\System32\wsl.exe bash -lc $command
exit $LASTEXITCODE
