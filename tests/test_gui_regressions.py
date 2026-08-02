"""Regression tests for side-effect-free and accurate GUI presentation."""

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

from gui import app as gui_app
from gui.app import SimulatorUI, _ASSEMBLY_STARTER, _C_STARTER
from gui.example_programs import EXAMPLE_PROGRAMS_BY_ID
from gui.renderers import (
    build_asm_view_html,
    build_cache_access_html,
    build_cache_table_html,
    build_csr_table_html,
    build_mc_stage_html,
    build_memory_table_html,
    build_register_table_html,
    build_state_legend_html,
    build_trap_log_html,
    format_branch_prediction_stats,
    parse_disassembly,
)
from rv32i.cache import Cache
from rv32i.memory import Memory
from rv32i.pipeline import BranchPredictionSnapshot


class _WidgetStub:
    def __init__(self, value=None) -> None:
        self.value = value
        self.themes: list[str] = []
        self.languages: list[str] = []
        self.text = ""

    def set_theme(self, theme: str) -> None:
        self.themes.append(theme)

    def set_language(self, language: str) -> None:
        self.languages.append(language)

    def set_text(self, text: str) -> None:
        self.text = text

    def set_value(self, value: str) -> None:
        self.value = value


def test_gui_main_uses_platform_port(monkeypatch) -> None:
    options: dict = {}
    monkeypatch.delenv("RV32I_GUI_PORT", raising=False)
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setattr(gui_app.ui, "run", lambda **kwargs: options.update(kwargs))

    gui_app.main()

    assert options["port"] == 10000


def test_gui_main_prefers_project_port(monkeypatch) -> None:
    options: dict = {}
    monkeypatch.setenv("RV32I_GUI_PORT", "9090")
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setattr(gui_app.ui, "run", lambda **kwargs: options.update(kwargs))

    gui_app.main()

    assert options["port"] == 9090


def test_disassembly_drops_section_heading_and_preserves_pc_mapping() -> None:
    text = """\
demo.elf: file format elf32-littleriscv

Disassembly of section .text:

00010000 <_start>:
   10000:\tlui\tt0,0x1
   10004:\tret
"""

    lines, pc_to_line = parse_disassembly(text)

    assert lines == [
        "00010000 <_start>:",
        "10000: lui\tt0,0x1",
        "10004: ret",
    ]
    assert pc_to_line == {0x10000: 1, 0x10004: 2}


def test_disassembly_renderer_exposes_label_hierarchy_and_stable_columns() -> None:
    lines = [
        "00010000 <_start>:",
        "10000: lui\tt0,0x1",
    ]

    html = build_asm_view_html(
        lines,
        {0x10000: 1},
        current_pc=0x10000,
        breakpoints={0x10000},
    )

    assert ".text" not in html
    assert 'class="asm-symbol"' in html
    assert 'class="asm-symbol-kind">Label</span>' in html
    assert 'class="asm-symbol-name">_start</div>' in html
    assert 'class="asm-symbol-address">0x00010000</span>' in html
    assert 'class="asm-line asm-current asm-breakpoint"' in html
    assert 'class="asm-address">0x00010000</span>' in html
    assert 'class="asm-mnemonic">lui</span>' in html
    assert 'class="asm-operands">t0,0x1</span>' in html
    assert 'aria-pressed="true"' in html


def test_memory_renderer_does_not_read_mmio_and_escapes_ascii() -> None:
    mem = Memory()
    reads = 0

    def on_read(addr: int, width: int) -> int:
        nonlocal reads
        reads += 1
        return ord("X")

    mem.register_device("probe", 0x1000, 16, on_read, lambda *_: None)
    build_memory_table_html(mem, 0x1000, 1, 0)
    assert reads == 0

    mem = Memory()
    mem.load_bytes(0, b"<b>&")
    html = build_memory_table_html(mem, 0, 1, 0)
    assert "&lt;b&gt;&amp;" in html
    assert "<b>&</b>" not in html


def test_register_and_csr_tables_highlight_only_latest_changes() -> None:
    registers = [0] * 32
    registers[5] = 42
    register_html = build_register_table_html(registers, {5})

    assert register_html.count('data-changed="true"') == 1
    assert 'aria-label="x5 t0, changed"' in register_html
    assert ">▸</span>" in register_html
    assert 'aria-label="x0 zero, unchanged"' in register_html

    csr_html = build_csr_table_html({0x300: 8, 0xB00: 4}, {0xB00})
    assert csr_html.count('data-changed="true"') == 1
    assert 'aria-label="mcycle, changed"' in csr_html
    assert 'aria-label="mstatus, unchanged"' in csr_html


def test_memory_table_marks_pc_row_and_only_changed_bytes() -> None:
    mem = Memory()
    mem.load_bytes(0x20, b"\x10\x20\x30")

    html = build_memory_table_html(
        mem,
        base_addr=0x20,
        rows=1,
        current_pc=0x21,
        changed_addresses={0x22},
    )

    assert 'class="memory-table"' in html
    assert 'data-pc-row="true"' in html
    assert html.count('data-changed="true"') == 1
    assert 'class="memory-byte memory-byte-changed"' in html


def test_cache_address_visual_keeps_msb_to_lsb_order() -> None:
    cache = Cache(Memory())
    cache.read_word(0x12345678)

    html = build_cache_access_html(cache.last_access, cache)
    displayed = "".join(re.findall(r'border-radius:2px">([01])</span>', html))

    assert displayed == f"{0x12345678:032b}"


def test_cache_access_raises_selected_cache_context() -> None:
    cache = Cache(Memory())
    cache.read_word(0x24)

    html = build_cache_access_html(cache.last_access, cache, "D")

    assert 'class="panel-context-band cache-access-context"' in html
    assert 'class="cache-access-kind">D-CACHE</span>' in html
    assert 'class="cache-access-address">0x00000024</strong>' in html
    assert "MISS" in html
    assert "Set <strong" in html


def test_trap_log_raises_latest_event_and_keeps_older_events_flat() -> None:
    entries = [
        {
            "kind": "EXC",
            "cause_name": "Illegal instruction",
            "cycle": 3,
            "mepc": 0x1000,
            "mtvec": 0,
            "mtval": 0xFFFFFFFF,
            "halted": True,
            "priority": -1,
        },
        {
            "kind": "INT",
            "cause_name": "Machine timer interrupt",
            "cycle": 9,
            "mepc": 0x1010,
            "mtvec": 0x2000,
            "mtval": 0,
            "halted": False,
            "priority": 2,
        },
    ]

    html = build_trap_log_html(entries)

    assert html.count('class="panel-context-band trap-latest"') == 1
    assert 'aria-label="Latest trap"' in html
    assert "Machine timer interrupt" in html
    assert "Priority 3" in html
    assert html.count('class="trap-history-row"') == 1
    assert "Earlier traps" in html


def test_wide_cache_block_renders_every_word_in_wrapping_data_region() -> None:
    mem = Memory()
    mem.load_bytes(0, bytes(range(128)))
    cache = Cache(mem, total_size=1024, block_size=128, ways=1)
    cache.read_word(0)

    html = build_cache_table_html(
        cache,
        start_idx=0,
        num_lines=1,
        last_access=cache.last_access,
        lookup_idx=0,
    )

    assert html.count('data-word-index="') == 32
    assert "W1F" in html
    assert "+16" not in html
    assert 'aria-label="Last access">A</span>' in html
    assert 'aria-label="Lookup match">L</span>' in html
    assert 'data-last-access="true"' in html
    assert 'data-lookup-match="true"' in html


def test_state_legends_explain_every_compact_marker_without_tooltips() -> None:
    pipeline = build_state_legend_html("pipeline")
    cache = build_state_legend_html("cache")

    for label in ("Fetch", "Decode", "Execute", "Memory", "Writeback", "Current cycle"):
        assert f">{label}</span>" in pipeline
    assert ">Stall</span>" not in pipeline
    assert ">Flush</span>" not in pipeline
    for label in ("Hit", "Miss", "Last access", "Lookup match"):
        assert f">{label}</span>" in cache
    assert 'role="list"' in pipeline
    assert 'role="list"' in cache
    assert "title=" not in pipeline + cache


def test_multicycle_active_stage_uses_readable_foreground() -> None:
    html = build_mc_stage_html(
        pc=0, mnemonic="addi", stages=["IF", "ID", "EX", "WB"], active_idx=1
    )
    assert 'class="mc-stage mc-stage-active"' in html
    assert 'aria-current="step"' in html
    assert "color:var(--fg)" in html
    assert "color:var(--bg)" not in html


def test_branch_prediction_stats_format_has_no_lost_cycle_metric() -> None:
    stats = BranchPredictionSnapshot(
        total=4,
        predicted_taken=4,
        predicted_not_taken=0,
        correct=3,
        incorrect=1,
    )

    text = format_branch_prediction_stats(stats)

    assert text == (
        "Branches 4 | predicted T 4 / NT 0 | correct 3 / wrong 1 | "
        "accuracy 75.0%"
    )
    assert "cycle" not in text.lower()


def test_source_language_change_replaces_compiles_and_resets() -> None:
    ui = SimulatorUI.__new__(SimulatorUI)
    ui._source_language = "c"
    ui.editor = _WidgetStub()
    ui._breakpoints = {0x10000}
    switched: list[str] = []
    compiled: list[bool] = []
    ui.switch_source_view = switched.append
    ui.compile = lambda: compiled.append(True)

    assert ui.source_suffix() == ".c"

    ui.on_source_language_change("assembly")

    assert ui.source_suffix() == ".s"
    assert ui.editor.languages[-1] == "Gas"
    assert ui.editor.value == _ASSEMBLY_STARTER
    assert ui._breakpoints == set()
    assert switched == ["source"]
    assert compiled == [True]

    ui.on_source_language_change("c")
    assert ui.source_suffix() == ".c"
    assert ui.editor.languages[-1] == "C"
    assert ui.editor.value == _C_STARTER
    assert compiled == [True, True]


def test_example_change_loads_source_build_settings_and_compiles() -> None:
    ui = SimulatorUI.__new__(SimulatorUI)
    ui._source_language = "assembly"
    ui._arch = "rv32i_zicsr"
    ui._link_mode = "linker"
    ui._source_language_labels = {"C": "c", "Assembly": "assembly"}
    ui._arch_labels = {
        "RV32I": "rv32i_zicsr",
        "RV32IMC": "rv32imc_zicsr",
    }
    ui._link_mode_labels = {
        "No linker": "no_linker",
        "With linker": "linker",
    }
    ui.example_select = _WidgetStub()
    ui.source_language_select = _WidgetStub()
    ui.arch_select = _WidgetStub()
    ui.link_select = _WidgetStub()
    ui.editor = _WidgetStub()
    ui._breakpoints = {0x10000}
    hints: list[bool] = []
    switched: list[str] = []
    compiled: list[bool] = []
    ui.update_ld_hint = lambda: hints.append(True)
    ui.switch_source_view = switched.append
    ui.compile = lambda: compiled.append(True)

    ui.on_example_change("hello-terminal")

    example = EXAMPLE_PROGRAMS_BY_ID["hello-terminal"]
    assert ui._source_language == "c"
    assert ui._arch == example.arch
    assert ui._link_mode == example.link_mode
    assert ui.example_select.value == example.id
    assert ui.source_language_select.value == "C"
    assert ui.arch_select.value == "RV32IMC"
    assert ui.link_select.value == "No linker"
    assert ui.editor.languages == ["C"]
    assert ui.editor.value == example.path.read_text(encoding="utf-8")
    assert ui._breakpoints == set()
    assert hints == [True]
    assert switched == ["source"]
    assert compiled == [True]


def test_unknown_example_reports_error_without_replacing_source() -> None:
    ui = SimulatorUI.__new__(SimulatorUI)
    ui.editor = _WidgetStub("keep this source")
    statuses: list[str] = []
    ui.apply_status = lambda message, color: statuses.append(message)

    ui.on_example_change("not-in-the-catalog")

    assert ui.editor.value == "keep this source"
    assert statuses == ["Unknown example: not-in-the-catalog"]


def test_memory_goto_rejects_addresses_outside_rv32() -> None:
    ui = SimulatorUI.__new__(SimulatorUI)
    ui._mem_base_addr = 0x200
    ui._mem_follow_pc = True
    ui.render_mem_page = lambda: None
    statuses: list[str] = []
    ui.apply_status = lambda message, color: statuses.append(message)

    for value in ("-1", "0x100000000", "not-an-address"):
        ui.mem_addr_input = SimpleNamespace(value=value)
        ui.mem_goto_addr()
        assert ui._mem_base_addr == 0x200

    assert len(statuses) == 3


def test_persisted_light_theme_updates_both_editors(monkeypatch) -> None:
    async def stored_theme(script: str) -> str:
        return "light"

    monkeypatch.setattr("gui.app.ui.run_javascript", stored_theme)
    ui = SimulatorUI.__new__(SimulatorUI)
    ui._theme = "dark"
    ui.editor = _WidgetStub()
    ui.ld_editor = _WidgetStub()
    ui.btn_theme = _WidgetStub()
    ui.rebuild_terminal = lambda: None

    asyncio.run(ui.sync_theme_from_browser())

    assert ui._theme == "light"
    assert ui.editor.themes[-1] == "basicLight"
    assert ui.ld_editor.themes[-1] == "basicLight"
    assert ui.btn_theme.text == "Dark"


def test_run_shortcut_toggle_uses_current_timer_state() -> None:
    ui = SimulatorUI.__new__(SimulatorUI)
    calls: list[str] = []
    ui.run_timer = SimpleNamespace(active=False)
    ui.run = lambda: calls.append("run")
    ui.stop = lambda: calls.append("stop")

    ui.toggle_run()
    ui.run_timer.active = True
    ui.toggle_run()

    assert calls == ["run", "stop"]


def test_compile_failure_blocks_execution_of_previous_program(monkeypatch) -> None:
    ui = SimulatorUI.__new__(SimulatorUI)
    ui._program_ready = True
    ui._source_language = "c"
    ui._link_mode = "no_linker"
    ui._arch = "rv32i_zicsr"
    ui.editor = _WidgetStub("this is not valid C")
    ui.run_timer = SimpleNamespace(deactivate=lambda: None)
    ui.sim = SimpleNamespace(step=lambda: executed.append(True))
    ui.apply_cache_config = lambda: None
    ui.update_asm_view = lambda current: None
    statuses: list[str] = []
    executed: list[bool] = []
    ui.apply_status = lambda message, color: statuses.append(message)
    monkeypatch.setattr(
        "gui.app.build",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bad source")),
    )

    ui.compile()
    ui.step()

    assert not ui._program_ready
    assert executed == []
    assert statuses[-2:] == [
        "Compile error: bad source",
        "A successful compile is required before execution",
    ]


def test_gui_does_not_access_private_simulator_state() -> None:
    gui_dir = Path(__file__).parents[1] / "gui"
    source = "\n".join(
        path.read_text()
        for path in (gui_dir / "app.py", gui_dir / "pipeline_control.py")
    )

    assert "self.sim._" not in source
    assert "sim._" not in source
    assert ".csr._csr" not in source
    assert ".mem._waiting_for_input" not in source
