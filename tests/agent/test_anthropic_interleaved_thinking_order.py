"""Regression guard: preserve interleaved thinking block order on direct Anthropic.

With ``interleaved-thinking-2025-05-14`` enabled (always on for the OAuth /
Claude-Code path), Claude emits multiple ``thinking`` blocks interleaved with
``tool_use`` within a single assistant turn, e.g.::

    [thinking_1, tool_use_1, thinking_2, tool_use_2]

``transports/anthropic.py::normalize_response`` flattens the response into
parallel buckets (text -> content, thinking -> reasoning_details, tool_use ->
tool_calls), discarding the relative order between thinking and tool_use.  On
replay, ``_convert_assistant_message`` rebuilds the turn grouped by type::

    [thinking_1, thinking_2, tool_use_1, tool_use_2]   # WRONG

Anthropic signs the thinking sequence against its original position and rejects
the reordered turn with HTTP 400::

    messages.N.content.M: `thinking` or `redacted_thinking` blocks in the latest
    assistant message cannot be modified. These blocks must remain as they were
    in the original response.

The fix carries the native block order on the assistant message under
``anthropic_ordered_content`` and replays it verbatim.

See systematic-debugging session 2026-05-28.
"""

from __future__ import annotations


class TestInterleavedThinkingOrderPreserved:
    """convert_messages_to_anthropic must replay interleaved turns verbatim."""

    def _interleaved_history(self):
        return [
            {"role": "user", "content": "do two things"},
            {
                "role": "assistant",
                "content": "",
                # Native block order as emitted by Claude (interleaved).
                "anthropic_ordered_content": [
                    {"type": "thinking", "thinking": "plan A", "signature": "sigA"},
                    {"type": "tool_use", "id": "call_1", "name": "f", "input": {}},
                    {"type": "thinking", "thinking": "plan B", "signature": "sigB"},
                    {"type": "tool_use", "id": "call_2", "name": "g", "input": {}},
                ],
                # Flattened buckets that the storage layer also keeps — these
                # are what the buggy rebuild path consumes (grouped by type).
                "reasoning_details": [
                    {"type": "thinking", "thinking": "plan A", "signature": "sigA"},
                    {"type": "thinking", "thinking": "plan B", "signature": "sigB"},
                ],
                "tool_calls": [
                    {"id": "call_1", "type": "function",
                     "function": {"name": "f", "arguments": "{}"}},
                    {"id": "call_2", "type": "function",
                     "function": {"name": "g", "arguments": "{}"}},
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "r1"},
            {"role": "tool", "tool_call_id": "call_2", "content": "r2"},
        ]

    def test_interleaved_order_preserved_on_direct_anthropic(self) -> None:
        from agent.anthropic_adapter import convert_messages_to_anthropic

        _system, converted = convert_messages_to_anthropic(
            self._interleaved_history(), base_url=None, model="claude-opus-4-8"
        )

        assistant_msg = next(m for m in converted if m["role"] == "assistant")
        seq = [b.get("type") for b in assistant_msg["content"] if isinstance(b, dict)]
        assert seq == ["thinking", "tool_use", "thinking", "tool_use"], (
            "interleaved thinking/tool_use order must be replayed verbatim; "
            f"grouping by type triggers HTTP 400. got {seq}"
        )

    def test_thinking_signatures_kept_in_place(self) -> None:
        from agent.anthropic_adapter import convert_messages_to_anthropic

        _system, converted = convert_messages_to_anthropic(
            self._interleaved_history(), base_url=None, model="claude-opus-4-8"
        )

        content = next(m for m in converted if m["role"] == "assistant")["content"]
        thinking = [b for b in content if isinstance(b, dict) and b.get("type") == "thinking"]
        assert [b["signature"] for b in thinking] == ["sigA", "sigB"]
        # The first thinking must precede the first tool_use (interleaving).
        assert content[0]["type"] == "thinking" and content[0]["signature"] == "sigA"
        assert content[1]["type"] == "tool_use" and content[1]["id"] == "call_1"
