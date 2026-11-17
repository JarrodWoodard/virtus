"""Answer-first: a per-profile rewrite of the two sentences that turn a question into work.

Owner ruling, 2026-11-16: the default profile's wording must NOT change. Only profiles that opt in
(`agent.prompt.answer_first`) get the rewrite. These tests pin both halves.
"""

from __future__ import annotations

import pytest

from agent.prompt_builder import (
    TOOL_USE_ENFORCEMENT_GUIDANCE,
    apply_answer_first,
    execution_guidance_text,
)

UPSTREAM_RESPONSE_SENTENCE = (
    "Every response should either (a) contain tool calls that make progress, or (b) deliver a final "
    "result to the user. Responses that only describe intentions without acting are not acceptable."
)
UPSTREAM_ACT_DONT_ASK = (
    "When a question has an obvious default interpretation, act on it immediately instead of asking "
    "for clarification."
)


def _composed(answer_first: bool) -> str:
    """The guidance tier as a profile with this flag set would compose it."""
    from types import SimpleNamespace

    from agent.system_prompt import _guidance_parts

    agent = SimpleNamespace(
        valid_tool_names={"read_file", "terminal"}, model="deepseek-v4.1-flash",
        _tool_use_enforcement="true", _execution_guidance="true",
        _task_completion_guidance=True, _parallel_tool_call_guidance=True,
        _memory_manager=None, _prompt_suppress=set(),
        _planning_exemption=False, _answer_first=answer_first,
    )
    return "\n".join(p for p in _guidance_parts(agent) if p)


def test_off_composes_upstream_text_unchanged():
    """A profile that did not opt in composes upstream's wording, untouched."""
    off = _composed(False)
    assert UPSTREAM_RESPONSE_SENTENCE in off
    assert UPSTREAM_ACT_DONT_ASK in off
    assert "(c) answer the question and stop" not in off
    assert "# Question or task" not in off


def test_on_composes_the_rewrite():
    on = _composed(True)
    assert "(c) answer the question and stop" in on
    assert UPSTREAM_RESPONSE_SENTENCE not in on
    assert "not for a command" in on


def test_anchors_still_exist_upstream():
    """If upstream rewords either source sentence, fail loudly instead of silently not applying."""
    assert UPSTREAM_RESPONSE_SENTENCE in TOOL_USE_ENFORCEMENT_GUIDANCE
    assert UPSTREAM_ACT_DONT_ASK in execution_guidance_text({"read_file"})


def test_on_rewrites_the_response_rule_and_adds_question_vs_task():
    rewritten = apply_answer_first(TOOL_USE_ENFORCEMENT_GUIDANCE)
    assert "(c) answer the question and stop" in rewritten
    assert "An answer is a finished response" in rewritten
    assert "# Question or task" in rewritten
    assert "A question asks for information. A task asks for a change." in rewritten
    assert UPSTREAM_RESPONSE_SENTENCE not in rewritten


def test_on_retunes_act_dont_ask_to_resolve_the_reference():
    rewritten = apply_answer_first(execution_guidance_text({"read_file", "terminal"}))
    assert UPSTREAM_ACT_DONT_ASK not in rewritten
    assert "not for a command" in rewritten
    assert "resolve that interpretation yourself" in rewritten
    # the scope-resolution intent survives: the same three reference examples are still taught
    assert "this machine, not some other host" in rewritten
    assert "`date`, not a guess" in rewritten


def test_idempotent():
    once = apply_answer_first(TOOL_USE_ENFORCEMENT_GUIDANCE)
    assert apply_answer_first(once) == once
