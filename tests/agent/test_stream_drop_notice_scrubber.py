"""Regression tests: stream-drop notices must survive an unterminated <think>.

When a stream dies mid tool-call, ``_interruptible_streaming_api_call`` tells the
user about it in one of two ways:

  * retries exhausted / non-transient error -> "Stream stalled mid tool-call
    (<names>); the action was not executed."
  * transient error, retry available       -> "Connection dropped mid tool-call;
    reconnecting..."

Both notices are fired through ``AIAgent._fire_stream_delta``, which routes every
delta through the stateful ``StreamingThinkScrubber``.  A reasoning model that
emitted ``<think>`` and then died before ``</think>`` leaves that scrubber
latched inside the block, and the accumulator cannot un-latch it: once tool-call
deltas start arriving, later content is written straight to the display callback
and never reaches the scrubber, so the closing tag can no longer land there
either.  Everything fed to a latched scrubber is dropped as reasoning content,
``_fire_stream_delta`` returns early on the resulting empty string, and the
notice disappears.  The user is left believing the tool ran -- often staring at
a completely empty reply.

The fix flushes the scrubbers via ``_reset_stream_delivery_tracking()`` before
firing either notice.  These tests drive the real streaming loop with the real
``_fire_stream_delta`` and the real scrubbers -- no stubbed delta sink -- so
they fail on the pre-fix code instead of passing vacuously.

Each site is covered twice: the ``<think>`` case (the bug) and a plain-text
control (the case that already worked).  The control is what makes the pair
discriminating -- it proves the harness can deliver a notice at all.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

import run_agent
from agent.memory_manager import StreamingContextScrubber
from agent.think_scrubber import StreamingThinkScrubber


STALL_NOTICE = "the action was not executed"
RECONNECT_NOTICE = "reconnecting"

# The delta that opens a reasoning block and never closes it.  Everything after
# it is reasoning content the user must never see.
THINK_PREAMBLE = "<think>\nI should call write_file to save the report"
VISIBLE_PREAMBLE = "Let me write the audit: "
REASONING_LEAK = "I should call write_file"


class _StallError(RuntimeError):
    """Non-transient mid-stream failure: no silent retry, straight to the stub."""


def _chunk(content=None, tool_calls=None, finish_reason=None):
    """A mock chunk shaped like OpenAI's ChatCompletionChunk."""
    delta = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        reasoning_content=None,
        reasoning=None,
    )
    choice = SimpleNamespace(index=0, delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model=None, usage=None)


def _tool_delta(index=0, tc_id=None, name=None, arguments=None):
    return SimpleNamespace(
        index=index, id=tc_id, function=SimpleNamespace(name=name, arguments=arguments),
    )


def _build_agent():
    """A real AIAgent wired with the real scrubbers and a capturing delta sink.

    ``_fire_stream_delta`` is deliberately NOT stubbed: the whole point is to
    exercise the scrubber chain it runs deltas through.
    """
    agent = run_agent.AIAgent(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        model="test/model",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False

    # Guard the premise of these tests: if the agent ever stops wiring the real
    # scrubbers, the deliveries below would pass for the wrong reason.
    assert isinstance(agent._stream_think_scrubber, StreamingThinkScrubber)
    assert isinstance(agent._stream_context_scrubber, StreamingContextScrubber)

    delivered: list[str] = []
    agent.stream_delta_callback = delivered.append
    return agent, delivered


def _run_stream(agent, stream_factory, monkeypatch, retries):
    with patch("run_agent.AIAgent._replace_primary_openai_client"), patch(
        "run_agent.AIAgent._create_request_openai_client"
    ) as mock_create, patch("run_agent.AIAgent._close_request_openai_client"):
        client = MagicMock()
        client.chat.completions.create.side_effect = stream_factory
        mock_create.return_value = client
        monkeypatch.setenv("HERMES_STREAM_RETRIES", retries)
        return agent._interruptible_streaming_api_call({})


# -- Site 1: "Stream stalled mid tool-call" (retries exhausted / hard error) --


def _stalling_stream(preamble):
    """Text, then a named tool call, then the stream dies. No retry."""

    def factory(*args, **kwargs):
        def gen():
            yield _chunk(content=preamble)
            yield _chunk(
                tool_calls=[_tool_delta(index=0, tc_id="call_1", name="write_file")]
            )
            yield _chunk(tool_calls=[_tool_delta(index=0, arguments='{"path": "/tmp/x", ')])
            raise _StallError("simulated upstream stall")

        return gen()

    return factory


def test_stall_notice_reaches_user_after_visible_text(monkeypatch):
    """Control: no reasoning block open, so the notice was always delivered."""
    agent, delivered = _build_agent()
    _run_stream(agent, _stalling_stream(VISIBLE_PREAMBLE), monkeypatch, "0")

    joined = "".join(delivered)
    assert STALL_NOTICE in joined, (
        f"Control case regressed: the dropped-tool-call warning must reach the "
        f"user when no reasoning block is open. delivered={delivered!r}"
    )
    assert "write_file" in joined
    # The flush empties the streamed-text buffer, which makes _fire_stream_delta
    # treat the warning as the turn's first delta and strip its leading
    # newlines.  The warning must still open its own paragraph rather than glue
    # onto the preamble.
    assert f"{VISIBLE_PREAMBLE}\n\n⚠" in joined, (
        f"The warning lost its paragraph break and ran into the preamble: "
        f"{joined!r}"
    )


def test_stall_notice_reaches_user_when_stream_died_inside_think(monkeypatch):
    """The bug: the stream died inside <think>, so the notice was swallowed.

    Pre-fix the delta sink receives nothing at all -- the user is never told the
    tool call did not run, and (because the reasoning text was correctly hidden)
    sees an empty reply.
    """
    agent, delivered = _build_agent()
    _run_stream(agent, _stalling_stream(THINK_PREAMBLE), monkeypatch, "0")

    joined = "".join(delivered)
    assert STALL_NOTICE in joined, (
        f"Stream died inside an unterminated <think> block, so the think "
        f"scrubber was still latched when the dropped-tool-call warning was "
        f"fired and swallowed it. The user is told nothing and assumes the tool "
        f"ran. delivered={delivered!r}"
    )
    assert "write_file" in joined
    # Flushing the scrubber must not turn into leaking the reasoning it held.
    assert REASONING_LEAK not in joined, (
        f"Reasoning content leaked to the user while delivering the warning: "
        f"{joined!r}"
    )


# -- Site 2: "Connection dropped mid tool-call; reconnecting" (silent retry) --


def _dropped_then_recovered_stream(preamble):
    """First attempt drops mid tool-call (transient); the retry succeeds."""
    attempts = {"n": 0}

    def factory(*args, **kwargs):
        attempts["n"] += 1

        def first():
            yield _chunk(content=preamble)
            yield _chunk(
                tool_calls=[_tool_delta(index=0, tc_id="call_1", name="write_file")]
            )
            raise httpx.RemoteProtocolError("peer closed connection")

        def second():
            yield _chunk(content="Saving now. ")
            yield _chunk(
                tool_calls=[_tool_delta(index=0, tc_id="call_1", name="write_file")]
            )
            yield _chunk(
                tool_calls=[
                    _tool_delta(
                        index=0, arguments='{"path": "/tmp/x", "content": "hi"}'
                    )
                ]
            )
            yield _chunk(finish_reason="tool_calls")

        return first() if attempts["n"] == 1 else second()

    return factory, attempts


def test_reconnect_notice_reaches_user_after_visible_text(monkeypatch):
    """Control: no reasoning block open, so the marker was always delivered."""
    agent, delivered = _build_agent()
    factory, attempts = _dropped_then_recovered_stream(VISIBLE_PREAMBLE)
    response = _run_stream(agent, factory, monkeypatch, "2")

    assert attempts["n"] == 2, f"Expected a silent retry, got {attempts['n']} attempt(s)"
    assert response.choices[0].message.tool_calls
    joined = "".join(delivered)
    assert RECONNECT_NOTICE in joined.lower(), (
        f"Control case regressed: the reconnect marker explains why the preamble "
        f"is about to be re-streamed. delivered={delivered!r}"
    )


def test_reconnect_notice_reaches_user_when_stream_died_inside_think(monkeypatch):
    """The bug: the marker was fired before the scrubbers were flushed.

    The retry re-streams its preamble, so pre-fix the user sees the duplicated
    text appear with no explanation for it.
    """
    agent, delivered = _build_agent()
    factory, attempts = _dropped_then_recovered_stream(THINK_PREAMBLE)
    response = _run_stream(agent, factory, monkeypatch, "2")

    assert attempts["n"] == 2, f"Expected a silent retry, got {attempts['n']} attempt(s)"
    assert response.choices[0].message.tool_calls
    joined = "".join(delivered)
    assert RECONNECT_NOTICE in joined.lower(), (
        f"Connection dropped inside an unterminated <think> block: the reconnect "
        f"marker was fired into the still-latched think scrubber and dropped, so "
        f"the retry's re-streamed preamble arrives unexplained. "
        f"delivered={delivered!r}"
    )
    assert REASONING_LEAK not in joined, (
        f"Reasoning content leaked to the user while delivering the marker: "
        f"{joined!r}"
    )
