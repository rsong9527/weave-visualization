"""Rich terminal interface for microbot.

Features:
  - Streaming output with markdown rendering
  - Slash commands (/help, /clear, /save, /load, /history, /config, /model, /exit)
  - Tool call visualization
  - Color-coded output
  - Session auto-save
"""

import sys
import time
import signal
import shutil
from typing import Optional

from microbot.config import Config
from microbot.agent import (
    Agent, AgentEvent, TextDelta, TextComplete,
    ToolCallStart, ToolCallResult, ErrorEvent, ThinkingEvent,
)
from microbot.tools import ToolRegistry
from microbot.memory import Memory
from microbot.llm import Message
from microbot.utils import (
    generate_session_id, truncate, format_duration,
    estimate_tokens, word_count,
)


# =========================================================================
# ANSI color helpers (no dependency on 'rich' — stay lightweight!)
# =========================================================================

class Colors:
    """ANSI escape code color definitions."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


C = Colors


def styled(text: str, *styles: str) -> str:
    """Apply ANSI styles to text."""
    prefix = "".join(styles)
    return f"{prefix}{text}{C.RESET}" if prefix else text


# =========================================================================
# Banner & Help
# =========================================================================

BANNER = f"""
{styled("╔══════════════════════════════════════════════════════╗", C.CYAN)}
{styled("║", C.CYAN)}  {styled("🤖 microbot", C.BOLD, C.BRIGHT_CYAN)}  {styled("Ultra-Lightweight AI Assistant", C.DIM)}     {styled("║", C.CYAN)}
{styled("║", C.CYAN)}  {styled("~2000 lines of pure Python", C.DIM)}                       {styled("║", C.CYAN)}
{styled("║", C.CYAN)}  {styled("Type /help for commands, /exit to quit", C.DIM)}            {styled("║", C.CYAN)}
{styled("╚══════════════════════════════════════════════════════╝", C.CYAN)}
"""

HELP_TEXT = f"""
{styled("Commands:", C.BOLD, C.YELLOW)}

  {styled("/help", C.GREEN)}       Show this help message
  {styled("/clear", C.GREEN)}      Clear conversation history
  {styled("/save", C.GREEN)}       Save current session
  {styled("/load", C.GREEN)} {styled("<id>", C.DIM)}  Load a saved session
  {styled("/history", C.GREEN)}    List saved sessions
  {styled("/search", C.GREEN)} {styled("<q>", C.DIM)} Search sessions
  {styled("/delete", C.GREEN)} {styled("<id>", C.DIM)} Delete a saved session
  {styled("/model", C.GREEN)} {styled("[name]", C.DIM)} Show or change current model
  {styled("/config", C.GREEN)}     Show current configuration
  {styled("/tokens", C.GREEN)}     Show token usage estimate
  {styled("/tools", C.GREEN)}      List available tools
  {styled("/export", C.GREEN)} {styled("<f>", C.DIM)}  Export conversation to file
  {styled("/exit", C.GREEN)}       Exit microbot (also: Ctrl+D)
  {styled("/quit", C.GREEN)}       Same as /exit

{styled("Tips:", C.BOLD, C.YELLOW)}
  - Multiline input: end a line with \\\\ to continue
  - Paste code blocks directly — they work fine
  - The assistant can call tools automatically when needed
"""


# =========================================================================
# CLI Application
# =========================================================================

class MicrobotCLI:
    """Main CLI application."""

    def __init__(self):
        self.config = Config.load()
        self.config.ensure_dirs()
        self.registry = ToolRegistry()
        self.registry.register_defaults()
        self.agent = Agent(self.config, self.registry)
        self.memory = Memory()
        self.session_id = generate_session_id()
        self.term_width = shutil.get_terminal_size((80, 24)).columns
        self._interrupted = False

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the interactive session."""
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._handle_interrupt)

        print(BANNER)
        self._show_status()

        # Validate config
        warnings = self.config.validate()
        for w in warnings:
            print(styled(f"  ⚠ {w}", C.YELLOW))
        if warnings:
            print()

        try:
            self._loop()
        except (EOFError, KeyboardInterrupt):
            print()
        finally:
            self._auto_save()
            self.memory.close()
            print(styled("\n  👋 Goodbye!\n", C.DIM))

    def _loop(self) -> None:
        """Main input loop."""
        while True:
            try:
                user_input = self._get_input()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                should_exit = self._handle_command(user_input)
                if should_exit:
                    break
                continue

            # Process with agent
            self._process_input(user_input)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def _get_input(self) -> str:
        """Read user input, supporting multiline with trailing backslash."""
        prompt = styled("\n  You > ", C.BOLD, C.GREEN)
        try:
            line = input(prompt).rstrip()
        except EOFError:
            raise

        lines = [line]
        # Support multiline with trailing backslash
        while lines[-1].endswith("\\"):
            lines[-1] = lines[-1][:-1]  # Remove trailing backslash
            try:
                continuation = input(styled("  ... > ", C.DIM))
                lines.append(continuation.rstrip())
            except EOFError:
                break

        return "\n".join(lines).strip()

    # ------------------------------------------------------------------
    # Agent interaction
    # ------------------------------------------------------------------

    def _process_input(self, user_input: str) -> None:
        """Send input to agent and render events."""
        self._interrupted = False
        start_time = time.monotonic()
        first_token = True

        for event in self.agent.run(user_input):
            if self._interrupted:
                print(styled("\n  [interrupted]", C.DIM))
                break

            if isinstance(event, ThinkingEvent):
                print(styled(f"\n  ⏳ {event.status}", C.DIM), end="", flush=True)

            elif isinstance(event, TextDelta):
                if first_token:
                    # Clear the "Thinking..." line and start assistant output
                    print(f"\r{' ' * self.term_width}\r", end="")
                    print(styled("  Bot > ", C.BOLD, C.BLUE), end="", flush=True)
                    first_token = False
                sys.stdout.write(event.text)
                sys.stdout.flush()

            elif isinstance(event, TextComplete):
                if first_token:
                    # Non-streaming mode: print all at once
                    print(f"\r{' ' * self.term_width}\r", end="")
                    print(styled("  Bot > ", C.BOLD, C.BLUE) + event.full_text)
                else:
                    print()  # Newline after streaming

            elif isinstance(event, ToolCallStart):
                self._render_tool_start(event)

            elif isinstance(event, ToolCallResult):
                self._render_tool_result(event)

            elif isinstance(event, ErrorEvent):
                print(f"\r{' ' * self.term_width}\r", end="")
                print(styled(f"  ❌ {event.message}", C.RED))

        elapsed = int((time.monotonic() - start_time) * 1000)
        print(styled(f"  [{format_duration(elapsed)}]", C.DIM))

    # ------------------------------------------------------------------
    # Tool rendering
    # ------------------------------------------------------------------

    def _render_tool_start(self, event: ToolCallStart) -> None:
        """Render tool call start."""
        print(f"\r{' ' * self.term_width}\r", end="")
        args_preview = ", ".join(f"{k}={truncate(repr(v), 40)}" for k, v in event.arguments.items())
        print(styled(f"  🔧 {event.tool_name}", C.YELLOW, C.BOLD) +
              styled(f"({args_preview})", C.DIM))

    def _render_tool_result(self, event: ToolCallResult) -> None:
        """Render tool call result."""
        result_preview = truncate(event.result.replace("\n", " "), 120)
        duration = format_duration(event.duration_ms)
        status = styled("✓", C.GREEN) if not event.result.startswith("[Error]") else styled("✗", C.RED)
        print(styled(f"  {status} ", C.DIM) +
              styled(f"Result ", C.DIM) +
              styled(f"({duration}): ", C.DIM) +
              styled(result_preview, C.DIM))

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    def _handle_command(self, cmd: str) -> bool:
        """Handle a slash command. Returns True if should exit."""
        parts = cmd.strip().split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/help": lambda: print(HELP_TEXT),
            "/clear": self._cmd_clear,
            "/save": self._cmd_save,
            "/load": lambda: self._cmd_load(arg),
            "/history": self._cmd_history,
            "/search": lambda: self._cmd_search(arg),
            "/delete": lambda: self._cmd_delete(arg),
            "/model": lambda: self._cmd_model(arg),
            "/config": self._cmd_config,
            "/tokens": self._cmd_tokens,
            "/tools": self._cmd_tools,
            "/export": lambda: self._cmd_export(arg),
            "/exit": lambda: None,
            "/quit": lambda: None,
        }

        if command in ("/exit", "/quit"):
            return True

        handler = handlers.get(command)
        if handler:
            handler()
        else:
            print(styled(f"  Unknown command: {command}. Type /help for available commands.", C.RED))

        return False

    def _cmd_clear(self) -> None:
        self.agent.clear()
        self.session_id = generate_session_id()
        print(styled("  ✓ Conversation cleared, new session started.", C.GREEN))

    def _cmd_save(self) -> None:
        messages = self.agent.get_messages()
        if len(messages) <= 1:  # Only system prompt
            print(styled("  Nothing to save.", C.YELLOW))
            return
        self.memory.save_messages(self.session_id, messages)
        print(styled(f"  ✓ Session saved: {self.session_id[:16]}...", C.GREEN))

    def _cmd_load(self, session_id: str) -> None:
        if not session_id:
            print(styled("  Usage: /load <session_id>", C.YELLOW))
            print(styled("  Use /history to see available sessions.", C.DIM))
            return
        # Support partial ID matching
        sessions = self.memory.list_sessions(limit=100)
        match = None
        for s in sessions:
            if s.session_id.startswith(session_id):
                match = s
                break
        if not match:
            print(styled(f"  Session not found: {session_id}", C.RED))
            return
        messages = self.memory.load_messages(match.session_id)
        if not messages:
            print(styled("  Session is empty.", C.YELLOW))
            return
        self.agent.set_messages(messages)
        self.session_id = match.session_id
        print(styled(f"  ✓ Loaded session: {match.title} ({match.message_count} messages)", C.GREEN))

    def _cmd_history(self) -> None:
        sessions = self.memory.list_sessions(limit=20)
        if not sessions:
            print(styled("  No saved sessions.", C.DIM))
            return
        print(styled("\n  Recent sessions:", C.BOLD))
        for s in sessions:
            sid = styled(s.session_id[:16], C.CYAN)
            title = styled(truncate(s.title, 40), C.WHITE)
            meta = styled(f"({s.message_count} msgs, {s.updated_at})", C.DIM)
            print(f"    {sid}  {title}  {meta}")
        print()

    def _cmd_search(self, query: str) -> None:
        if not query:
            print(styled("  Usage: /search <query>", C.YELLOW))
            return
        results = self.memory.search_sessions(query)
        if not results:
            print(styled(f"  No sessions matching '{query}'.", C.DIM))
            return
        print(styled(f"\n  Results for '{query}':", C.BOLD))
        for s in results:
            sid = styled(s.session_id[:16], C.CYAN)
            title = styled(truncate(s.title, 40), C.WHITE)
            print(f"    {sid}  {title}")
        print()

    def _cmd_delete(self, session_id: str) -> None:
        if not session_id:
            print(styled("  Usage: /delete <session_id>", C.YELLOW))
            return
        sessions = self.memory.list_sessions(limit=100)
        for s in sessions:
            if s.session_id.startswith(session_id):
                self.memory.delete_session(s.session_id)
                print(styled(f"  ✓ Deleted session: {s.title}", C.GREEN))
                return
        print(styled(f"  Session not found: {session_id}", C.RED))

    def _cmd_model(self, model_name: str) -> None:
        if not model_name:
            print(styled(f"  Current model: {self.config.llm.model}", C.CYAN))
            print(styled(f"  Provider: {self.config.llm.provider}", C.DIM))
            return
        self.config.llm.model = model_name
        # Auto-detect provider from model name
        if model_name.startswith("claude"):
            self.config.llm.provider = "anthropic"
        elif model_name.startswith(("gpt", "o1", "o3")):
            self.config.llm.provider = "openai"
        self.agent = Agent(self.config, self.registry)
        print(styled(f"  ✓ Model changed to: {model_name} ({self.config.llm.provider})", C.GREEN))

    def _cmd_config(self) -> None:
        print(styled("\n  Configuration:", C.BOLD))
        print(styled(f"    Provider:    {self.config.llm.provider}", C.WHITE))
        print(styled(f"    Model:       {self.config.llm.model}", C.WHITE))
        base = self.config.llm.base_url or "(default)"
        print(styled(f"    Base URL:    {base}", C.WHITE))
        print(styled(f"    Temperature: {self.config.llm.temperature}", C.WHITE))
        print(styled(f"    Max tokens:  {self.config.llm.max_tokens}", C.WHITE))
        print(styled(f"    Stream:      {self.config.stream}", C.WHITE))
        print(styled(f"    Tools:       {self.config.tools_enabled}", C.WHITE))
        api_key = self.config.llm.api_key
        masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "(not set)"
        print(styled(f"    API Key:     {masked}", C.WHITE))
        print(styled(f"    Session:     {self.session_id[:16]}...", C.WHITE))
        print()

    def _cmd_tokens(self) -> None:
        messages = self.agent.get_messages()
        total = sum(estimate_tokens(m.content) for m in messages if m.content)
        user_count = sum(1 for m in messages if m.role == "user")
        assistant_count = sum(1 for m in messages if m.role == "assistant")
        tool_count = sum(1 for m in messages if m.role == "tool")
        print(styled("\n  Token usage estimate:", C.BOLD))
        print(styled(f"    Total tokens: ~{total}", C.WHITE))
        print(styled(f"    Messages:     {len(messages)} (user: {user_count}, assistant: {assistant_count}, tool: {tool_count})", C.WHITE))
        print()

    def _cmd_tools(self) -> None:
        print(styled("\n  Available tools:", C.BOLD))
        for name in self.registry.names():
            td = self.registry.get(name)
            print(styled(f"    🔧 {name}", C.YELLOW) + styled(f" — {td.description}", C.DIM))
        print()

    def _cmd_export(self, filename: str) -> None:
        if not filename:
            print(styled("  Usage: /export <filename>", C.YELLOW))
            return
        messages = self.agent.get_messages()
        lines = []
        for m in messages:
            if m.role == "system":
                continue
            role = m.role.upper()
            lines.append(f"[{role}]")
            if m.content:
                lines.append(m.content)
            if m.tool_calls:
                for tc in m.tool_calls:
                    fn = tc.get("function", {})
                    lines.append(f"  -> Tool call: {fn.get('name', '?')}({fn.get('arguments', '')})")
            lines.append("")
        try:
            from pathlib import Path
            Path(filename).write_text("\n".join(lines), encoding="utf-8")
            print(styled(f"  ✓ Exported to {filename}", C.GREEN))
        except Exception as e:
            print(styled(f"  ❌ Export failed: {e}", C.RED))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_status(self) -> None:
        """Show initial status line."""
        model = styled(self.config.llm.model, C.CYAN)
        provider = styled(self.config.llm.provider, C.DIM)
        tools = styled(f"{len(self.registry.names())} tools", C.GREEN) if self.config.tools_enabled else styled("no tools", C.DIM)
        print(f"  Model: {model} ({provider})  |  {tools}")
        print()

    def _auto_save(self) -> None:
        """Auto-save session on exit."""
        messages = self.agent.get_messages()
        if len(messages) > 1:  # More than just system prompt
            try:
                self.memory.save_messages(self.session_id, messages)
            except Exception:
                pass  # Silently fail on auto-save

    def _handle_interrupt(self, signum, frame) -> None:
        """Handle Ctrl+C."""
        self._interrupted = True
        print()  # Newline after ^C


# =========================================================================
# Entry point
# =========================================================================

def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="microbot",
        description="🤖 microbot — Ultra-lightweight personal AI assistant (~2000 LoC)",
    )
    parser.add_argument("--version", action="version", version=f"microbot 0.1.0")
    parser.add_argument("--model", "-m", help="LLM model to use")
    parser.add_argument("--provider", "-p", choices=["openai", "anthropic"], help="LLM provider")
    parser.add_argument("--no-tools", action="store_true", help="Disable tool calling")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming")
    parser.add_argument("--api-key", "-k", help="API key (prefer env vars instead)")
    parser.add_argument("--base-url", help="Custom API base URL")
    parser.add_argument("--exec", "-e", dest="execute", help="Execute a single prompt and exit")
    parser.add_argument("--init", action="store_true", help="Create default config file")

    args = parser.parse_args()

    # Handle --init
    if args.init:
        config = Config()
        config.save()
        print(styled(f"  ✓ Created config at {Config.load.__func__.__code__.co_filename}", C.GREEN))
        from microbot.config import CONFIG_FILE
        print(styled(f"  ✓ Config file: {CONFIG_FILE}", C.GREEN))
        return

    # Apply CLI overrides
    config = Config.load()
    if args.model:
        config.llm.model = args.model
    if args.provider:
        config.llm.provider = args.provider
    if args.no_tools:
        config.tools_enabled = False
    if args.no_stream:
        config.stream = False
    if args.api_key:
        config.llm.api_key = args.api_key
    if args.base_url:
        config.llm.base_url = args.base_url

    # Single-shot mode
    if args.execute:
        config.ensure_dirs()
        registry = ToolRegistry()
        registry.register_defaults()
        agent = Agent(config, registry)
        for event in agent.run(args.execute):
            if isinstance(event, TextDelta):
                sys.stdout.write(event.text)
                sys.stdout.flush()
            elif isinstance(event, TextComplete):
                if not config.stream:
                    print(event.full_text)
                else:
                    print()
            elif isinstance(event, ErrorEvent):
                print(styled(f"Error: {event.message}", C.RED), file=sys.stderr)
        return

    # Interactive mode
    cli = MicrobotCLI()
    cli.config = config  # Use the CLI-overridden config
    cli.agent = Agent(config, cli.registry)
    cli.run()


if __name__ == "__main__":
    main()
