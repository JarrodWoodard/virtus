"""Guard: the rebrand must never touch identifiers.

A blunt text replacement once turned `from hermes_constants import …` into `from virtus_constants …`,
which broke every CLI turn while `--version` still worked. Importing the entry surface catches that.
"""
from __future__ import annotations

import importlib

import pytest

MODULES = [
    "hermes_cli.commands",
    "hermes_cli._parser",
    "hermes_cli.commands_completion",
    "hermes_cli.setup",
    "hermes_cli.virtus_config",
    "agent.curator",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    importlib.import_module(name)
