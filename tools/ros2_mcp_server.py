"""Read-only ROS 2 introspection over MCP, for agents that must never actuate.

Speaks MCP over stdio as line-delimited JSON-RPC 2.0. No third-party
dependencies, so it runs under the system Python that ships with a ROS 2
distribution rather than needing a virtualenv on the robot.

Every tool shells out to the `ros2` CLI through an allowlist. The verbs that
publish, call, set, or kill are absent by construction: there is no code path
from this server to a moving joint. See `library/topics/safety-for-learned-policies.md`
for the shield pattern this follows.

Usage (normally launched by the MCP client, not by hand):
    ROS_DISTRO_SETUP=/opt/ros/humble/setup.bash python3 tools/ros2_mcp_server.py
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "ros2-readonly"
SERVER_VERSION = "1.0.0"
DEFAULT_SETUP = "/opt/ros/humble/setup.bash"
MAX_OUTPUT_CHARS = 20000
HARD_TIMEOUT_S = 30.0

# Only these `ros2` subcommand paths may run. Anything that changes robot state
# (topic pub, service call, action send_goal, param set, lifecycle set, run,
# launch, daemon stop) is absent on purpose and cannot be reached.
ALLOWED_ARGV_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("topic", "list"),
    ("topic", "info"),
    ("topic", "type"),
    ("topic", "echo"),
    ("topic", "hz"),
    ("topic", "bw"),
    ("topic", "delay"),
    ("topic", "find"),
    ("node", "list"),
    ("node", "info"),
    ("service", "list"),
    ("service", "type"),
    ("service", "find"),
    ("action", "list"),
    ("action", "info"),
    ("param", "list"),
    ("param", "get"),
    ("param", "describe"),
    ("param", "dump"),
    ("interface", "list"),
    ("interface", "show"),
    ("interface", "proto"),
    ("pkg", "list"),
    ("pkg", "prefix"),
    ("pkg", "xml"),
    ("bag", "info"),
    ("bag", "list"),
    ("doctor", "--report"),
    ("daemon", "status"),
)


class ToolError(Exception):
    """A tool call failed in a way the model should see and act on."""


def _setup_script() -> str:
    return os.environ.get("ROS_DISTRO_SETUP", DEFAULT_SETUP)


def run_ros2(argv: list[str], timeout_s: float) -> str:
    """Run one allowlisted `ros2` invocation and return its combined output.

    Args:
        argv: Arguments after the `ros2` executable, e.g. ["topic", "list"].
        timeout_s: Wall-clock limit; the call is killed after it.

    Returns:
        Combined stdout and stderr, truncated to MAX_OUTPUT_CHARS.

    Raises:
        ToolError: If argv is not allowlisted, or the setup script is missing.
    """
    if not any(tuple(argv[: len(p)]) == p for p in ALLOWED_ARGV_PREFIXES):
        raise ToolError(
            f"refused: 'ros2 {' '.join(argv)}' is not in the read-only allowlist. "
            "This server cannot publish, call services, send goals, or set parameters."
        )
    setup = _setup_script()
    if not os.path.exists(setup):
        raise ToolError(f"ROS setup script not found at {setup}; set ROS_DISTRO_SETUP")
    # PYTHONPATH is unset so a conda env on the caller's PATH cannot shadow rclpy.
    # exec replaces bash with ros2, so killing the child kills ros2 itself.
    command = (
        f"unset PYTHONPATH; . {shlex.quote(setup)} >/dev/null 2>&1; exec ros2 {' '.join(shlex.quote(a) for a in argv)}"
    )
    limit = min(timeout_s, HARD_TIMEOUT_S)
    proc = subprocess.Popen(["bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    # `topic hz` and a multi-message `topic echo` never exit on their own, so the
    # timeout is the normal path: kill the child and keep what it already printed.
    try:
        out, _ = proc.communicate(timeout=limit)
        timed_out = False
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
        timed_out = True
    out = (out or "").strip()
    if not out:
        return (
            f"(no output within {limit:g} s; the topic may be idle or the node may be down)"
            if timed_out
            else "(no output)"
        )
    if len(out) > MAX_OUTPUT_CHARS:
        out = out[:MAX_OUTPUT_CHARS] + f"\n... truncated at {MAX_OUTPUT_CHARS} characters"
    return out


@dataclass(frozen=True)
class Tool:
    """One MCP tool: its schema and the function that runs it."""

    name: str
    description: str
    schema: dict[str, Any]
    run: Callable[[dict[str, Any]], str]


def _topic_arg(args: dict[str, Any], key: str = "topic") -> str:
    value = str(args.get(key, "")).strip()
    if not value.startswith("/"):
        raise ToolError(f"{key} must be an absolute name starting with '/', got {value!r}")
    return value


def _tools() -> list[Tool]:
    def topic_list(_a: dict[str, Any]) -> str:
        return run_ros2(["topic", "list", "-t"], 10)

    def topic_info(a: dict[str, Any]) -> str:
        return run_ros2(["topic", "info", _topic_arg(a), "--verbose"], 10)

    def topic_echo(a: dict[str, Any]) -> str:
        # Humble's `topic echo` has --once but no --times, so more than one
        # message means streaming until the timeout and keeping what arrived.
        count = max(1, min(int(a.get("count", 1)), 20))
        argv = ["topic", "echo", _topic_arg(a)]
        if count == 1:
            argv.append("--once")
        return run_ros2(argv, float(a.get("timeout_s", 10)))

    def topic_hz(a: dict[str, Any]) -> str:
        window = max(2, min(int(a.get("window", 10)), 100))
        return run_ros2(["topic", "hz", _topic_arg(a), "--window", str(window)], float(a.get("timeout_s", 10)))

    def node_list(_a: dict[str, Any]) -> str:
        return run_ros2(["node", "list"], 10)

    def node_info(a: dict[str, Any]) -> str:
        name = str(a.get("node", "")).strip()
        if not name.startswith("/"):
            raise ToolError("node must be an absolute name starting with '/'")
        return run_ros2(["node", "info", name], 10)

    def param_list(a: dict[str, Any]) -> str:
        node = str(a.get("node", "")).strip()
        return run_ros2(["param", "list", node] if node else ["param", "list"], 15)

    def param_get(a: dict[str, Any]) -> str:
        node = str(a.get("node", "")).strip()
        name = str(a.get("name", "")).strip()
        if not node or not name:
            raise ToolError("both node and name are required")
        return run_ros2(["param", "get", node, name], 10)

    def service_list(_a: dict[str, Any]) -> str:
        return run_ros2(["service", "list", "-t"], 10)

    def action_list(_a: dict[str, Any]) -> str:
        return run_ros2(["action", "list", "-t"], 10)

    def interface_show(a: dict[str, Any]) -> str:
        itype = str(a.get("type", "")).strip()
        if "/" not in itype:
            raise ToolError("type must look like pkg/msg/Name, e.g. sensor_msgs/msg/JointState")
        return run_ros2(["interface", "show", itype], 10)

    def bag_info(a: dict[str, Any]) -> str:
        path = str(a.get("path", "")).strip()
        if not path or not os.path.exists(path):
            raise ToolError(f"bag path does not exist: {path!r}")
        return run_ros2(["bag", "info", path], 20)

    def doctor(_a: dict[str, Any]) -> str:
        return run_ros2(["doctor", "--report"], 20)

    topic_prop = {"topic": {"type": "string", "description": "Absolute topic name, e.g. /joint_states"}}
    return [
        Tool(
            "ros2_topic_list",
            "List all topics with their message types.",
            {"type": "object", "properties": {}},
            topic_list,
        ),
        Tool(
            "ros2_topic_info",
            "Publisher and subscriber count, type, and QoS profiles for one topic.",
            {"type": "object", "properties": topic_prop, "required": ["topic"]},
            topic_info,
        ),
        Tool(
            "ros2_topic_echo",
            "Read up to 20 messages from a topic. Read-only: this never publishes.",
            {
                "type": "object",
                "properties": {
                    **topic_prop,
                    "count": {"type": "integer", "description": "Messages to read, 1 to 20 (default 1)"},
                    "timeout_s": {"type": "number", "description": "Give up after this many seconds (default 10)"},
                },
                "required": ["topic"],
            },
            topic_echo,
        ),
        Tool(
            "ros2_topic_hz",
            "Measure the publish rate of a topic. Use to check a control loop is running at its configured rate.",
            {
                "type": "object",
                "properties": {**topic_prop, "window": {"type": "integer"}, "timeout_s": {"type": "number"}},
                "required": ["topic"],
            },
            topic_hz,
        ),
        Tool("ros2_node_list", "List running nodes.", {"type": "object", "properties": {}}, node_list),
        Tool(
            "ros2_node_info",
            "Subscriptions, publishers, services, and actions of one node.",
            {"type": "object", "properties": {"node": {"type": "string"}}, "required": ["node"]},
            node_info,
        ),
        Tool(
            "ros2_param_list",
            "List parameters, for one node or for all nodes.",
            {"type": "object", "properties": {"node": {"type": "string"}}},
            param_list,
        ),
        Tool(
            "ros2_param_get",
            "Read one parameter value. There is no setter in this server.",
            {
                "type": "object",
                "properties": {"node": {"type": "string"}, "name": {"type": "string"}},
                "required": ["node", "name"],
            },
            param_get,
        ),
        Tool(
            "ros2_service_list",
            "List services with their types. Calling a service is not possible here.",
            {"type": "object", "properties": {}},
            service_list,
        ),
        Tool(
            "ros2_action_list",
            "List action servers with their types. Sending a goal is not possible here.",
            {"type": "object", "properties": {}},
            action_list,
        ),
        Tool(
            "ros2_interface_show",
            "Show the definition of a message, service, or action type.",
            {"type": "object", "properties": {"type": {"type": "string"}}, "required": ["type"]},
            interface_show,
        ),
        Tool(
            "ros2_bag_info",
            "Summarise a recorded bag: duration, message counts, topics, storage format.",
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            bag_info,
        ),
        Tool(
            "ros2_doctor",
            "Run ros2 doctor and return the report. Use when discovery or QoS looks wrong.",
            {"type": "object", "properties": {}},
            doctor,
        ),
    ]


TOOLS: dict[str, Tool] = {t.name: t for t in _tools()}


def handle(request: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one JSON-RPC request; return a response, or None for a notification."""
    method = request.get("method", "")
    req_id = request.get("id")
    if method == "initialize":
        client_version = str(request.get("params", {}).get("protocolVersion") or PROTOCOL_VERSION)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": client_version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Read-only ROS 2 introspection. No tool here can publish, call a service, "
                    "send an action goal, or set a parameter. To command a robot, ask the human."
                ),
            },
        }
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {"name": t.name, "description": t.description, "inputSchema": t.schema} for t in TOOLS.values()
                ]
            },
        }
    if method == "tools/call":
        params = request.get("params", {})
        name = str(params.get("name", ""))
        tool = TOOLS.get(name)
        if tool is None:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"unknown tool {name!r}"}}
        try:
            text = tool.run(params.get("arguments") or {})
            is_error = False
        except ToolError as exc:
            text, is_error = str(exc), True
        except (OSError, ValueError) as exc:
            text, is_error = f"{type(exc).__name__}: {exc}", True
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": text}], "isError": is_error},
        }
    if req_id is None:
        return None
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"unknown method {method!r}"}}


def main() -> int:
    """Serve MCP over stdio until stdin closes."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
