#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
'''
vscode_extra.py - extra tools for the Snapgent VS Code provider.

File tools: find_files, search_regex, move_file, copy_file, make_dir, project_tree
Background processes: start_process, read_process_output, stop_process, list_processes
Git helpers: git_log, git_commit, git_branch
Dev checks: run_tests, lint

execute(name, args, resolve_path) returns a string, or None if the name is not handled here.
'''
import atexit
import fnmatch
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

NL = chr(10)
IGNORED_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.mypy_cache', '.pytest_cache', '.ruff_cache', '.snapgent_backup'}
BINARY_EXT = {'.exe', '.dll', '.so', '.dylib', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.zip', '.gz', '.tar', '.pdf', '.pyc', '.woff', '.woff2', '.mp4', '.mp3'}
MAX_FILE_BYTES = 2 * 1024 * 1024


def _str(d):
    return {'type': 'string', 'description': d}


def _num(d):
    return {'type': 'integer', 'description': d}


def _flag(d):
    return {'type': 'boolean', 'description': d}


def _tool(name, description, properties, required=None):
    schema = {'type': 'object', 'properties': properties}
    if required:
        schema['required'] = required
    return {'name': name, 'description': description, 'inputSchema': schema}


TOOLS = [
    _tool('find_files', 'Find files by name with a glob pattern (e.g. *.py, src/*.js). Skips .git, node_modules and virtualenvs.',
          {'pattern': _str('Glob pattern, case-insensitive.'), 'path': _str('Folder to search. Default is the workspace.'), 'max_results': _num('Max results (default 200).')}, ['pattern']),
    _tool('search_regex', 'Search file contents with a regular expression. Uses ripgrep when installed, otherwise a built-in fallback.',
          {'pattern': _str('Regular expression.'), 'path': _str('File or folder to search. Default is the workspace.'), 'glob': _str('Only search files matching this glob, e.g. *.py.'), 'ignore_case': _flag('Case-insensitive search.'), 'max_results': _num('Max matching lines (default 100).')}, ['pattern']),
    _tool('move_file', 'Move or rename a file or folder. Refuses to overwrite unless overwrite=true (files only).',
          {'src': _str('Source path.'), 'dst': _str('Destination path. An existing folder means move inside it.'), 'overwrite': _flag('Allow replacing an existing destination file.')}, ['src', 'dst']),
    _tool('copy_file', 'Copy a file or folder. Refuses to overwrite unless overwrite=true (files only).',
          {'src': _str('Source path.'), 'dst': _str('Destination path. An existing folder means copy inside it.'), 'overwrite': _flag('Allow replacing an existing destination file.')}, ['src', 'dst']),
    _tool('make_dir', 'Create a folder and any missing parents.', {'path': _str('Folder to create.')}, ['path']),
    _tool('project_tree', 'Compact tree view of a folder. Skips .git, node_modules and virtualenvs.',
          {'path': _str('Folder. Default is the workspace.'), 'max_depth': _num('Depth (default 3).'), 'max_entries': _num('Max entries (default 300).')}),
    _tool('start_process', 'Start a long-running shell command in the background (dev server, watcher, long build). Returns an id. Max 5 running.',
          {'command': _str('Shell command to run.'), 'cwd': _str('Optional working directory.')}, ['command']),
    _tool('read_process_output', 'Read new output of a background process since the last read.',
          {'id': _num('Process id from start_process.'), 'wait_seconds': _num('Optional wait before reading, 0-30.')}, ['id']),
    _tool('stop_process', 'Stop a background process and its children.', {'id': _num('Process id from start_process.')}, ['id']),
    _tool('list_processes', 'List background processes and their status.', {}),
    _tool('git_log', 'Show recent commits (short hash, date, author, subject).',
          {'path': _str('Repo folder. Default is the workspace.'), 'max_count': _num('Number of commits (default 20, max 200).'), 'file': _str('Only commits touching this file.')}),
    _tool('git_commit', 'Create a commit. Stages only the given files (or everything with all=true), otherwise commits what is already staged. Never pushes and never amends.',
          {'message': _str('Commit message.'), 'files': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Paths to stage before committing.'}, 'all': _flag('Stage ALL changes, including unrelated ones.'), 'path': _str('Repo folder. Default is the workspace.')}, ['message']),
    _tool('git_branch', 'List, create, switch or delete a branch. Delete is the safe kind and only works for merged branches.',
          {'action': {'type': 'string', 'enum': ['list', 'create', 'switch', 'delete'], 'description': 'Default is list.'}, 'name': _str('Branch name (needed for create, switch, delete).'), 'path': _str('Repo folder. Default is the workspace.')}),
    _tool('run_tests', 'Run project tests. Auto-detects pytest, npm test, cargo test or go test, or runs a custom command. Returns pass/fail plus the tail of the output.',
          {'path': _str('Project folder. Default is the workspace.'), 'command': _str('Optional custom test command (overrides detection).'), 'timeout': _num('Timeout in seconds (default 300, max 1800).')}),
    _tool('lint', 'Run linters. Auto-detects ruff and eslint, with a Python syntax check as fallback. fix=true lets the linter modify files.',
          {'path': _str('Project folder. Default is the workspace.'), 'command': _str('Optional custom lint command (overrides detection).'), 'fix': _flag('Apply automatic fixes (modifies files).'), 'timeout': _num('Timeout in seconds (default 300, max 1800).')}),
]


def _to_int(v, default):
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _clip(text, limit=15000, keep_tail=False):
    if len(text) <= limit:
        return text
    if keep_tail:
        return f'[Note: output truncated, showing the last {limit} of {len(text)} chars]' + NL + text[-limit:]
    return text[:limit] + NL + NL + f'[Note: output truncated at {limit} chars (total {len(text)}).]'


def _run(cmd, cwd, timeout=120, shell=False):
    try:
        res = subprocess.run(cmd, cwd=str(cwd), shell=shell, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        return res, None
    except subprocess.TimeoutExpired:
        return None, f'Error: command timed out after {timeout} seconds.'
    except Exception as e:
        return None, f'Error: {e}'


def _combined(res):
    out = res.stdout or ''
    if res.stderr:
        out += (NL + 'STDERR:' + NL if out else '') + res.stderr
    return out.strip()


def _is_text_candidate(path):
    try:
        return path.suffix.lower() not in BINARY_EXT and path.stat().st_size <= MAX_FILE_BYTES
    except OSError:
        return False


def _walk(base):
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        for fname in sorted(files):
            yield Path(root) / fname


# ---------------------------------------------------------------- file tools
def _find_files(args, resolve_path):
    pattern = args.get('pattern')
    if not pattern:
        return 'Error: pattern argument is required.'
    base = resolve_path(args.get('path'))
    if not base.is_dir():
        return f'Error: folder {base} not found.'
    limit = _to_int(args.get('max_results'), 200)
    use_rel = '/' in pattern
    pat = pattern.lower()
    found = []
    for f in _walk(base):
        rel = f.relative_to(base).as_posix()
        target = rel if use_rel else f.name
        if fnmatch.fnmatchcase(target.lower(), pat):
            found.append(rel)
            if len(found) >= limit:
                break
    if not found:
        return f'No files matching {pattern} in {base}'
    note = f'{NL}[limit of {limit} reached, narrow the pattern]' if len(found) >= limit else ''
    return f'Base: {base}{NL}' + NL.join(found) + note


def _search_regex(args, resolve_path):
    pattern = args.get('pattern')
    if not pattern:
        return 'Error: pattern argument is required.'
    base = resolve_path(args.get('path'))
    if not base.exists():
        return f'Error: {base} not found.'
    name_glob = args.get('glob')
    ignore_case = bool(args.get('ignore_case'))
    limit = _to_int(args.get('max_results'), 100)
    rg = shutil.which('rg')
    if rg:
        cmd = [rg, '--line-number', '--no-heading', '--color', 'never', '--max-columns', '200']
        if ignore_case:
            cmd.append('-i')
        if name_glob:
            cmd += ['-g', name_glob]
        cmd += ['-e', pattern, '--', str(base)]
        res, err = _run(cmd, base if base.is_dir() else base.parent, 60)
        if err:
            return err
        if res.returncode == 1:
            return f'No matches found for /{pattern}/ in {base}'
        if res.returncode > 1:
            return f'Error: ripgrep failed: {_combined(res)}'
        lines = res.stdout.splitlines()
        note = f'{NL}[showing first {limit} of {len(lines)} matches]' if len(lines) > limit else ''
        return NL.join(lines[:limit]) + note
    try:
        rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as e:
        return f'Error: invalid regex: {e}'
    files = [base] if base.is_file() else _walk(base)
    results = []
    for f in files:
        if name_glob and not fnmatch.fnmatch(f.name, name_glob):
            continue
        if not _is_text_candidate(f):
            continue
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                for no, line in enumerate(fh, 1):
                    if rx.search(line):
                        results.append(f'{f}:{no}: {line.strip()[:200]}')
                        if len(results) >= limit:
                            break
        except OSError:
            continue
        if len(results) >= limit:
            break
    if not results:
        return f'No matches found for /{pattern}/ in {base}'
    return NL.join(results)


def _move_copy(name, args, resolve_path):
    if not args.get('src') or not args.get('dst'):
        return 'Error: src and dst are required.'
    src = resolve_path(args['src'])
    dst = resolve_path(args['dst'])
    if not src.exists():
        return f'Error: {src} not found.'
    final = dst / src.name if dst.is_dir() else dst
    if final == src:
        return 'Error: source and destination are the same.'
    if src.is_dir() and src in final.parents:
        return 'Error: cannot place a folder inside itself.'
    if final.exists():
        if not args.get('overwrite'):
            return f'Error: {final} already exists. Pass overwrite=true to replace a file.'
        if final.is_dir() or src.is_dir():
            return 'Error: overwrite only works file-to-file. Remove the destination folder yourself first.'
        if name == 'move_file':
            final.unlink()
    final.parent.mkdir(parents=True, exist_ok=True)
    try:
        if name == 'move_file':
            shutil.move(str(src), str(final))
            return f'Moved {src} -> {final}'
        if src.is_dir():
            shutil.copytree(str(src), str(final))
        else:
            shutil.copy2(str(src), str(final))
        return f'Copied {src} -> {final}'
    except Exception as e:
        return f'Error: {e}'


def _make_dir(args, resolve_path):
    if not args.get('path'):
        return 'Error: path argument is required.'
    target = resolve_path(args['path'])
    if target.exists() and not target.is_dir():
        return f'Error: {target} exists and is not a folder.'
    target.mkdir(parents=True, exist_ok=True)
    return f'Folder ready: {target}'


def _project_tree(args, resolve_path):
    base = resolve_path(args.get('path'))
    if not base.is_dir():
        return f'Error: folder {base} not found.'
    max_depth = max(1, _to_int(args.get('max_depth'), 3))
    cap = _to_int(args.get('max_entries'), 300)
    lines = [f'{base}/']
    state = {'count': 0, 'truncated': False}

    def walk(d, prefix, depth):
        try:
            entries = sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        entries = [e for e in entries if not (e.is_dir() and e.name in IGNORED_DIRS)]
        for i, e in enumerate(entries):
            if state['count'] >= cap:
                state['truncated'] = True
                return
            last = i == len(entries) - 1
            lines.append(prefix + ('+-- ' if last else '|-- ') + e.name + ('/' if e.is_dir() else ''))
            state['count'] += 1
            if e.is_dir() and not e.is_symlink() and depth < max_depth:
                walk(e, prefix + ('    ' if last else '|   '), depth + 1)
            if state['truncated']:
                return

    walk(base, '', 1)
    if state['truncated']:
        lines.append(f'[truncated at {cap} entries]')
    return NL.join(lines)


# ------------------------------------------------------ background processes
_PROCS = {}
_LOCK = threading.Lock()
_COUNTER = [0]
MAX_RUNNING = 5
MAX_BUF_LINES = 5000


class _Proc(object):
    def __init__(self, command, cwd):
        self.command = command
        self.cwd = str(cwd)
        self.started = time.time()
        self.lines = []
        self.base = 0
        self.read_pos = 0
        self.lock = threading.Lock()
        extra = {}
        if os.name == 'nt':
            extra['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            extra['start_new_session'] = True
        self.popen = subprocess.Popen(command, shell=True, cwd=self.cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, **extra)
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            for line in self.popen.stdout:
                with self.lock:
                    self.lines.append(line.rstrip(NL))
                    over = len(self.lines) - MAX_BUF_LINES
                    if over > 0:
                        del self.lines[:over]
                        self.base += over
        except Exception:
            pass

    def read_new(self):
        with self.lock:
            start = max(self.read_pos, self.base)
            skipped = start - self.read_pos
            new = self.lines[start - self.base:]
            self.read_pos = self.base + len(self.lines)
        return new, skipped

    def status(self):
        code = self.popen.poll()
        return 'running' if code is None else f'exited (code {code})'

    def stop(self):
        if self.popen.poll() is not None:
            return
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(self.popen.pid), '/T', '/F'], capture_output=True)
            else:
                os.killpg(os.getpgid(self.popen.pid), signal.SIGTERM)
        except Exception:
            try:
                self.popen.terminate()
            except Exception:
                pass
        try:
            self.popen.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                if os.name == 'nt':
                    self.popen.kill()
                else:
                    os.killpg(os.getpgid(self.popen.pid), signal.SIGKILL)
            except Exception:
                pass


def _proc_output(proc):
    new, skipped = proc.read_new()
    text = NL.join(new)
    if skipped:
        text = f'[{skipped} older lines were dropped from the buffer]' + NL + text
    if not text.strip():
        return '(no new output)'
    return _clip(text, 8000, keep_tail=True)


def _start_process(args, resolve_path):
    cmd = args.get('command')
    if not cmd:
        return 'Error: command argument is required.'
    cwd = resolve_path(args.get('cwd'))
    if not cwd.is_dir():
        return f'Error: directory {cwd} does not exist.'
    with _LOCK:
        running = [p for p in _PROCS.values() if p.popen.poll() is None]
        if len(running) >= MAX_RUNNING:
            return f'Error: {MAX_RUNNING} processes already running. Stop one first.'
        _COUNTER[0] += 1
        pid = _COUNTER[0]
        try:
            proc = _Proc(cmd, cwd)
        except Exception as e:
            return f'Error: could not start process: {e}'
        _PROCS[pid] = proc
    time.sleep(1.0)
    return f'Started process {pid} ({proc.status()}) in {cwd}{NL}{_proc_output(proc)}'


def _read_process(args, resolve_path):
    pid = _to_int(args.get('id'), -1)
    proc = _PROCS.get(pid)
    if proc is None:
        return f'Error: no process with id {pid}. Use list_processes.'
    wait = min(max(_to_int(args.get('wait_seconds'), 0), 0), 30)
    if wait:
        time.sleep(wait)
    return f'Process {pid}: {proc.status()}{NL}{_proc_output(proc)}'


def _stop_process(args, resolve_path):
    pid = _to_int(args.get('id'), -1)
    proc = _PROCS.get(pid)
    if proc is None:
        return f'Error: no process with id {pid}. Use list_processes.'
    proc.stop()
    time.sleep(0.3)
    out = _proc_output(proc)
    status = proc.status()
    with _LOCK:
        _PROCS.pop(pid, None)
    return f'Process {pid} stopped ({status}).{NL}Last output:{NL}{out}'


def _list_processes(args, resolve_path):
    if not _PROCS:
        return '(no background processes)'
    rows = []
    for pid, p in sorted(_PROCS.items()):
        age = int(time.time() - p.started)
        rows.append(f'{pid}: {p.status()} | {age}s | {p.command} | cwd {p.cwd}')
    return NL.join(rows)


def _cleanup():
    for p in list(_PROCS.values()):
        try:
            p.stop()
        except Exception:
            pass


atexit.register(_cleanup)


# ----------------------------------------------------------------------- git
def _git_cwd(args, resolve_path):
    base = resolve_path(args.get('path'))
    if not base.is_dir():
        return None, f'Error: folder {base} not found.'
    return base, None


def _git_log(args, resolve_path):
    base, err = _git_cwd(args, resolve_path)
    if err:
        return err
    n = min(max(_to_int(args.get('max_count'), 20), 1), 200)
    cmd = ['git', 'log', f'--max-count={n}', '--date=short', '--pretty=format:%h %ad %an | %s']
    if args.get('file'):
        cmd += ['--', str(args['file'])]
    res, e = _run(cmd, base, 60)
    if e:
        return e
    out = _combined(res)
    if res.returncode != 0:
        return f'Error: git log failed: {out}'
    return out or '(no commits)'


def _git_commit(args, resolve_path):
    base, err = _git_cwd(args, resolve_path)
    if err:
        return err
    msg = (args.get('message') or '').strip()
    if not msg:
        return 'Error: message argument is required.'
    files = args.get('files') or []
    if files:
        if not isinstance(files, list):
            return 'Error: files must be a list of paths.'
        res, e = _run(['git', 'add', '--'] + [str(f) for f in files], base, 60)
        if e:
            return e
        if res.returncode != 0:
            return f'Error: git add failed: {_combined(res)}'
    elif args.get('all'):
        res, e = _run(['git', 'add', '-A'], base, 60)
        if e:
            return e
        if res.returncode != 0:
            return f'Error: git add failed: {_combined(res)}'
    res, e = _run(['git', 'diff', '--cached', '--quiet'], base, 60)
    if e:
        return e
    if res.returncode == 0:
        return 'Error: nothing staged to commit. Pass files=[...] or all=true.'
    if res.returncode != 1:
        return f'Error: git failed: {_combined(res)}'
    res, e = _run(['git', 'commit', '-m', msg], base, 120)
    if e:
        return e
    out = _combined(res)
    if res.returncode != 0:
        return f'Error: git commit failed: {out}'
    last, _ = _run(['git', 'log', '-1', '--stat', '--oneline'], base, 30)
    return 'Committed.' + NL + (last.stdout.strip() if last is not None else out)


def _git_branch(args, resolve_path):
    base, err = _git_cwd(args, resolve_path)
    if err:
        return err
    action = (args.get('action') or 'list').strip().lower()
    name = (args.get('name') or '').strip()
    if action == 'list':
        cmd = ['git', 'branch', '-vv']
    elif action in ('create', 'switch', 'delete'):
        if not name:
            return 'Error: name is required for ' + action + '.'
        if name.startswith('-') or not re.match(r'^[A-Za-z0-9._/-]+$', name):
            return 'Error: invalid branch name.'
        if action == 'create':
            cmd = ['git', 'switch', '-c', name]
        elif action == 'switch':
            cmd = ['git', 'switch', name]
        else:
            cmd = ['git', 'branch', '-d', name]
    else:
        return 'Error: action must be list, create, switch or delete.'
    res, e = _run(cmd, base, 60)
    if e:
        return e
    out = _combined(res)
    if res.returncode != 0:
        return f'Error: git {action} failed: {out}'
    return out or f'Done: {action} {name}'.strip()


# ------------------------------------------------------------ tests and lint
def _timeout(args):
    return min(max(_to_int(args.get('timeout'), 300), 1), 1800)


def _report(label, res, err):
    if err:
        return f'{label}: {err}'
    out = _combined(res)
    status = 'PASSED' if res.returncode == 0 else f'FAILED (exit code {res.returncode})'
    return f'{label}: {status}' + NL + _clip(out, 6000, keep_tail=True)


def _run_tests(args, resolve_path):
    base = resolve_path(args.get('path'))
    if not base.is_dir():
        return f'Error: folder {base} not found.'
    timeout = _timeout(args)
    custom = (args.get('command') or '').strip()
    if custom:
        res, err = _run(custom, base, timeout, shell=True)
        return _report('Tests (' + custom + ')', res, err)
    pkg = base / 'package.json'
    has_npm_test = False
    if pkg.is_file():
        try:
            scripts = json.loads(pkg.read_text(encoding='utf-8', errors='replace')).get('scripts', {})
            has_npm_test = 'test' in scripts and 'no test specified' not in str(scripts['test'])
        except Exception:
            has_npm_test = False
    py_markers = ['pytest.ini', 'conftest.py', 'tox.ini', 'setup.cfg', 'pyproject.toml']
    has_py = any((base / m).exists() for m in py_markers) or (base / 'tests').is_dir()
    if has_py:
        res, err = _run([sys.executable, '-m', 'pytest', '-q', '--maxfail=20'], base, timeout)
        if res is not None and 'No module named pytest' in _combined(res):
            return 'Error: pytest is not installed. Install it with: pip install pytest'
        return _report('Tests (pytest)', res, err)
    if has_npm_test:
        res, err = _run('npm test', base, timeout, shell=True)
        return _report('Tests (npm test)', res, err)
    if (base / 'Cargo.toml').is_file():
        res, err = _run(['cargo', 'test'], base, timeout)
        return _report('Tests (cargo test)', res, err)
    if (base / 'go.mod').is_file():
        res, err = _run(['go', 'test', './...'], base, timeout)
        return _report('Tests (go test)', res, err)
    return 'Error: no test setup detected. Pass command=... to run a custom test command.'


def _lint(args, resolve_path):
    base = resolve_path(args.get('path'))
    if not base.is_dir():
        return f'Error: folder {base} not found.'
    timeout = _timeout(args)
    fix = bool(args.get('fix'))
    custom = (args.get('command') or '').strip()
    if custom:
        res, err = _run(custom, base, timeout, shell=True)
        return _report('Lint (' + custom + ')', res, err)
    parts = []
    py_files = []
    for f in _walk(base):
        if f.suffix == '.py':
            py_files.append(f)
            if len(py_files) >= 2000:
                break
    if py_files and shutil.which('ruff'):
        cmd = ['ruff', 'check'] + (['--fix'] if fix else []) + ['.']
        res, err = _run(cmd, base, timeout)
        parts.append(_report('ruff', res, err))
    eslint_cfgs = ['eslint.config.js', 'eslint.config.mjs', 'eslint.config.cjs', '.eslintrc', '.eslintrc.json', '.eslintrc.js', '.eslintrc.cjs', '.eslintrc.yml', '.eslintrc.yaml']
    if any((base / c).exists() for c in eslint_cfgs):
        cmd = 'npx --no-install eslint' + (' --fix' if fix else '') + ' .'
        res, err = _run(cmd, base, timeout, shell=True)
        parts.append(_report('eslint', res, err))
    if not parts and py_files:
        problems = []
        for f in py_files:
            try:
                compile(f.read_text(encoding='utf-8', errors='replace'), str(f), 'exec')
            except SyntaxError as e:
                problems.append(f'{f}:{e.lineno}: {e.msg}')
            except Exception as e:
                problems.append(f'{f}: {e}')
        if problems:
            parts.append('python syntax check: FAILED' + NL + NL.join(problems[:100]))
        else:
            parts.append(f'python syntax check: PASSED ({len(py_files)} files). Install ruff for real lint rules.')
    if not parts:
        return 'Error: no linter detected (need ruff, an eslint config, or Python files). Pass command=... for a custom linter.'
    return (NL + NL).join(parts)


# ------------------------------------------------------------------ dispatch
HANDLERS = {
    'find_files': _find_files,
    'search_regex': _search_regex,
    'make_dir': _make_dir,
    'project_tree': _project_tree,
    'start_process': _start_process,
    'read_process_output': _read_process,
    'stop_process': _stop_process,
    'list_processes': _list_processes,
    'git_log': _git_log,
    'git_commit': _git_commit,
    'git_branch': _git_branch,
    'run_tests': _run_tests,
    'lint': _lint,
}


def execute(name, args, resolve_path):
    args = args or {}
    try:
        if name in ('move_file', 'copy_file'):
            return _move_copy(name, args, resolve_path)
        handler = HANDLERS.get(name)
        if handler is None:
            return None
        return handler(args, resolve_path)
    except Exception as e:
        return f'Error in {name}: {e}'
