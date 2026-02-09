"""Core agent loop with tool-calling support.

Implements a ReAct-style loop:
  1. Send messages to LLM
  2. If LLM requests tool calls, execute them
  3. Feed results back and repeat
  4. Until LLM produces a final text response
"""

import json
import time
from typing import Generator, Callable, Any
from dataclasses import dataclass, field

from microbot.config import Config
from microbot.llm import LLMProvider, Message, StreamChunk, LLMResponse
from microbot.tools import ToolRegistry
from microbot.prompts import build_system_prompt


# =========================================================================
# Agent events (yielded to the CLI for rendering)
# =========================================================================

@dataclass
class AgentEvent:
    """Base class for events emitted by the agent."""
    pass


@dataclass
class TextDelta(AgentEvent):
    """Incremental text from the assistant."""
    text: str = ""


@dataclass
class TextComplete(AgentEvent):
    """Full assistant text response is done."""
    full_text: str = ""


@dataclass
class ToolCallStart(AgentEvent):
    """Agent is about to call a tool."""
    tool_name: str = ""
    arguments: dict = field(default_factory=dict)
    call_id: str = ""


@dataclass
class ToolCallResult(AgentEvent):
    """Result from a tool execution."""
    tool_name: str = ""
    result: str = ""
    call_id: str = ""
    duration_ms: int = 0


@dataclass
class ErrorEvent(AgentEvent):
    """An error occurred."""
    message: str = ""


@dataclass
class ThinkingEvent(AgentEvent):
    """Agent is thinking / processing."""
    status: str = ""


# =========================================================================
# Agent
# =========================================================================

class Agent:
    """The core agent that orchestrates LLM calls and tool execution."""

    MAX_TOOL_ROUNDS = 15  # safety limit on consecutive tool-call rounds

    def __init__(self, config: Config, registry: ToolRegistry | None = None):
        self.config = config
        self.llm = LLMProvider(config.llm)
        self.registry = registry or ToolRegistry()
        self.messages: list[Message] = []
        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """Set system prompt as first message."""
        prompt = self.config.system_prompt or build_system_prompt(
            tools_enabled=self.config.tools_enabled,
            tool_names=self.registry.names(),
        )
        if self.messages and self.messages[0].role == "system":
            self.messages[0] = Message(role="system", content=prompt)
        else:
            self.messages.insert(0, Message(role="system", content=prompt))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, user_input: str) -> Generator[AgentEvent, None, None]:
        """Process a user message and yield events."""
        self.messages.append(Message(role="user", content=user_input))
        self._trim_history()

        tool_schemas = self.registry.schemas() if self.config.tools_enabled else None

        for round_num in range(self.MAX_TOOL_ROUNDS):
            yield ThinkingEvent(status="Thinking..." if round_num == 0 else "Processing tool results...")

            if self.config.stream:
                yield from self._stream_round(tool_schemas)
            else:
                yield from self._sync_round(tool_schemas)

            # Check if the last message has tool calls → need another round
            last = self.messages[-1] if self.messages else None
            if last and last.role == "assistant" and last.tool_calls:
                yield from self._execute_tools(last.tool_calls)
            else:
                break  # Final text response, we're done

    def set_messages(self, messages: list[Message]) -> None:
        """Replace conversation history (used when loading sessions)."""
        self.messages = messages
        self._setup_system_prompt()

    def clear(self) -> None:
        """Clear conversation history."""
        self.messages = []
        self._setup_system_prompt()

    def get_messages(self) -> list[Message]:
        """Return current message list."""
        return self.messages

    # ------------------------------------------------------------------
    # Streaming round
    # ------------------------------------------------------------------

    def _stream_round(self, tool_schemas) -> Generator[AgentEvent, None, None]:
        """Run one LLM call with streaming."""
        try:
            stream = self.llm.chat(self.messages, tools=tool_schemas, stream=True)
        except Exception as e:
            yield ErrorEvent(message=f"LLM API error: {e}")
            self.messages.append(Message(role="assistant", content=f"[Error: {e}]"))
            return

        full_text = ""
        collected_tool_calls: list | None = None

        try:
            for chunk in stream:
                if chunk.content:
                    full_text += chunk.content
                    yield TextDelta(text=chunk.content)

                if chunk.tool_calls_delta:
                    collected_tool_calls = chunk.tool_calls_delta

                if chunk.finish_reason == "stop" and not collected_tool_calls:
                    break
        except Exception as e:
            yield ErrorEvent(message=f"Stream error: {e}")
            if full_text:
                self.messages.append(Message(role="assistant", content=full_text))
            return

        # Build assistant message
        msg = Message(role="assistant", content=full_text, tool_calls=collected_tool_calls)
        self.messages.append(msg)

        if full_text and not collected_tool_calls:
            yield TextComplete(full_text=full_text)

    # ------------------------------------------------------------------
    # Non-streaming round
    # ------------------------------------------------------------------

    def _sync_round(self, tool_schemas) -> Generator[AgentEvent, None, None]:
        """Run one LLM call without streaming."""
        try:
            resp: LLMResponse = self.llm.chat(self.messages, tools=tool_schemas, stream=False)
        except Exception as e:
            yield ErrorEvent(message=f"LLM API error: {e}")
            self.messages.append(Message(role="assistant", content=f"[Error: {e}]"))
            return

        msg = Message(role="assistant", content=resp.content, tool_calls=resp.tool_calls)
        self.messages.append(msg)

        if resp.content:
            yield TextDelta(text=resp.content)
            yield TextComplete(full_text=resp.content)

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tools(self, tool_calls: list) -> Generator[AgentEvent, None, None]:
        """Execute tool calls and append results to messages."""
        for tc in tool_calls:
            call_id = tc.get("id", "")
            func_info = tc.get("function", {})
            name = func_info.get("name", "unknown")
            args_str = func_info.get("arguments", "{}")

            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}

            yield ToolCallStart(tool_name=name, arguments=args, call_id=call_id)

            start = time.monotonic()
            result = self.registry.call(name, args)
            elapsed = int((time.monotonic() - start) * 1000)

            # Truncate very long results
            if len(result) > 15_000:
                result = result[:15_000] + "\n... [truncated]"

            yield ToolCallResult(
                tool_name=name,
                result=result,
                call_id=call_id,
                duration_ms=elapsed,
            )

            self.messages.append(Message(
                role="tool",
                content=result,
                tool_call_id=call_id,
                name=name,
            ))

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def _trim_history(self) -> None:
        """Keep conversation within max_history limit."""
        max_msgs = self.config.max_history
        if max_msgs <= 0:
            return
        # Always keep the system message
        if len(self.messages) <= max_msgs + 1:
            return
        system = self.messages[0] if self.messages[0].role == "system" else None
        non_system = [m for m in self.messages if m.role != "system"]
        trimmed = non_system[-(max_msgs):]
        self.messages = ([system] if system else []) + trimmed
