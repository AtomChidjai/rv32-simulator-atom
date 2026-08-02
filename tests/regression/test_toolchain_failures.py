"""Failure handling for compiler and ELF metadata subprocesses."""

import os
from types import SimpleNamespace

import pytest

import rv32i.builder as builder
import rv32i.elf_loader as elf_loader

# Subprocess timeouts
def test_compile_c_to_elf_passes_timeout_argument(monkeypatch):
    captured: list = []

    def fake_run(cmd, **kwargs):
        captured.append((cmd, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)
    builder.compile_c_to_elf("a.c", "a.elf")

    assert captured, "subprocess.run was never called"
    _, kwargs = captured[0]
    assert kwargs["timeout"] == builder.TOOL_TIMEOUT_SECONDS


def test_elf_to_bin_and_objdump_also_use_timeout(monkeypatch):
    captured: list = []

    def fake_run(cmd, **kwargs):
        captured.append(kwargs)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)
    builder.elf_to_bin("a.elf", "a.bin")
    builder.get_disassembly("a.elf")

    assert len(captured) == 2
    assert all(kw["timeout"] == builder.TOOL_TIMEOUT_SECONDS for kw in captured)


def test_tool_timeout_is_reported_as_typed_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise builder.subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    with pytest.raises(builder.ToolchainError, match="timed out"):
        builder.compile_c_to_elf("a.c", "a.elf")


def test_missing_tool_is_reported_as_typed_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    with pytest.raises(builder.ToolchainError, match="not found"):
        builder.get_disassembly("a.elf")


def test_build_confines_default_artifacts(monkeypatch, tmp_path):
    seen_cmds: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        seen_cmds.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)
    source = tmp_path / "caller-controlled.c"
    result = builder.build(str(source))

    build_root = builder._BUILD_DIR.name
    assert os.path.commonpath([build_root, result["elf_file"]]) == build_root
    assert os.path.commonpath([build_root, result["bin_file"]]) == build_root
    assert seen_cmds[0][seen_cmds[0].index("-o") + 1] == result["elf_file"]


# ELF metadata errors
def test_load_elf_reports_bad_entry_point(monkeypatch):
    bad_readelf = "  Entry point address: NOT-A-NUMBER\n"

    def fake_run(cmd):
        tool = cmd[0]
        if tool.endswith("readelf"):
            return bad_readelf
        return ""

    monkeypatch.setattr(elf_loader, "run", fake_run)

    with pytest.raises(elf_loader.ELFLoadError, match="entry point"):
        elf_loader.load_elf("x.elf")


def test_load_elf_reports_short_section_line(monkeypatch):
    short_objdump = (
        "Sections:\n"
        "Idx Name Size\n"
        "  0 .text\n"                 # Too few columns.
        "                  CONTENTS, ALLOC, LOAD\n"
    )

    def fake_run(cmd):
        tool = cmd[0]
        if tool.endswith("readelf"):
            return "  Entry point address: 00010074\n"
        if tool.endswith("objdump"):
            return short_objdump
        return ""

    monkeypatch.setattr(elf_loader, "run", fake_run)

    with pytest.raises(elf_loader.ELFLoadError, match="section row"):
        elf_loader.load_elf("x.elf")


def test_elf_loader_subprocess_uses_timeout(monkeypatch):
    captured: list[dict] = []

    def fake_run(cmd, **kwargs):
        captured.append(kwargs)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(elf_loader.subprocess, "run", fake_run)
    elf_loader.run(["readelf", "-h", "x.elf"])

    assert captured[0]["timeout"] == elf_loader.TOOL_TIMEOUT_SECONDS
