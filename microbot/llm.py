"""LLM provider abstraction with streaming and tool-calling support.

Supported providers:
  - OpenAI  (and any OpenAI-compatible API)
  - Anthropic
"""

import json
import httpx
from dataclasses import dataclass, field
from typing import Generator, Any, Optional

from microbot.config import LLMConfig


# =========================================================================
# Message types
# =========================================================================

@dataclass
class Message:
    """A single conversation message."""
    role: str                       # system | user | assistant | tool
    content: str = ""
    tool_calls: list | None = None  # assistant → tool invocations
    tool_call_id: str | None = None # tool → response to which call
    name: str | None = None         # tool name (for tool responses)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_openai(self) -> dict:
        msg: dict[str, Any] = {"role": self.role, "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
            if not self.content:
                msg["content"] = None
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name and self.role == "tool":
            msg["name"] = self.name
        return msg

    def to_anthropic(self) -> dict | None:
        if self.role == "system":
            return None                     # handled via top-level "system" param

        if self.role == "tool":
            return {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": self.tool_call_id,
                    "content": self.content,
                }],
            }

        if self.tool_calls:
            blocks: list[dict] = []
            if self.content:
                blocks.append({"type": "text", "text": self.content})
            for tc in self.tool_calls:
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}
                blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": args,
                })
            return {"role": "assistant", "content": blocks}

        return {"role": self.role, "content": self.content or ""}

    def to_dict(self) -> dict:
        """Serialise for persistence."""
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(
            role=d["role"],
            content=d.get("content", ""),
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
        )


# =========================================================================
# Response / Streaming types
# =========================================================================

@dataclass
class StreamChunk:
    """A single streaming delta."""
    content: str = ""
    tool_calls_delta: list | None = None
    finish_reason: str | None = None


@dataclass
class LLMResponse:
    """Complete (non-streaming) LLM response."""
    content: str = ""
    tool_calls: list | None = None
    usage: dict | None = None


# =========================================================================
# Provider
# =========================================================================

class LLMProvider:
    """Unified LLM interface for OpenAI and Anthropic APIs."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = httpx.Client(timeout=120.0)

    def close(self):
        self.client.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> LLMResponse | Generator[StreamChunk, None, None]:
        if self.config.provider == "anthropic":
            return self._anthropic_chat(messages, tools, stream)
        return self._openai_chat(messages, tools, stream)

    # ==================================================================
    # OpenAI
    # ==================================================================

    def _openai_chat(self, messages, tools, stream):
        base = self.config.base_url or "https://api.openai.com/v1"
        url = f"{base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [m.to_openai() for m in messages],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if stream:
            return self._openai_stream(url, headers, payload)

        resp = self.client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        return LLMResponse(
            content=choice.get("content") or "",
            tool_calls=choice.get("tool_calls"),
            usage=data.get("usage"),
        )

    def _openai_stream(self, url, headers, payload) -> Generator[StreamChunk, None, None]:
        with self.client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            tool_calls_acc: dict[int, dict] = {}
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    # Yield accumulated tool calls
                    if tool_calls_acc:
                        merged = []
                        for idx in sorted(tool_calls_acc):
                            merged.append(tool_calls_acc[idx])
                        yield StreamChunk(tool_calls_delta=merged, finish_reason="tool_calls")
                    break
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                delta = chunk["choices"][0].get("delta", {})
                finish = chunk["choices"][0].get("finish_reason")

                # Accumulate tool call deltas
                if "tool_calls" in delta:
                    for tc_delta in delta["tool_calls"]:
                        idx = tc_delta["index"]
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": tc_delta.get("id", ""),
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        entry = tool_calls_acc[idx]
                        if tc_delta.get("id"):
                            entry["id"] = tc_delta["id"]
                        fn = tc_delta.get("function", {})
                        if fn.get("name"):
                            entry["function"]["name"] = fn["name"]
                        if fn.get("arguments"):
                            entry["function"]["arguments"] += fn["arguments"]

                content = delta.get("content") or ""
                if content:
                    yield StreamChunk(content=content)

                if finish and finish != "tool_calls":
                    yield StreamChunk(finish_reason=finish)

    # ==================================================================
    # Anthropic
    # ==================================================================

    def _anthropic_chat(self, messages, tools, stream):
        base = self.config.base_url or "https://api.anthropic.com"
        url = f"{base}/v1/messages"
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        system_text = ""
        api_msgs: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_text = m.content
                continue
            converted = m.to_anthropic()
            if not converted:
                continue
            # Merge consecutive same-role messages (Anthropic requirement)
            if api_msgs and api_msgs[-1]["role"] == converted["role"]:
                prev = api_msgs[-1]
                if isinstance(prev["content"], str):
                    prev["content"] = [{"type": "text", "text": prev["content"]}]
                new_content = converted["content"]
                if isinstance(new_content, str):
                    prev["content"].append({"type": "text", "text": new_content})
                elif isinstance(new_content, list):
                    prev["content"].extend(new_content)
            else:
                api_msgs.append(converted)

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": api_msgs,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if system_text:
            payload["system"] = system_text
        if tools:
            payload["tools"] = [self._tool_to_anthropic(t) for t in tools]

        if stream:
            payload["stream"] = True
            return self._anthropic_stream(url, headers, payload)

        resp = self.client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return self._parse_anthropic_response(data)

    def _parse_anthropic_response(self, data: dict) -> LLMResponse:
        content = ""
        tool_calls: list[dict] = []
        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block["input"]),
                    },
                })
        return LLMResponse(
            content=content,
            tool_calls=tool_calls or None,
            usage=data.get("usage"),
        )

    def _anthropic_stream(self, url, headers, payload) -> Generator[StreamChunk, None, None]:
        with self.client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            current_tool: dict | None = None
            accumulated_tools: list[dict] = []

            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                etype = data.get("type", "")

                if etype == "content_block_start":
                    block = data.get("content_block", {})
                    if block.get("type") == "tool_use":
                        current_tool = {
                            "id": block["id"],
                            "name": block["name"],
                            "args_buf": "",
                        }

                elif etype == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield StreamChunk(content=delta.get("text", ""))
                    elif delta.get("type") == "input_json_delta" and current_tool:
                        current_tool["args_buf"] += delta.get("partial_json", "")

                elif etype == "content_block_stop":
                    if current_tool:
                        accumulated_tools.append({
                            "id": current_tool["id"],
                            "type": "function",
                            "function": {
                                "name": current_tool["name"],
                                "arguments": current_tool["args_buf"],
                            },
                        })
                        current_tool = None

                elif etype == "message_stop":
                    if accumulated_tools:
                        yield StreamChunk(
                            tool_calls_delta=accumulated_tools,
                            finish_reason="tool_calls",
                        )
                    else:
                        yield StreamChunk(finish_reason="stop")

    @staticmethod
    def _tool_to_anthropic(tool: dict) -> dict:
        func = tool["function"]
        return {
            "name": func["name"],
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {
                "type": "object",
                "properties": {},
            }),
        }
