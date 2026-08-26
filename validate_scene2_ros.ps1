$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$isaacPython = "C:\Users\jainl\is6\Scripts\python.exe"
$rosRoot = "C:\Users\jainl\is6\Lib\site-packages\isaacsim\exts\isaacsim.ros2.core\humble"

if (-not (Test-Path -LiteralPath $isaacPython)) {
    throw "Isaac Sim Python launcher was not found at $isaacPython"
}
if (-not (Test-Path -LiteralPath "$rosRoot\rclpy")) {
    throw "Isaac Sim bundled ROS 2 Humble libraries were not found at $rosRoot"
}

$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:ROS_DISTRO = "humble"
$env:RMW_IMPLEMENTATION = "rmw_fastrtps_cpp"
$env:PYTHONPATH = "$rosRoot\rclpy;$env:PYTHONPATH"
$env:PATH = "$env:PATH;$rosRoot\lib"

& $isaacPython "$projectRoot\isaac_sim\run_scene2.py" --headless --ros2 --ros2-self-test @args
exit $LASTEXITCODE
