import json
import subprocess
import sys
from pathlib import Path

import pytest

import ros2_mcp_server as srv

SERVER = Path(srv.__file__)


def test_actuating_verbs_are_not_reachable() -> None:
    for argv in (
        ["topic", "pub", "/cmd_vel", "geometry_msgs/msg/Twist", "{}"],
        ["service", "call", "/set_io", "std_srvs/srv/SetBool"],
        ["action", "send_goal", "/follow_joint_trajectory", "x", "{}"],
        ["param", "set", "/arm", "max_velocity", "9.0"],
        ["lifecycle", "set", "/driver", "activate"],
        ["run", "demo_nodes_cpp", "talker"],
        ["launch", "my_pkg", "bringup.launch.py"],
        ["daemon", "stop"],
    ):
        with pytest.raises(srv.ToolError, match="read-only allowlist"):
            srv.run_ros2(argv, 1)


def test_allowlist_matches_on_prefix_not_substring() -> None:
    with pytest.raises(srv.ToolError, match="read-only allowlist"):
        srv.run_ros2(["bag", "record", "-a"], 1)
    with pytest.raises(srv.ToolError, match="read-only allowlist"):
        srv.run_ros2(["topic", "pub"], 1)


def test_missing_setup_script_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROS_DISTRO_SETUP", "/nonexistent/setup.bash")
    with pytest.raises(srv.ToolError, match="setup script not found"):
        srv.run_ros2(["topic", "list"], 1)


def test_topic_name_must_be_absolute() -> None:
    result = srv.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "ros2_topic_info", "arguments": {"topic": "joint_states"}},
        }
    )
    assert result is not None
    assert result["result"]["isError"] is True
    assert "absolute name" in result["result"]["content"][0]["text"]


def test_initialize_echoes_client_protocol_version() -> None:
    result = srv.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
    )
    assert result is not None
    assert result["result"]["protocolVersion"] == "2025-06-18"
    assert result["result"]["serverInfo"]["name"] == "ros2-readonly"


def test_tools_list_exposes_only_read_verbs() -> None:
    result = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert result is not None
    names = {t["name"] for t in result["result"]["tools"]}
    assert "ros2_topic_list" in names and "ros2_bag_info" in names
    assert not {n for n in names if any(v in n for v in ("pub", "call", "send", "set", "kill"))}
    for tool in result["result"]["tools"]:
        assert tool["inputSchema"]["type"] == "object"


def test_notifications_get_no_response() -> None:
    assert srv.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_tool_is_a_jsonrpc_error() -> None:
    result = srv.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "ros2_topic_pub"}})
    assert result is not None
    assert result["error"]["code"] == -32601


def test_output_is_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(srv, "MAX_OUTPUT_CHARS", 50)
    monkeypatch.setattr(srv, "ALLOWED_ARGV_PREFIXES", (("echo",),))
    out = srv.run_ros2(["echo", "x" * 500], 5)
    assert "truncated" in out and len(out) < 200


def test_stdio_round_trip() -> None:
    """The server answers initialize then tools/list over stdin and stdout."""
    lines = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        + "\n"
    )
    proc = subprocess.run([sys.executable, str(SERVER)], input=lines, capture_output=True, text=True, timeout=30)
    replies = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert [r["id"] for r in replies] == [1, 2]
    assert len(replies[1]["result"]["tools"]) == len(srv.TOOLS)
