#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
vscode_mcp.py - Native MCP tools provider for VS Code and local system in Snapgent.
Supports multi-directory access, portable relative paths, dynamic workspace switching,
and integrations with external CLI tools (OpenClaw, Antigravity/AGY, Hermes).
"""
import os
import sys
import glob
import json
import shutil
import subprocess
from pathlib import Path

WORKSPACE = os.environ.get("VSCODE_WORKSPACE_PATH") or os.environ.get("WORKSPACE_PATH") or os.getcwd()
WORKSPACE_PATH = Path(WORKSPACE).resolve()

def resolve_path(p: str) -> Path:
    if not p:
        return WORKSPACE_PATH
    expanded = os.path.expanduser(os.path.expandvars(str(p).strip()))
    path_obj = Path(expanded)
    if path_obj.is_absolute():
        return path_obj.resolve()
    return (WORKSPACE_PATH / path_obj).resolve()

def find_openclaw_bin() -> str:
    candidates = [
        shutil.which("openclaw"),
        os.path.expanduser("~/.nvm/versions/node/v24.22.0/bin/openclaw"),
        os.path.expanduser("~/.local/bin/openclaw"),
        "/usr/local/bin/openclaw"
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return "openclaw"

def find_agy_bin() -> str:
    candidates = [
        shutil.which("agy"),
        os.path.expanduser("~/.gemini/antigravity/bin/agentapi"),
        os.path.expanduser("~/.local/bin/agy"),
        "/usr/local/bin/agy"
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return "agy"

def find_hermes_bin() -> str:
    candidates = [
        shutil.which("hermes"),
        os.path.expanduser("~/.local/bin/hermes"),
        os.path.expanduser("~/hermes/hermes"),
        "/usr/local/bin/hermes"
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return "hermes"

TOOLS = [
    {
        "name": "list_dir",
        "description": "List files and folders in any directory using relative paths (e.g. '.', './src', '../sibling-project', '../../') or home path (~).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Supports relative paths (e.g. '.', '../another-folder', '../../') or home path (~). Default is '.'."
                }
            }
        }
    },
    {
        "name": "read_file",
        "description": "Read the text content of any file using relative paths (e.g. 'file.txt', '../other/app.js') or home path (~).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read. Supports relative paths (e.g. 'file.txt', '../other-folder/config.json') or home path (~)."
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional 1-based start line to read from."
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional 1-based end line (inclusive)."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write or overwrite any file using relative paths (e.g. 'file.txt', '../other/app.js') or home path (~).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the target file. Supports relative paths (e.g. 'output.txt', '../sibling/index.html') or home path (~)."
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write."
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "append_file",
        "description": "Append text to the end of a file (creates it if missing).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file (supports relative paths like 'log.txt' or '../other/log.txt')."
                },
                "content": {
                    "type": "string",
                    "description": "Text content to append."
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "replace_in_file",
        "description": "Replace every occurrence of a text fragment inside a file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file (supports relative paths like 'main.py' or '../other/main.py')."
                },
                "old_text": {
                    "type": "string",
                    "description": "Existing text to find."
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text."
                }
            },
            "required": ["path", "old_text", "new_text"]
        }
    },
    {
        "name": "delete_file",
        "description": "Delete a single file (files only, never directories).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to delete (supports relative paths like 'temp.txt' or '../other/temp.txt')."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "search_files",
        "description": "Search files for a text query across any folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for."
                },
                "path": {
                    "type": "string",
                    "description": "Folder to search inside. Supports relative paths (e.g. '.', '../sibling-folder') or home path (~). Default is '.'."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "run_command",
        "description": "Run a shell command in any directory (defaults to current workspace).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run."
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional working directory to run the command in (e.g. '../sibling-project' or '.')."
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "set_workspace",
        "description": "Switch the active default workspace directory to another folder using relative or home paths.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the new workspace directory (e.g. '../sibling-project', '../../other', or '~/my-project')."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "get_workspace_info",
        "description": "Get workspace root path plus total file, directory and byte counts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional folder path to inspect (supports relative paths like '.' or '../other'). Defaults to active workspace."
                }
            }
        }
    },
    {
        "name": "openclaw_command",
        "description": "Run OpenClaw CLI commands to access multi-channel agents, skills, and tools (e.g. 'status', 'skills list', 'models status', 'plugins list').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "OpenClaw subcommand to execute (e.g. 'status', 'skills list', 'plugins list', 'agent --message ...')."
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "agy_command",
        "description": "Run Google Antigravity (AGY) CLI commands, agentapi, or inspect agent workflows.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Antigravity/AGY command or arguments to execute."
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "hermes_command",
        "description": "Run Hermes agent / CLI commands or Python evaluation scripts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Hermes command or script parameters to execute."
                }
            },
            "required": ["command"]
        }
    }
]

def execute_tool(name: str, args: dict) -> str:
    global WORKSPACE_PATH

    if name == "set_workspace":
        target = resolve_path(args.get("path"))
        if not target.exists():
            return f"Error: directory '{target}' does not exist."
        if not target.is_dir():
            return f"Error: '{target}' is not a directory."
        WORKSPACE_PATH = target
        return f"Active workspace successfully changed to: {WORKSPACE_PATH}"

    elif name == "list_dir":
        rel = args.get("path") or "."
        target = resolve_path(rel)
        if not target.exists():
            return f"Error: directory '{target}' does not exist."
        if not target.is_dir():
            return f"Error: '{target}' is not a directory."
        items = []
        for p in sorted(target.iterdir()):
            kind = "DIR " if p.is_dir() else "FILE"
            size = f" ({p.stat().st_size} bytes)" if p.is_file() else ""
            items.append(f"{kind} {p.name}{size}")
        return f"Directory: {target}\n" + ("\n".join(items) if items else "(empty directory)")

    elif name == "read_file":
        rel = args.get("path")
        if not rel:
            return "Error: 'path' argument is required."
        target = resolve_path(rel)
        if not target.exists():
            return f"Error: file '{target}' not found."
        if not target.is_file():
            return f"Error: '{target}' is not a file."
        text = target.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start = args.get("start_line")
        end = args.get("end_line")
        if start is not None or end is not None:
            s_idx = max(1, int(start or 1)) - 1
            e_idx = int(end or len(lines))
            selected = lines[s_idx:e_idx]
            numbered = [f"{s_idx + i + 1:4d} | {line}" for i, line in enumerate(selected)]
            return "\n".join(numbered)
        return text

    elif name == "write_file":
        rel = args.get("path")
        content = args.get("content", "")
        if not rel:
            return "Error: 'path' argument is required."
        target = resolve_path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {target}"

    elif name == "append_file":
        rel = args.get("path")
        content = args.get("content", "")
        if not rel:
            return "Error: 'path' argument is required."
        target = resolve_path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully appended {len(content)} bytes to {target}"

    elif name == "replace_in_file":
        rel = args.get("path")
        old_text = args.get("old_text")
        new_text = args.get("new_text", "")
        if not rel or old_text is None:
            return "Error: 'path' and 'old_text' are required."
        target = resolve_path(rel)
        if not target.exists() or not target.is_file():
            return f"Error: file '{target}' not found."
        text = target.read_text(encoding="utf-8", errors="replace")
        count = text.count(old_text)
        if count == 0:
            return f"Error: old_text not found in {target}"
        new_content = text.replace(old_text, new_text)
        target.write_text(new_content, encoding="utf-8")
        return f"Replaced {count} occurrence(s) in {target}"

    elif name == "delete_file":
        rel = args.get("path")
        if not rel:
            return "Error: 'path' argument is required."
        target = resolve_path(rel)
        if not target.exists():
            return f"Error: file '{target}' not found."
        if not target.is_file():
            return f"Error: '{target}' is a directory. delete_file only removes files."
        target.unlink()
        return f"Deleted {target}"

    elif name == "search_files":
        query = args.get("query")
        rel = args.get("path") or "."
        if not query:
            return "Error: 'query' argument is required."
        target = resolve_path(rel)
        if not target.exists():
            return f"Error: folder '{target}' not found."
        results = []
        for root, _, files in os.walk(target):
            for file in files:
                fpath = Path(root) / file
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            if query in line:
                                results.append(f"{fpath}:{line_no}: {line.strip()[:160]}")
                                if len(results) >= 50:
                                    break
                except Exception:
                    continue
            if len(results) >= 50:
                break
        return "\n".join(results) if results else f"No matches found for '{query}' inside {target}"

    elif name == "run_command":
        cmd = args.get("command")
        custom_cwd = args.get("cwd")
        if not cmd:
            return "Error: 'command' argument is required."
        target_dir = resolve_path(custom_cwd) if custom_cwd else WORKSPACE_PATH
        if not target_dir.exists():
            return f"Error: directory '{target_dir}' does not exist."
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            out = res.stdout
            if res.stderr:
                out += ("\nSTDERR:\n" if out else "") + res.stderr
            return out if out.strip() else f"(Command exited with code {res.returncode}, no output)"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 120 seconds."
        except Exception as e:
            return f"Error running command: {e}"

    elif name == "get_workspace_info":
        target = resolve_path(args.get("path")) if args.get("path") else WORKSPACE_PATH
        if not target.exists():
            return f"Error: '{target}' does not exist."
        total_files = 0
        total_dirs = 0
        total_bytes = 0
        for root, dirs, files in os.walk(target):
            total_dirs += len(dirs)
            for f in files:
                total_files += 1
                try:
                    total_bytes += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return (
            f"Path: {target}\n"
            f"Active Workspace: {WORKSPACE_PATH}\n"
            f"Directories: {total_dirs}\n"
            f"Files: {total_files}\n"
            f"Total size: {total_bytes / (1024*1024):.2f} MB"
        )

    elif name == "openclaw_command":
        cmd_arg = args.get("command", "").strip()
        if not cmd_arg:
            return "Error: 'command' argument is required."
        bin_path = find_openclaw_bin()
        full_cmd = f"{bin_path} {cmd_arg}"
        try:
            res = subprocess.run(
                full_cmd,
                shell=True,
                cwd=str(WORKSPACE_PATH),
                capture_output=True,
                text=True,
                timeout=120
            )
            out = res.stdout
            if res.stderr:
                out += ("\nSTDERR:\n" if out else "") + res.stderr
            return out if out.strip() else f"(Command exited with code {res.returncode})"
        except Exception as e:
            return f"Error executing openclaw: {e}"

    elif name == "agy_command":
        cmd_arg = args.get("command", "").strip()
        if not cmd_arg:
            return "Error: 'command' argument is required."
        bin_path = find_agy_bin()
        full_cmd = f"{bin_path} {cmd_arg}"
        try:
            res = subprocess.run(
                full_cmd,
                shell=True,
                cwd=str(WORKSPACE_PATH),
                capture_output=True,
                text=True,
                timeout=120
            )
            out = res.stdout
            if res.stderr:
                out += ("\nSTDERR:\n" if out else "") + res.stderr
            return out if out.strip() else f"(Command exited with code {res.returncode})"
        except Exception as e:
            return f"Error executing agy: {e}"

    elif name == "hermes_command":
        cmd_arg = args.get("command", "").strip()
        if not cmd_arg:
            return "Error: 'command' argument is required."
        bin_path = find_hermes_bin()
        full_cmd = f"{bin_path} {cmd_arg}"
        try:
            res = subprocess.run(
                full_cmd,
                shell=True,
                cwd=str(WORKSPACE_PATH),
                capture_output=True,
                text=True,
                timeout=120
            )
            out = res.stdout
            if res.stderr:
                out += ("\nSTDERR:\n" if out else "") + res.stderr
            return out if out.strip() else f"(Command exited with code {res.returncode})"
        except Exception as e:
            return f"Error executing hermes: {e}"

    else:
        return f"Error: unknown tool '{name}'"
