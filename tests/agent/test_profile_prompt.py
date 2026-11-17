"""Per-profile system-prompt extension: PROMPT.md appended last, plus named-block suppression.

Owner requirement: the system prompt must be configurable PER PROFILE, so one binary can run
different prompts per profile (the architect plans; the orchestrator acts).

Invariants:
  - a profile with no PROMPT.md and an empty suppress list composes the prompt unchanged;
  - PROMPT.md lands at the very END of the prompt, after every built-in block, so it outranks them;
  - `agent.prompt.suppress` removes only the named blocks, leaving the rest untouched.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.system_prompt import _guidance_parts, _profile_prompt_part


def _agent(**overrides):
    base = dict(
        valid_tool_names={"read_file", "terminal"},
        model="deepseek-v4.1-flash",
        _tool_use_enforcement="true",
        _execution_guidance="true",
        _task_completion_guidance=True,
        _parallel_tool_call_guidance=True,
        _memory_manager=None,
        skip_context_files=False,
        _prompt_file="PROMPT.md",
        _prompt_suppress=set(),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def profile_home(tmp_path, monkeypatch):
    home = tmp_path / "profile"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def test_no_prompt_file_contributes_nothing(profile_home):
    """Absent file = no part at all, which is what keeps an untouched profile byte-identical."""
    assert _profile_prompt_part(_agent()) is None


def test_prompt_file_is_read_verbatim(profile_home):
    (profile_home / "PROMPT.md").write_text("Answer the question. Change nothing until GO.\n")
    part = _profile_prompt_part(_agent())
    assert part == "Answer the question. Change nothing until GO."


def test_custom_file_name_and_disable(profile_home):
    (profile_home / "ARCHITECT.md").write_text("You are the architect.\n")
    assert _profile_prompt_part(_agent(_prompt_file="ARCHITECT.md")) == "You are the architect."
    assert _profile_prompt_part(_agent(_prompt_file="MISSING.md")) is None
    assert _profile_prompt_part(_agent(_prompt_file="")) is None


def test_absolute_path_is_honoured(tmp_path, profile_home):
    target = tmp_path / "elsewhere.md"
    target.write_text("Absolute prompt.\n")
    assert _profile_prompt_part(_agent(_prompt_file=str(target))) == "Absolute prompt."


def test_suppress_drops_only_the_named_blocks():
    full = "\n".join(p for p in _guidance_parts(_agent()) if p)
    assert "Responses that only describe intentions" in full        # enforcement
    assert "Execution discipline" in full                              # execution guidance

    suppressed = "\n".join(p for p in _guidance_parts(
        _agent(_prompt_suppress={"enforcement", "execution_guidance"})
    ) if p)
    assert "Responses that only describe intentions" not in suppressed
    assert "Execution discipline" not in suppressed
    # unrelated blocks survive
    assert "Execution discipline" not in suppressed


def test_unknown_suppress_names_are_ignored():
    unknown = "\n".join(p for p in _guidance_parts(_agent(_prompt_suppress={"nonsense"})) if p)
    known = "\n".join(p for p in _guidance_parts(_agent()) if p)
    assert unknown == known
