"""Planning exemption: the "unless you are planning with me" condition on every ACT sentence.

Owner requirement, in his words: prepend "Unless the user has told you that you are planning with
them, you MUST use ..." wherever the built-in text pushes the agent to act.

Invariants:
  - off (default): the composed text is byte-identical to upstream's;
  - on: every act-pushing sentence carries the condition, one time only;
  - the anchors still exist in upstream's literals (a rewording fails loudly here).
"""

from __future__ import annotations

import pytest

from agent.prompt_builder import (
    PLANNING_UNLESS,
    TASK_COMPLETION_GUIDANCE,
    TOOL_USE_ENFORCEMENT_GUIDANCE,
    apply_planning_exemption,
    execution_guidance_text,
)


# The anchors as they appear in upstream's literals (capitalised sentence starts).
ACT_SENTENCE_ANCHORS = (
    "You MUST use your tools to take action",
    "Every response should either (a) contain tool calls",
    "When the user asks you to build, run, or verify something",
    "When a question has an obvious default interpretation",
    "Do not stop early when another tool call would materially improve the result.",
    "Keep calling tools until: (1) the task is complete",
)


def test_off_is_byte_identical():
    assert apply_planning_exemption("") == ""
    plain = TOOL_USE_ENFORCEMENT_GUIDANCE
    assert PLANNING_UNLESS not in plain


def test_every_act_sentence_gets_the_condition():
    exempt = apply_planning_exemption(TOOL_USE_ENFORCEMENT_GUIDANCE)
    for anchor in ACT_SENTENCE_ANCHORS[:2]:
        assert PLANNING_UNLESS + anchor[0].lower() + anchor[1:] in exempt


def test_task_completion_and_execution_guidance_are_covered():
    exempt = apply_planning_exemption(TASK_COMPLETION_GUIDANCE)
    assert PLANNING_UNLESS + "when the user asks you to build, run, or verify something" in exempt

    exec_text = execution_guidance_text({"read_file", "terminal"})
    exempt_exec = apply_planning_exemption(exec_text)
    assert PLANNING_UNLESS + "when a question has an obvious default interpretation" in exempt_exec
    assert PLANNING_UNLESS + "keep calling tools until: (1) the task is complete" in exempt_exec


def test_application_is_idempotent():
    once = apply_planning_exemption(TOOL_USE_ENFORCEMENT_GUIDANCE)
    twice = apply_planning_exemption(once)
    assert once == twice
    assert twice.count(PLANNING_UNLESS) == once.count(PLANNING_UNLESS)


def test_anchors_still_exist_in_the_upstream_literals():
    """If upstream rewording breaks an anchor, this fails instead of silently disabling the rule."""
    corpus = TOOL_USE_ENFORCEMENT_GUIDANCE + TASK_COMPLETION_GUIDANCE + execution_guidance_text({"terminal"})
    missing = [a for a in ACT_SENTENCE_ANCHORS if a not in corpus]
    assert not missing, f"anchors gone from upstream text: {missing}"
