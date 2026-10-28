#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
bridge.py - Native Python bridge for Snapgent on Linux / macOS / Windows.
Listens on ws://127.0.0.1:17613 and bridges browser AI chat to VS Code tools.
"""
import os
import sys
import json
import asyncio
import logging
from pathlib import Path

try:
    import websockets
except ImportError:
    print("[bridge] Missing dependency. Run: pip install websockets", file=sys.stderr)
    sys.exit(1)

import vscode_mcp

PORT = int(os.environ.get("ZS_BRIDGE_PORT", 17613))
HOST = "127.0.0.1"

# Attach server: "vscode" to all tool definitions so extension routes properly
ALL_TOOLS = []
for t in vscode_mcp.TOOLS:
    t_copy = dict(t)
    t_copy["server"] = "vscode"
    ALL_TOOLS.append(t_copy)

SERVERS_INFO = [
    {
        "id": "vscode",
        "name": "VS Code",
        "alive": True,
        "tools": len(ALL_TOOLS)
    }
]

print(f"\n\033[1;32m  === Snapgent Local Bridge ===\033[0m")
print(f"  Target: \033[1;36mVS Code MCP\033[0m ({len(ALL_TOOLS)} tools loaded)")
print(f"  Listening on: \033[1;33mws://{HOST}:{PORT}\033[0m")
print(f"  Workspace: {vscode_mcp.WORKSPACE_PATH}")
print(f"  Keep this process running while using the extension.\n")

async def handler(websocket):
    print(f"\033[32m[bridge] Browser extension connected.\033[0m")
    # Send initial connected handshake
    init_msg = {
        "type": "connected",
        "mcp_alive": True,
        "tools": ALL_TOOLS,
        "servers": SERVERS_INFO,
        "studio": False,
        "studio_app": False,
        "studio_proc": False
    }
    await websocket.send(json.dumps(init_msg))

    try:
        async for raw_message in websocket:
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            msg_id = data.get("id")

            if msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong", "id": msg_id}))

            elif msg_type == "studio_status":
                await websocket.send(json.dumps({
                    "type": "studio_status",
                    "id": msg_id,
                    "ok": True,
                    "studio": False,
                    "studio_app": False,
                    "studio_proc": False
                }))

            elif msg_type == "list_tools":
                await websocket.send(json.dumps({
                    "type": "tools",
                    "id": msg_id,
                    "ok": True,
                    "tools": ALL_TOOLS,
                    "servers": SERVERS_INFO,
                    "mcp_alive": True
                }))

            elif msg_type == "call_tool":
                tool_name = data.get("name")
                tool_args = data.get("arguments", {})
                print(f"[bridge] \033[36mCalling tool:\033[0m {tool_name} with {json.dumps(tool_args)[:120]}")
                try:
                    result_text = await asyncio.to_thread(vscode_mcp.execute_tool, tool_name, tool_args)
                    resp = {
                        "type": "tool_result",
                        "id": msg_id,
                        "ok": True,
                        "text": str(result_text),
                        "images": []
                    }
                except Exception as e:
                    resp = {
                        "type": "tool_result",
                        "id": msg_id,
                        "ok": False,
                        "kind": "error",
                        "error": str(e)
                    }
                await websocket.send(json.dumps(resp))

            elif msg_type == "restart_mcp":
                await websocket.send(json.dumps({
                    "type": "mcp_status",
                    "id": msg_id,
                    "ok": True,
                    "alive": True
                }))

            elif msg_type in ("add_server", "remove_server"):
                await websocket.send(json.dumps({
                    "type": "server_changed",
                    "id": msg_id,
                    "ok": True,
                    "restarting": False
                }))

            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "id": msg_id,
                    "error": f"Unknown message type: {msg_type}"
                }))

    except websockets.exceptions.ConnectionClosed:
        print("\033[33m[bridge] Browser extension disconnected.\033[0m")
    except Exception as e:
        print(f"\033[31m[bridge] Error: {e}\033[0m")

import re

# Only allow connections from browser extensions. Web pages (https://...) and
# clients without an Origin header are rejected with HTTP 403.
# Optional: lock to specific extension IDs via ZS_ALLOWED_ORIGINS, e.g.
# "chrome-extension://abcdefghijklmnop,moz-extension://xxxx"
_env_origins = os.environ.get("ZS_ALLOWED_ORIGINS", "").strip()
if _env_origins:
    ALLOWED_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = [re.compile(r"^(chrome|moz)-extension://[A-Za-z0-9._-]+$")]

async def main():
    async with websockets.serve(handler, HOST, PORT, origins=ALLOWED_ORIGINS):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[bridge] Stopped.")
