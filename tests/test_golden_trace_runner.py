"""Unit checks for failures in the external Spike golden-state harness."""

from types import SimpleNamespace

import pytest

from .test_golden_trace_utils import SpikeRunner


def test_spike_failure_is_reported_instead_of_becoming_empty_state(monkeypatch) -> None:
    runner = SpikeRunner()
    monkeypatch.setattr(runner, "find_ebreak_addr", lambda path: 0x80001000)
    monkeypatch.setattr(
        "tests.test_golden_trace_utils.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="Failed to run dtc"
        ),
    )

    with pytest.raises(RuntimeError, match="Failed to run dtc"):
        runner.run_to_ebreak("program.elf")
