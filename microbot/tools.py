"""Tool system with decorator-based registration and built-in tools.

Usage:
    from microbot.tools import tool, ToolRegistry

    @tool(description="Read a file from disk")
    def read_file(path: str) -> str:
        ...

    registry = ToolRegistry()
    registry.register_defaults()     # register all built-in tools
    schemas = registry.schemas()     # OpenAI-format tool schemas
    result  = registry.call("read_file", {"path": "foo.txt"})
"""

import os
import io
import json
import math
import glob as glob_mod
import subprocess
import textwrap
import inspect
import traceback
import contextlib
from pathlib import Path
from typing import Any, Callable, get_type_hints
from dataclasses import dataclass, field


# =========================================================================
# Tool metadata
# =========================================================================

@dataclass
class ToolDef:
    """Metadata for a registered tool."""
    name: str
    description: str
    parameters: dict          # JSON Schema for parameters
    func: Callable[..., str]  # The actual callable


# =========================================================================
# Decorator
# =========================================================================

_TOOL_STORE: list[ToolDef] = []


def tool(description: str = "", name: str = ""):
    """Decorator to declare a function as a tool."""
    def decorator(fn: Callable) -> Callable:
        tool_name = name or fn.__name__
        tool_desc = description or (fn.__doc__ or "").strip().split("\n")[0]
        params = _build_schema(fn)
        _TOOL_STORE.append(ToolDef(
            name=tool_name,
            description=tool_desc,
            parameters=params,
            func=fn,
        ))
        return fn
    return decorator


def _python_type_to_json(tp) -> str:
    """Map Python type annotation to JSON Schema type string."""
    mapping = {str: "string", int: "integer", float: "number", bool: "boolean"}
    return mapping.get(tp, "string")


def _build_schema(fn: Callable) -> dict:
    """Build a JSON Schema 'parameters' object from function signature."""
    hints = get_type_hints(fn)
    sig = inspect.signature(fn)
    properties: dict[str, dict] = {}
    required: list[str] = []

    for pname, param in sig.parameters.items():
        ptype = hints.get(pname, str)
        prop: dict[str, Any] = {"type": _python_type_to_json(ptype)}

        # Extract per-param description from docstring (numpy style)
        doc = fn.__doc__ or ""
        for doc_line in doc.split("\n"):
            stripped = doc_line.strip()
            if stripped.startswith(f"{pname}:") or stripped.startswith(f"{pname} :"):
                prop["description"] = stripped.split(":", 1)[1].strip()

        properties[pname] = prop
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


# =========================================================================
# Registry
# =========================================================================

class ToolRegistry:
    """Manages available tools and dispatches calls."""

    def __init__(self):
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool_def: ToolDef) -> None:
        self._tools[tool_def.name] = tool_def

    def register_defaults(self) -> None:
        """Register all built-in tools declared with @tool."""
        for td in _TOOL_STORE:
            self.register(td)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict]:
        """Return OpenAI-format tool schemas for all registered tools."""
        result = []
        for td in self._tools.values():
            result.append({
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": td.parameters,
                },
            })
        return result

    def call(self, name: str, arguments: dict) -> str:
        """Execute a tool by name with given arguments, return string result."""
        td = self._tools.get(name)
        if not td:
            return f"[Error] Unknown tool: {name}"
        try:
            result = td.func(**arguments)
            return str(result) if result is not None else "(done)"
        except Exception as exc:
            return f"[Error] {type(exc).__name__}: {exc}"


# =========================================================================
# Built-in tools
# =========================================================================

@tool(description="Read the contents of a file from disk")
def read_file(path: str) -> str:
    """Read a file and return its contents.
    path: Path to the file to read
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"[Error] File not found: {p}"
    if not p.is_file():
        return f"[Error] Not a file: {p}"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 50_000:
            return content[:50_000] + f"\n\n... [truncated, total {len(content)} chars]"
        return content
    except Exception as e:
        return f"[Error] {e}"


@tool(description="Write content to a file (creates parent directories if needed)")
def write_file(path: str, content: str) -> str:
    """Write content to a file.
    path: Path to the file to write
    content: Content to write
    """
    p = Path(path).expanduser().resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {p}"
    except Exception as e:
        return f"[Error] {e}"


@tool(description="Append content to the end of a file")
def append_file(path: str, content: str) -> str:
    """Append content to a file.
    path: Path to the file
    content: Content to append
    """
    p = Path(path).expanduser().resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(content)
        return f"Appended {len(content)} chars to {p}"
    except Exception as e:
        return f"[Error] {e}"


@tool(description="List files and directories at a given path")
def list_directory(path: str = ".") -> str:
    """List directory contents.
    path: Directory path (default: current directory)
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"[Error] Path not found: {p}"
    if not p.is_dir():
        return f"[Error] Not a directory: {p}"
    entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    lines = []
    for entry in entries[:200]:  # cap output
        prefix = "📁 " if entry.is_dir() else "📄 "
        size = ""
        if entry.is_file():
            sz = entry.stat().st_size
            if sz < 1024:
                size = f" ({sz}B)"
            elif sz < 1024 * 1024:
                size = f" ({sz/1024:.1f}KB)"
            else:
                size = f" ({sz/1024/1024:.1f}MB)"
        lines.append(f"{prefix}{entry.name}{size}")
    if len(list(p.iterdir())) > 200:
        lines.append(f"... and {len(list(p.iterdir())) - 200} more entries")
    return "\n".join(lines) if lines else "(empty directory)"


@tool(description="Search for files matching a glob pattern")
def search_files(pattern: str, directory: str = ".") -> str:
    """Search for files using glob.
    pattern: Glob pattern (e.g. '**/*.py')
    directory: Base directory to search from
    """
    base = Path(directory).expanduser().resolve()
    try:
        matches = sorted(base.glob(pattern))[:100]
        if not matches:
            return f"No files matching '{pattern}' in {base}"
        lines = [str(m.relative_to(base)) for m in matches]
        result = "\n".join(lines)
        if len(list(base.glob(pattern))) > 100:
            result += f"\n... (showing first 100 of {len(list(base.glob(pattern)))} matches)"
        return result
    except Exception as e:
        return f"[Error] {e}"


@tool(description="Search for text content in files using grep-like functionality")
def search_content(pattern: str, directory: str = ".", file_pattern: str = "*") -> str:
    """Search file contents for a pattern.
    pattern: Text or regex pattern to search for
    directory: Base directory to search in
    file_pattern: Glob pattern to filter files (e.g. '*.py')
    """
    base = Path(directory).expanduser().resolve()
    results: list[str] = []
    count = 0
    try:
        for fpath in sorted(base.rglob(file_pattern)):
            if not fpath.is_file() or fpath.stat().st_size > 1_000_000:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except (PermissionError, OSError):
                continue
            for i, line in enumerate(text.split("\n"), 1):
                if pattern.lower() in line.lower():
                    rel = fpath.relative_to(base)
                    results.append(f"{rel}:{i}: {line.rstrip()}")
                    count += 1
                    if count >= 50:
                        results.append("... (truncated at 50 matches)")
                        return "\n".join(results)
        return "\n".join(results) if results else f"No matches for '{pattern}'"
    except Exception as e:
        return f"[Error] {e}"


@tool(description="Execute a shell command and return the output")
def shell_exec(command: str, timeout: int = 30) -> str:
    """Run a shell command.
    command: The shell command to execute
    timeout: Maximum execution time in seconds (default 30)
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=min(timeout, 120),
            cwd=os.getcwd(),
        )
        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr}")
        output = "\n".join(output_parts).strip()
        if result.returncode != 0:
            output = f"[exit code: {result.returncode}]\n{output}"
        # Truncate very long output
        if len(output) > 30_000:
            output = output[:30_000] + "\n... [truncated]"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[Error] Command timed out after {timeout}s"
    except Exception as e:
        return f"[Error] {e}"


@tool(description="Execute Python code and return the output")
def python_exec(code: str) -> str:
    """Execute Python code in a sandboxed environment.
    code: Python code to execute
    """
    stdout_capture = io.StringIO()
    local_vars: dict[str, Any] = {}
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(compile(code, "<microbot>", "exec"), {"__builtins__": __builtins__}, local_vars)
        output = stdout_capture.getvalue()
        # If no print output, show the last expression value
        if not output and local_vars:
            last_key = list(local_vars.keys())[-1]
            if not last_key.startswith("_"):
                output = repr(local_vars[last_key])
        return output.strip() if output else "(executed, no output)"
    except Exception:
        error = traceback.format_exc()
        stdout = stdout_capture.getvalue()
        parts = []
        if stdout:
            parts.append(stdout)
        parts.append(f"[Error]\n{error}")
        return "\n".join(parts)


@tool(description="Evaluate a mathematical expression safely")
def calculator(expression: str) -> str:
    """Evaluate a math expression.
    expression: Mathematical expression (e.g. '2**10 + sqrt(144)')
    """
    # Provide safe math functions
    safe_ns = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "len": len, "pow": pow, "int": int, "float": float,
        "pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf,
        "sqrt": math.sqrt, "log": math.log, "log2": math.log2, "log10": math.log10,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "ceil": math.ceil, "floor": math.floor,
        "factorial": math.factorial, "gcd": math.gcd,
        "degrees": math.degrees, "radians": math.radians,
    }
    try:
        result = eval(expression, {"__builtins__": {}}, safe_ns)
        return str(result)
    except Exception as e:
        return f"[Error] {e}"


@tool(description="Fetch content from a URL via HTTP GET")
def web_fetch(url: str, max_length: int = 20000) -> str:
    """Fetch a webpage or API endpoint.
    url: The URL to fetch
    max_length: Maximum response length to return (default 20000)
    """
    try:
        import httpx as _httpx
        with _httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={
                "User-Agent": "microbot/0.1 (lightweight AI assistant)",
                "Accept": "text/html,application/json,text/plain,*/*",
            })
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            if "application/json" in content_type:
                try:
                    body = json.dumps(resp.json(), indent=2, ensure_ascii=False)
                except Exception:
                    body = resp.text
            else:
                body = resp.text

            # Basic HTML stripping for readability
            if "text/html" in content_type:
                body = _strip_html(body)

            if len(body) > max_length:
                body = body[:max_length] + "\n... [truncated]"
            return body
    except Exception as e:
        return f"[Error] {e}"


@tool(description="Get current date, time, and working directory info")
def get_system_info() -> str:
    """Return current system information."""
    import datetime
    now = datetime.datetime.now()
    info_lines = [
        f"Date: {now.strftime('%Y-%m-%d %A')}",
        f"Time: {now.strftime('%H:%M:%S')}",
        f"CWD:  {os.getcwd()}",
        f"Home: {Path.home()}",
        f"OS:   {os.name}",
    ]
    try:
        import platform
        info_lines.append(f"Platform: {platform.platform()}")
    except ImportError:
        pass
    return "\n".join(info_lines)


# =========================================================================
# HTML helpers
# =========================================================================

def _strip_html(html: str) -> str:
    """Very basic HTML tag removal for readable text extraction."""
    import re
    # Remove script and style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common entities
    for entity, char in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                         ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]:
        text = text.replace(entity, char)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
