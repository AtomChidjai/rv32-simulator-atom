"""NiceGUI front end and execution-mode state coordinator."""

import json
import os
import sys
import tempfile

# Support direct script execution as well as ``python -m gui.app``.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from nicegui import app as nicegui_app, ui
from rv32i import Simulator
from rv32i.builder import (
    build, get_disassembly, ARCH_OPTIONS, DEFAULT_ARCH,
    LINK_MODE_NO_LINKER, LINK_MODE_LINKER, DEFAULT_LINK_MODE,
    DEFAULT_LINKER_SCRIPT,
)
from rv32i.elf_loader import load_elf

from gui.theme import (
    C_BG, C_BG_DARK, C_BG_PANEL, C_FG_DIM, C_ACCENT, C_GREEN,
    C_RED, C_YELLOW, C_CYAN, C_BORDER, inject_global_css,
    XTERM_DARK, XTERM_LIGHT, CM_DARK, CM_LIGHT,
)
from gui.renderers import (
    parse_disassembly,
    build_register_table_html,
    build_csr_table_html,
    build_trap_log_html,
    build_memory_table_html,
    build_cache_table_html,
    build_cache_access_html,
    build_cache_stats_html,
    build_asm_view_html,
    build_pipeline_latch_html,
    build_pipeline_gantt_html,
    build_mc_stage_html,
    build_state_legend_html,
    format_branch_prediction_stats,
)
from gui.pipeline_control import (
    assembly_highlight_pc,
    current_breakpoint_pc,
    can_advance,
    cycle_limit_reached,
    execution_in_flight,
    mode_cycle_limit,
    mode_ui_state,
)
from gui.decode_panel import build_decode_panel
from gui.example_programs import (
    DEFAULT_EXAMPLE_ID,
    EXAMPLE_PROGRAMS,
    EXAMPLE_PROGRAMS_BY_ID,
)

_C_STARTER = """\
volatile unsigned int result;

void _start(void) {
    result = 42;
    __builtin_trap();
}
"""
_ASSEMBLY_STARTER = """\
.section .text
.globl _start

_start:
    addi x5, x0, 42
    ebreak
"""
_RISCV_LOGO_URL = nicegui_app.add_static_file(
    local_file=os.path.join(_PROJECT_ROOT, "gui", "assets", "riscv-logo.webp"),
    url_path="/rv32i-assets/riscv-logo.webp",
)
nicegui_app.add_static_file(
    local_file=os.path.join(_PROJECT_ROOT, "gui", "assets", "vendor", "wavedrom.min.js"),
    url_path="/rv32i-assets/vendor/wavedrom.min.js",
)
_DECODE_BITFIELD_URL = nicegui_app.add_static_file(
    local_file=os.path.join(_PROJECT_ROOT, "gui", "assets", "decode_bitfield.js"),
    url_path="/rv32i-assets/decode_bitfield.js",
)
_SHORTCUTS_URL = nicegui_app.add_static_file(
    local_file=os.path.join(_PROJECT_ROOT, "gui", "assets", "shortcuts.js"),
    url_path="/rv32i-assets/shortcuts.js",
)


class SimulatorUI:
    def __init__(self) -> None:
        self.sim = Simulator(verbose_decoder=False, trace=False, max_cycles=500)
        self.sim.on_console_write = self.on_console_write
        self._max_cycles_base: int = self.sim.max_cycles
        self._mode: str = "single"
        self.asm_lines: list[str] = []
        self.pc_to_line: dict[int, int] = {}
        self.run_timer = ui.timer(0.1, self.auto_tick, active=False)
        self._program_ready = False
        self._mem_snapshot: dict[int, bytes] = {}
        self._init_sp: int = 0x7FFFFFF0
        self._init_gp: int | None = None
        self._mem_base_addr = 0
        self._mem_page_size = 128
        self._mem_follow_pc = True
        self._cache_page = 0
        self._cache_lines_per_page = 8
        self._cache_lookup_idx = -1
        self._cache_view = "D"
        self._breakpoints: set[int] = set()
        self._input_buffer: list[str] = []
        self._arch: str = DEFAULT_ARCH
        self._link_mode: str = DEFAULT_LINK_MODE
        self._linker_script: str | None = None
        self._cache_size: int = 32 * 1024
        self._cache_block: int = 64
        self._cache_ways: int = 1
        self._cache_policy: str = "fifo"
        self._i_miss_stall: int = 0
        self._d_miss_stall: int = 0
        self._source_view: str = "source"
        self._source_language: str = "c"
        self._theme: str = "dark"
        self._register_values = tuple(self.sim.proc.registers)
        self._csr_values = self.sim.csr_snapshot()
        self._memory_view_bytes: dict[int, int] = {}
        self._term_lines: list[str] = []
        self.build_ui()
        self.load_default()

    def build_ui(self) -> None:
        inject_global_css()
        ui.add_head_html(
            f'<script type="module" src="{_DECODE_BITFIELD_URL}?v=2"></script>'
        )
        ui.add_head_html(
            f'<script type="module">'
            f'import {{ installSimulatorShortcuts }} from "{_SHORTCUTS_URL}?v=1";'
            f'installSimulatorShortcuts();'
            f'</script>'
        )

        with ui.column().classes("w-full items-center justify-center").style("height:100dvh;background:" + C_BG) as self.splash:
            ui.label("██████╗ ██╗   ██╗██████╗ ██████╗ ").classes("font-mono text-xl").style(f"color:{C_ACCENT}")
            ui.label("██╔══██╗██║   ██║╚════██╗╚════██╗").classes("font-mono text-xl").style(f"color:{C_ACCENT}")
            ui.label("██████╔╝██║   ██║ █████╔╝ █████╔╝").classes("font-mono text-xl").style(f"color:{C_ACCENT}")
            ui.label("██╔══██╗╚██╗ ██╔╝ ╚═══██╗██╔═══╝ ").classes("font-mono text-xl").style(f"color:{C_ACCENT}")
            ui.label("██║  ██║ ╚████╔╝ ██████╔╝███████╗").classes("font-mono text-xl").style(f"color:{C_ACCENT}")
            ui.label("╚═╝  ╚═╝  ╚═══╝  ╚═════╝ ╚══════╝").classes("font-mono text-xl").style(f"color:{C_ACCENT}")
            ui.label("RISC-V RV32I Simulator").classes("text-sm mt-2").style(f"color:{C_FG_DIM}")

        self.terminal_drawer = ui.right_drawer(
            value=False, bordered=True, top_corner=True, bottom_corner=True,
        ).props("width=560 overlay").style(f"background:{C_BG_PANEL};")
        with self.terminal_drawer:
            with ui.column().classes("w-full gap-0").style("height:100%"):
                with ui.row().classes("w-full items-center").style(f"padding:0 0 10px;border-bottom:1px solid {C_BORDER};gap:4px;margin-bottom:4px"):
                    with ui.tabs(value="terminal").props("dense no-caps narrow-indicator").classes("text-xs") as self.utility_tabs:
                        ui.tab("terminal", label="Terminal")
                        ui.tab("traps", label="Trap Log")
                    ui.space()
                    ui.button("\u2715", on_click=lambda: self.terminal_drawer.hide()).props("outline dense").classes("text-xs").style("min-height:26px;padding:2px 10px")
                with ui.tab_panels(self.utility_tabs, value="terminal", animated=False).classes("w-full").style("flex:1;min-height:0;background:transparent"):
                    with ui.tab_panel("terminal").classes("p-0").style("height:100%"):
                        self.terminal_slot = ui.column().classes("w-full").style("width:100%;height:100%;min-height:0")
                        with self.terminal_slot:
                            self.build_terminal()
                    with ui.tab_panel("traps").classes("p-0").style("height:100%;overflow-y:auto"):
                        self.trap_html = ui.html(
                            build_trap_log_html([])
                        ).classes("font-mono w-full")
                        self.build_interrupt_controls()

        self.main_container = ui.column().classes("app-shell w-full gap-0").style("display:none;height:100dvh;flex-direction:column;background:" + C_BG)

        with self.main_container:
            self.build_top_bar()

            with ui.row().classes("workspace-primary w-full"):
                with ui.column().classes("sim-panel panel-frame panel-source"):
                    with ui.row().classes("panel-header w-full items-center"):
                        ui.label("SOURCE").classes("panel-title")
                        ui.space()
                        self.build_source_controls()
                        self.btn_view_source = ui.button("code (C/assembly)", on_click=lambda: self.switch_source_view("source")).props("outline").classes("text-xs").style("min-height:26px;padding:2px 12px")
                        self.btn_view_linker = ui.button(".ld", on_click=lambda: self.switch_source_view("linker")).props("outline").classes("text-xs").style("min-height:26px;padding:2px 12px")
                    self.source_editor_wrap = ui.column().classes("w-full").style("flex:1;height:100%;min-height:0")
                    with self.source_editor_wrap:
                        self.editor = ui.codemirror(value="", language="c", theme=CM_DARK).classes("w-full").style("height:100%;min-height:0")
                    self.linker_editor_wrap = ui.column().classes("w-full").style("flex:1;height:100%;min-height:0;display:none")
                    with self.linker_editor_wrap:
                        self.ld_editor = ui.codemirror(value="", language="C", theme=CM_DARK).classes("w-full").style("height:100%;min-height:0")
                        self.ld_hint = ui.label("").classes("text-xs").style(f"color:{C_FG_DIM};padding-top:6px")
                    self.refresh_source_view_toggle()

                with ui.column().classes("sim-panel panel-frame panel-assembly"):
                    self.panel_header("DISASSEMBLY")
                    with ui.scroll_area().classes("w-full").style("flex:1;height:100%;min-height:0"):
                        self.asm_html = ui.html("").classes("font-mono text-m w-full")

                with ui.column().classes("sim-panel panel-frame panel-registers"):
                    with self.panel_header("REGISTERS"):
                        ui.space()
                        with ui.tabs(value="gpr").props("dense no-caps narrow-indicator").classes("text-xs") as register_tabs:
                            ui.tab("gpr", label="GP")
                            ui.tab("csr", label="CSR")
                    with ui.tab_panels(register_tabs, value="gpr", animated=False).classes("w-full").style("flex:1;min-height:0;background:transparent"):
                        with ui.tab_panel("gpr").classes("p-0").style("height:100%;overflow-y:auto"):
                            self.reg_html = ui.html("").classes("font-mono w-full")
                        with ui.tab_panel("csr").classes("p-0").style("height:100%;overflow-y:auto"):
                            self.csr_html = ui.html("").classes("font-mono w-full")

            with ui.row().classes("workspace-secondary w-full"):
                with ui.column().classes("sim-panel panel-frame panel-memory"):
                    with self.panel_header("MEMORY SYSTEM"):
                        ui.space()
                        with ui.tabs(value="memory").props("dense no-caps narrow-indicator").classes("text-xs") as memory_tabs:
                            ui.tab("memory", label="Memory")
                            ui.tab("cache", label="Cache")
                    with ui.tab_panels(memory_tabs, value="memory", animated=False).classes("w-full").style("flex:1;min-height:0;background:transparent"):
                        with ui.tab_panel("memory").classes("p-0").style("height:100%;overflow:hidden"):
                            self.mem_html = ui.html("").classes("mem-table-scroll font-mono w-full")
                            with ui.row().classes("w-full items-center justify-center").style("gap:8px;padding:8px 0 0"):
                                self.btn_mem_prev = ui.button("◀ Prev", on_click=self.mem_prev_page).props("outline")
                                self.mem_page_label = ui.label("").classes("text-xs").style(f"color:{C_FG_DIM}")
                                self.btn_mem_next = ui.button("Next ▶", on_click=self.mem_next_page).props("outline")
                                self.btn_mem_goto_pc = ui.button("Go to PC", on_click=self.mem_goto_pc).props("outline")
                                ui.label("│").style(f"color:{C_BORDER}")
                                self.mem_addr_input = ui.input(placeholder="0x address").classes("text-xs").style("width:110px")
                                self.btn_mem_goto_addr = ui.button("Go", on_click=self.mem_goto_addr).props("outline")
                        with ui.tab_panel("cache").classes("cache-panel p-0").style("height:100%;overflow-y:auto"):
                            self.cache_header_label = ui.label(self.cache_panel_desc()).classes("text-xs").style(f"color:{C_FG_DIM};padding-bottom:4px")
                            self.build_cache_controls()
                            with ui.row().classes("w-full items-center").style("gap:8px;padding:8px 0 0"):
                                self.btn_cache_view_d = ui.button("D-Cache", on_click=lambda: self.set_cache_view("D")).props("outline")
                                self.btn_cache_view_i = ui.button("I-Cache", on_click=lambda: self.set_cache_view("I")).props("outline")
                            ui.html(build_state_legend_html("cache")).classes("w-full")
                            self.cache_stats_html = ui.html("").classes("font-mono w-full").style(f"border-bottom:1px solid {C_BORDER};padding-bottom:6px")
                            self.cache_access_html = ui.html("").classes("cache-access font-mono w-full").style(f"border-bottom:1px solid {C_BORDER};padding-bottom:8px")
                            with ui.row().classes("w-full items-center").style("gap:8px;padding:8px 0 0"):
                                ui.label("Lookup:").classes("text-xs").style(f"color:{C_FG_DIM}")
                                self.cache_lookup_input = ui.input(placeholder="0x address").classes("text-xs").style("width:100px")
                                self.btn_cache_lookup = ui.button("Go", on_click=self.cache_lookup).props("outline")
                                self.btn_cache_lookup_pc = ui.button("PC", on_click=self.cache_lookup_pc).props("outline")
                            self.cache_html = ui.html("").classes("cache-table-scroll font-mono w-full")
                            with ui.row().classes("w-full items-center justify-center").style("gap:8px;padding:8px 0 0"):
                                self.btn_cache_prev = ui.button("◀ Prev", on_click=self.cache_prev_page).props("outline")
                                self.cache_page_label = ui.label("").classes("text-xs").style(f"color:{C_FG_DIM}")
                                self.btn_cache_next = ui.button("Next ▶", on_click=self.cache_next_page).props("outline")
                                self.btn_cache_goto = ui.button("Go to Last", on_click=self.cache_goto_last).props("outline")

                with ui.column().classes("sim-panel panel-frame panel-diagnostics"):
                    with ui.column().classes("diagnostics-stack w-full gap-0"):
                        self.decode_section = ui.column().classes(
                            "diagnostic-section decode-section w-full gap-0"
                        )
                        with self.decode_section:
                            self.panel_header("DECODE")
                            self.decode_html = ui.html("").classes("font-mono w-full")

                        self.pipeline_section = ui.column().classes(
                            "diagnostic-section pipeline-section w-full gap-0"
                        )
                        with self.pipeline_section:
                            self.panel_header("PIPELINE")
                            with ui.column().classes(
                                "panel-context-band pipeline-context w-full gap-0"
                            ):
                                self.build_pipeline_controls()
                                ui.html(build_state_legend_html("pipeline")).classes(
                                    "w-full"
                                )
                                # ui.label(
                                #     "A repeated stage indicates a stall. "
                                #     "A red crossed stage indicates a flush."
                                # ).classes("pipeline-trace-note")
                            with ui.splitter(
                                value=28,
                                limits=(20, 42),
                            ).classes("pipeline-splitter w-full") as self.pipeline_splitter:
                                with self.pipeline_splitter.before:
                                    with ui.column().classes(
                                        "pipeline-pane pipeline-register-pane w-full gap-0"
                                    ):
                                        ui.label("PIPELINE REGISTERS").classes(
                                            "pipeline-pane-title"
                                        )
                                        self.pipeline_latch_html = ui.html("").classes(
                                            "pipeline-pane-scroll pipeline-register-view font-mono w-full"
                                        )
                                with self.pipeline_splitter.after:
                                    with ui.column().classes(
                                        "pipeline-pane pipeline-visualization-pane w-full gap-0"
                                    ):
                                        ui.label("PIPELINE VISUALIZATION").classes(
                                            "pipeline-pane-title"
                                        )
                                        self.pipeline_gantt_html = ui.html("").classes(
                                            "pipeline-pane-scroll pipeline-timeline-view font-mono w-full"
                                        )

                        self.mc_section = ui.column().classes(
                            "diagnostic-section mc-section w-full gap-0"
                        )
                        with self.mc_section:
                            self.panel_header("MULTI-CYCLE")
                            self.mc_html = ui.html(
                                '<div style="color:{c};font-size:12px;padding:8px;font-family:monospace">'
                                "(idle - press Step to advance one clock)</div>".format(c=C_FG_DIM)
                            ).classes("font-mono w-full")

            self.apply_mode_ui(self._mode)

            with ui.row().classes("bottom-status w-full items-center").props(
                'role="status" aria-live="polite"'
            ).style(
                f"background:{C_BG_DARK};border-top:1px solid {C_BORDER}"
            ):
                self.status_label = ui.label("READY").props(
                    "id=sim-status"
                ).classes("app-status font-mono")
                ui.separator().props("vertical").classes("status-separator")
                self.pc_label = ui.label("PC:0x00000000").classes("font-bold text-l").style(f"color:{C_ACCENT}")
                self.cycle_label = ui.label("CYCLE:0000").classes("font-bold text-l").style(f"color:{C_ACCENT}")
                self.mtime_label = ui.label("MTIME:0000").classes("font-bold text-l").style(f"color:{C_ACCENT}")
                self.mtimecmp_label = ui.label("MTIMECMP:0000").classes("font-bold text-l").style(f"color:{C_ACCENT}")

        ui.add_head_html('''
        <script>
        window._bp_addr = "";
        function queueBreakpoint(el) {
            var addr = el.getAttribute("data-addr");
            if (addr) window._bp_addr = addr;
        }
        document.addEventListener("click", function(ev) {
            var el = ev.target.closest(".asm-line");
            if (!el) return;
            queueBreakpoint(el);
        });
        document.addEventListener("keydown", function(ev) {
            if (ev.key !== "Enter" && ev.key !== " ") return;
            var el = ev.target.closest(".asm-line");
            if (!el) return;
            ev.preventDefault();
            queueBreakpoint(el);
        });
        </script>
        ''')

        # Breakpoint polling timer (async: reads JS global, clears it, toggles)
        ui.timer(0.1, self.check_breakpoint_click)

        # Allow the browser theme and initial widget tree to settle before reveal.
        ui.timer(0.1, self.sync_theme_from_browser, once=True)
        ui.timer(0.15, self.boot_done, once=True)

    def build_top_bar(self) -> None:
        """Build brand utilities and the execution-only primary toolbar."""

        with ui.column().classes("app-topbar w-full gap-0"):
            with ui.row().classes("app-brandbar w-full items-center"):
                ui.element("img").props(
                    f'src="{_RISCV_LOGO_URL}" alt="RISC-V logo"'
                ).classes("app-logo")
                ui.label("RV32 SIMULATOR").classes("app-title")
                ui.label("RV32IMC + Zicsr").classes("app-subtitle")
                ui.space()
                self.btn_terminal = ui.button(
                    "Terminal", on_click=lambda: self.open_utility_drawer("terminal")
                ).props("outline id=sim-terminal")
                self.btn_trap_log = ui.button(
                    "Trap Log", on_click=lambda: self.open_utility_drawer("traps")
                ).props("outline")
                self.btn_theme = ui.button(
                    "Light", on_click=self.toggle_theme
                ).props("outline")

            with ui.row().classes("execution-toolbar w-full items-center"):
                ui.label("Execution").classes("control-group-label")
                self.mode_select = ui.toggle(
                    {
                        "single": "Single-Cycle",
                        "multi": "Multi-Cycle",
                        "pipe": "Pipeline",
                    },
                    value=self._mode,
                    on_change=lambda e: self.on_mode_change(str(e.value)),
                ).props("id=sim-mode").classes("text-xs")
                ui.separator().props("vertical").classes("toolbar-separator")
                self.btn_compile = ui.button(
                    "Compile", on_click=self.compile
                ).classes("btn-primary").props("id=sim-compile")
                self.btn_step = ui.button("Step", on_click=self.step).classes(
                    "btn-primary"
                ).props('id=sim-step aria-keyshortcuts="Control+Enter Meta+Enter"')
                self.btn_run = ui.button("Run", on_click=self.run).classes(
                    "btn-primary"
                ).props(
                    'id=sim-run aria-keyshortcuts="Control+Shift+Enter Meta+Shift+Enter"'
                )
                self.btn_stop = ui.button("Stop", on_click=self.stop).props(
                    'outline id=sim-stop aria-keyshortcuts="Control+Shift+Enter Meta+Shift+Enter"'
                )
                self.btn_reset = ui.button("Reset", on_click=self.reset).props(
                    'outline id=sim-reset aria-keyshortcuts="Control+Alt+R Meta+Alt+R"'
                )
                ui.space()
                ui.label("Run speed").classes("control-group-label")
                self.speed_slider = ui.slider(
                    min=100, max=3000, value=100, step=100
                ).props('aria-label="Run speed"').classes("run-speed-slider").on(
                    "update:model-value",
                    lambda e: setattr(
                        self.run_timer,
                        "interval",
                        self.speed_slider.value / 1000.0,
                    ),
                )
                ui.label().bind_text_from(
                    self.speed_slider,
                    "value",
                    lambda v: f"{int(v)} ms",
                ).classes("run-speed-value")
                ui.button("", on_click=self.toggle_run).props(
                    "id=sim-run-toggle aria-hidden=true tabindex=-1"
                ).style("display:none")

    def open_utility_drawer(self, panel: str) -> None:
        """Open the shared utility drawer at the requested tab."""

        self.utility_tabs.value = panel
        self.terminal_drawer.show()

    def build_source_controls(self) -> None:
        """Build example, ISA, and linker controls beside the source."""

        self._example_labels = {
            example.id: example.label for example in EXAMPLE_PROGRAMS
        }
        self._source_language_labels = {
            "C": "c",
            "Assembly": "assembly",
        }
        self._arch_labels = {opt["label"]: opt["march"] for opt in ARCH_OPTIONS}
        default_label = next(
            label for label, march in self._arch_labels.items() if march == DEFAULT_ARCH
        )
        self._link_mode_labels = {
            "No linker (default)": LINK_MODE_NO_LINKER,
            "With linker": LINK_MODE_LINKER,
        }
        with ui.row().classes("context-controls items-center").style("padding:0;flex-wrap:nowrap"):
            self.example_select = ui.select(
                self._example_labels,
                value=DEFAULT_EXAMPLE_ID,
                label="Example",
                on_change=lambda e: self.on_example_change(e.value),
            ).props("id=sim-example options-dense").classes("text-xs").style(
                "min-width:180px"
            )
            self.source_language_select = ui.select(
                self._source_language_labels,
                value="C",
                label="Source",
                on_change=lambda e: self.on_source_language_change(
                    self._source_language_labels[e.value]
                ),
            ).classes("text-xs").style("min-width:85px")
            self.arch_select = ui.select(
                self._arch_labels,
                value=default_label,
                label="ISA",
                on_change=lambda e: setattr(
                    self, "_arch", self._arch_labels[e.value]
                ),
            ).classes("text-xs").style("min-width:145px")
            self.link_select = ui.select(
                self._link_mode_labels,
                value="No linker (default)",
                label="Linking",
                on_change=lambda e: self.on_link_mode_change(
                    self._link_mode_labels[e.value]
                ),
            ).classes("text-xs").style("min-width:130px")

    def build_cache_controls(self) -> None:
        """Build cache geometry and timing controls inside the Cache panel."""

        with ui.expansion("Configuration").classes("context-expansion w-full").props("dense"):
            with ui.row().classes("context-controls w-full items-center"):
                self.cache_size_select = ui.select(
                    {s: f"{s // 1024} KB" for s in self.valid_cache_sizes()},
                    value=self._cache_size,
                    label="Size",
                    on_change=lambda e: self.on_cache_config_change(
                        size=int(e.value),
                        block=self._cache_block,
                        ways=self._cache_ways,
                        policy=self._cache_policy,
                    ),
                ).classes("text-xs").style("min-width:100px")
                self.cache_block_select = ui.select(
                    {16: "16 B", 32: "32 B", 64: "64 B", 128: "128 B"},
                    value=self._cache_block,
                    label="Block",
                    on_change=lambda e: self.on_cache_config_change(
                        size=self._cache_size,
                        block=int(e.value),
                        ways=self._cache_ways,
                        policy=self._cache_policy,
                    ),
                ).classes("text-xs").style("min-width:80px")
                self.cache_assoc_select = ui.select(
                    {1: "1-way", 2: "2-way", 4: "4-way", 8: "8-way", 16: "16-way"},
                    value=self._cache_ways,
                    label="Ways",
                    on_change=lambda e: self.on_cache_config_change(
                        size=self._cache_size,
                        block=self._cache_block,
                        ways=int(e.value),
                        policy=self._cache_policy,
                    ),
                ).classes("text-xs").style("min-width:90px")
                self.cache_policy_select = ui.select(
                    {"fifo": "FIFO", "lru": "LRU"},
                    value=self._cache_policy,
                    label="Policy",
                    on_change=lambda e: self.on_cache_config_change(
                        size=self._cache_size,
                        block=self._cache_block,
                        ways=self._cache_ways,
                        policy=str(e.value),
                    ),
                ).classes("text-xs").style("min-width:80px")
            self.cache_timing_controls = ui.row().classes(
                "context-controls w-full items-center"
            )
            with self.cache_timing_controls:
                self.i_miss_stall_input = ui.number(
                    label="I-Miss Stall",
                    value=self._i_miss_stall,
                    min=0,
                    max=100,
                    on_change=lambda e: self.on_cache_stall_change(
                        i=e.value, d=self._d_miss_stall
                    ),
                ).classes("text-xs").style("min-width:110px")
                self.d_miss_stall_input = ui.number(
                    label="D-Miss Stall",
                    value=self._d_miss_stall,
                    min=0,
                    max=100,
                    on_change=lambda e: self.on_cache_stall_change(
                        i=self._i_miss_stall, d=e.value
                    ),
                ).classes("text-xs").style("min-width:110px")

    def build_pipeline_controls(self) -> None:
        """Build live hazard controls inside the Pipeline panel."""

        self.pipeline_controls = ui.row().classes(
            "context-controls w-full items-center"
        )
        with self.pipeline_controls:
            self.fwd_switch = ui.switch(
                "Forwarding",
                value=self.sim.forwarding,
                on_change=lambda e: self.on_pipeline_config_change(
                    forwarding=e.value
                ),
            ).classes("text-xs")
            ui.label("Prediction").classes("control-group-label")
            self.predict_select = ui.toggle(
                {"nottaken": "Not-Taken", "taken": "Taken"},
                value=self.sim.branch_predict,
                on_change=lambda e: self.on_pipeline_config_change(
                    branch_predict=str(e.value)
                ),
            ).classes("text-xs")
            self.prediction_stats_label = ui.label(
                format_branch_prediction_stats(
                    self.sim.pipeline_state().branch_prediction
                )
            ).classes("text-xs").style(f"color:{C_FG_DIM}")

    def build_interrupt_controls(self) -> None:
        """Build manual interrupt triggers next to the trap log."""

        with ui.row().classes("context-controls w-full items-center"):
            ui.label("Trigger interrupt").classes("control-group-label")
            self.btn_irq = ui.button(
                "[!] External", on_click=self.fire_irq
            ).props("outline").classes("btn-danger-subtle")
            self.btn_swi = ui.button(
                "[!] Software", on_click=self.fire_swi
            ).props("outline").classes("btn-warning-subtle")

    def panel_header(self, title: str):
        with ui.row().classes("panel-header w-full items-center") as header:
            ui.label(title).classes("panel-title")
        return header

    def xterm_theme(self) -> dict:
        """Concrete xterm color dict for the current theme (canvas can't use CSS vars)."""
        return XTERM_DARK if self._theme == "dark" else XTERM_LIGHT

    def build_terminal(self):
        """(Re)create the xterm widget inside self.terminal_slot, replaying scrollback."""
        self.terminal = ui.xterm(
            options={"cursorBlink": True, "fontSize": 12, "theme": self.xterm_theme()},
            on_data=self.on_terminal_input,
        ).style("width:100%;height:100%")
        for line in self._term_lines:
            self.terminal.write(line.replace("\n", "\r\n"))

    def rebuild_terminal(self) -> None:
        self.terminal_slot.clear()
        with self.terminal_slot:
            self.build_terminal()

    def apply_widget_theme(self, theme: str) -> None:
        self._theme = theme
        editor_theme = CM_DARK if theme == "dark" else CM_LIGHT
        self.editor.set_theme(editor_theme)
        self.ld_editor.set_theme(editor_theme)
        self.rebuild_terminal()
        self.btn_theme.set_text("Light" if theme == "dark" else "Dark")

    async def sync_theme_from_browser(self) -> None:
        """Align server-owned widgets with the no-flash browser theme."""
        try:
            theme = await ui.run_javascript(
                "document.documentElement.getAttribute('data-theme') || 'dark'"
            )
        except TimeoutError:
            return
        if theme in ("dark", "light"):
            self.apply_widget_theme(theme)

    def toggle_theme(self):
        """Flip between light and dark, persist the choice, and re-skin JS widgets."""
        theme = "light" if self._theme == "dark" else "dark"
        ui.run_javascript(
            f"document.documentElement.setAttribute('data-theme','{theme}');"
            f"document.documentElement.classList.toggle('q-dark',{str(theme == 'dark').lower()});"
            f"try{{localStorage.setItem('rv32i_theme','{theme}');}}catch(e){{}}"
        )
        self.apply_widget_theme(theme)

    def apply_status(self, text: str, color: str):
        """Set the status label text and color in one shot."""
        self.status_label.set_text(text)
        self.status_label.style(f"color:{color}")

    def boot_done(self):
        self.splash.style("display:none")
        self.main_container.style("display:flex;height:100dvh;flex-direction:column")

    async def check_breakpoint_click(self):
        try:
            addr_hex = await ui.run_javascript('(function(){var a=window._bp_addr;window._bp_addr="";return a})()')
        except TimeoutError:
            # A client can disconnect or refresh between timer ticks.
            return
        if addr_hex:
            try:
                addr = int(addr_hex, 16)
                if addr in self._breakpoints:
                    self._breakpoints.discard(addr)
                else:
                    self._breakpoints.add(addr)
                self.update_asm_view(
                    assembly_highlight_pc(
                        self.sim, self._mode, self.pc_to_line
                    )
                )
            except ValueError:
                pass

    def on_console_write(self, ch: str):
        # Keep scrollback so a theme-triggered terminal rebuild can replay it.
        self._term_lines.append(ch)
        self.terminal.write(ch.replace("\n", "\r\n"))

    def on_terminal_input(self, e):
        for ch in e.data:
            self.terminal.write(ch.replace("\n", "\r\n"))
            self._input_buffer.append(ch)
        if self.sim.waiting_for_input:
            self.sim.resume_input()
            if self.run_timer.active:
                pass  # auto_tick will resume on next tick
            else:
                self.step()  # resume the stalled step

    def read_input(self):
        return self._input_buffer.pop(0) if self._input_buffer else ""

    def load_default(self):
        try:
            with open(DEFAULT_LINKER_SCRIPT, "r") as f:
                self.ld_editor.set_value(f.read())
        except OSError:
            self.ld_editor.set_value("")
        self.update_ld_hint()

        self.on_example_change(DEFAULT_EXAMPLE_ID)

    def on_example_change(self, example_id: str | None) -> None:
        """Load a curated source with its known-good build settings."""
        example = EXAMPLE_PROGRAMS_BY_ID.get(example_id or "")
        if example is None:
            self.apply_status(f"Unknown example: {example_id}", C_RED)
            return

        try:
            source = example.path_for(self._source_language).read_text(encoding="utf-8")
        except OSError as exc:
            self.apply_status(
                f"Could not load example '{example.label}': {exc}", C_RED
            )
            return

        self._arch = example.arch
        self._link_mode = example.link_mode
        self.example_select.value = example.id
        self.arch_select.value = next(
            label
            for label, arch in self._arch_labels.items()
            if arch == example.arch
        )
        self.link_select.value = next(
            label
            for label, mode in self._link_mode_labels.items()
            if mode == example.link_mode
        )
        self.editor.set_language("C" if self._source_language == "c" else "Gas")
        self.editor.set_value(source)
        self._breakpoints.clear()
        self.update_ld_hint()
        self.switch_source_view("source")
        self.compile()

    def on_link_mode_change(self, mode: str):
        self._link_mode = mode
        self.update_ld_hint()
        if mode == LINK_MODE_LINKER:
            self.switch_source_view("linker")

    def on_source_language_change(self, language: str) -> None:
        """Load the selected example in the requested source language."""
        if language not in ("c", "assembly") or language == self._source_language:
            return
        self._source_language = language
        example_id = self.example_select.value
        if example_id in EXAMPLE_PROGRAMS_BY_ID:
            self.on_example_change(example_id)
            return

        self.editor.set_language("C" if language == "c" else "Gas")
        self.editor.set_value(_C_STARTER if language == "c" else _ASSEMBLY_STARTER)
        self._breakpoints.clear()
        self.switch_source_view("source")
        self.compile()

    def source_suffix(self) -> str:
        return ".c" if self._source_language == "c" else ".s"

    def switch_source_view(self, view: str):
        """Toggle between the C source editor and the linker-script editor."""
        self._source_view = view
        show_source = view == "source"
        self.source_editor_wrap.style(f"display:{'flex' if show_source else 'none'};flex:1;height:100%;min-height:0")
        self.linker_editor_wrap.style(f"display:{'flex' if not show_source else 'none'};flex:1;height:100%;min-height:0")
        self.refresh_source_view_toggle()

    def refresh_source_view_toggle(self):
        """Active toggle reads as solid (accent), inactive as outline."""
        active = self._source_view
        for label, is_active, btn in (
            ("code (C/assembly)", active == "source", self.btn_view_source),
            (".ld", active == "linker", self.btn_view_linker),
        ):
            if is_active:
                btn.classes(remove="outline", add="btn-primary")
                btn.props("")
            else:
                btn.classes(remove="btn-primary")
                btn.props("outline")

    def update_ld_hint(self):
        """Tell the user what the current link mode resolves to."""
        if self._link_mode == LINK_MODE_NO_LINKER:
            self.ld_hint.set_text(
                "Link mode: no linker. GCC default script + -Ttext=0x10000 "
                "(text @ 0x00010000, stack @ 0x7FFFFFF0). This editor is ignored."
            )
        else:
            self.ld_hint.set_text(
                "Link mode: linker. The script in this tab is used as-is. "
                "Default = rv32i/scripts/default.ld."
            )

    def fire_irq(self):
        self.sim.raise_external_interrupt()

    def fire_swi(self):
        self.sim.raise_software_interrupt()

    def compile(self):
        # Stop timer callbacks before rebuilding simulator state.
        self.run_timer.deactivate()
        self._program_ready = False
        self.apply_cache_config()
        code = self.editor.value
        if not code.strip():
            self.apply_status("Editor is empty", C_RED)
            return

        tmp = tempfile.NamedTemporaryFile(
            suffix=self.source_suffix(),
            mode="w",
            delete=False,
            dir="/tmp",
        )
        ld_tmp = None
        result = None
        try:
            tmp.write(code)
            tmp.close()

            linker_script = None
            if self._link_mode == LINK_MODE_LINKER:
                ld_code = self.ld_editor.value
                if not ld_code.strip():
                    raise RuntimeError("link mode is 'With linker' but the linker-script editor is empty")
                ld_tmp = tempfile.NamedTemporaryFile(suffix=".ld", mode="w", delete=False, dir="/tmp")
                ld_tmp.write(ld_code)
                ld_tmp.close()
                linker_script = ld_tmp.name

            self.apply_status("Compiling...", C_YELLOW)
            result = build(
                tmp.name,
                march=self._arch,
                link_mode=self._link_mode,
                linker_script=linker_script,
            )
            elf_info = load_elf(result["elf_file"])

            self.sim.load_program(
                result["bin_file"],
                elf_info,
                on_console_read=self.read_input,
            )
            self._mem_snapshot = self.sim.memory_snapshot()

            gp = elf_info.get("global_pointer")
            self._init_sp = elf_info["stack_top"]
            self._init_gp = gp

            asm_text = get_disassembly(result["elf_file"])
            self.asm_lines, self.pc_to_line = parse_disassembly(asm_text)

            self.reset_loaded_state(restore_memory=False)
            self.refresh()
            self.update_mc_panel()  # reflect the zeroed mcycle/minstret/CPI
            self._program_ready = True
            self.apply_status("Compiled OK", C_GREEN)

        except Exception as e:
            self.apply_status(f"Compile error: {e}", C_RED)
            self.asm_lines = [str(e)]
            self.pc_to_line = {}
            self.update_asm_view(-1)
        finally:
            os.unlink(tmp.name)
            if result is not None:
                for artifact in (result["elf_file"], result["bin_file"]):
                    if os.path.exists(artifact):
                        os.unlink(artifact)
            if ld_tmp is not None and os.path.exists(ld_tmp.name):
                os.unlink(ld_tmp.name)

    def require_program_ready(self) -> bool:
        if getattr(self, "_program_ready", True):
            return True
        self.run_timer.deactivate()
        self.apply_status(
            "A successful compile is required before execution",
            C_YELLOW,
        )
        return False

    def step(self):
        if not self.require_program_ready():
            return
        if cycle_limit_reached(self.sim, self._mode):
            self.apply_status("Maximum cycle budget reached -- press Reset", C_YELLOW)
            return
        if not can_advance(self.sim, self._mode):
            self.apply_status("CPU halted -- press Reset", C_RED)
            return
        if self.sim.waiting_for_input:
            self.apply_status("Waiting for input...", C_CYAN)
            return
        breakpoint_pc = current_breakpoint_pc(self.sim, self._mode)
        if breakpoint_pc in self._breakpoints:
            self.apply_status(f"Breakpoint @ 0x{breakpoint_pc:08x}. Click Step again to pass", C_YELLOW)
            self._breakpoints.discard(breakpoint_pc)
            return
        if self._mode == "multi":
            self.advance_multicycle(report_status=True)
            return
        if self._mode == "pipe":
            self.advance_pipeline(report_status=True)
            return
        self.sim.step()
        self.refresh()
        self.update_mc_panel()
        if self.sim.waiting_for_input:
            self.apply_status("Waiting for input...", C_CYAN)
        elif self.sim.proc.halted:
            self.apply_status("Halted", C_RED)

    def advance_multicycle(self, *, report_status: bool) -> None:
        """Advance one multi-cycle clock and refresh its shared UI state."""

        try:
            snap = self.sim.step_clk()
        except NotImplementedError as exc:
            self.run_timer.deactivate()
            self.apply_status(f"MC: {exc}", C_RED)
            self.update_mc_panel(error=str(exc))
            return
        retired = snap is not None
        self.refresh()
        self.update_mc_panel(retired=retired)
        if self.sim.proc.halted:
            self.run_timer.deactivate()
            self.apply_status("Halted", C_RED)
        elif report_status and retired:
            self.apply_status("Multi-cycle: instruction retired", C_GREEN)
        elif report_status:
            self.apply_status("Multi-cycle: one clock advanced", C_CYAN)

    def advance_pipeline(self, *, report_status: bool) -> None:
        """Advance one pipeline clock and refresh its shared UI state."""

        try:
            snap = self.sim.step_pipe()
        except NotImplementedError as exc:
            self.run_timer.deactivate()
            self.apply_status(f"PIPE: {exc}", C_RED)
            self.refresh()
            return
        self.refresh()
        pipe = self.sim.pipeline_state()
        if self.sim.proc.halted and pipe.drained:
            self.run_timer.deactivate()
            self.apply_status("Halted", C_RED)
        elif pipe.draining:
            self.apply_status("Draining pipeline...", C_YELLOW)
        elif report_status and snap is not None:
            self.apply_status("Pipeline: instruction retired", C_GREEN)
        elif report_status:
            self.apply_status("Pipeline: one clock advanced", C_CYAN)

    def update_mc_panel(self, retired: bool = False, error: str | None = None):
        """Render the current or just-retired multi-cycle stage walk."""
        mc = self.sim.multicycle_state()
        mcycle = self.sim.csr.read(0xB00)
        minstret = self.sim.csr.read(0xB02)
        if error is not None:
            self.mc_html.set_content(build_mc_stage_html(error=error))
            return
        if mc is not None:
            idx = (mc.stage_idx - 1) if not retired else (len(mc.stages) - 1)
            idx = max(0, idx)
            self.mc_html.set_content(build_mc_stage_html(
                pc=mc.pc,
                mnemonic=mc.decoded["inst_name"],
                stages=list(mc.stages),
                active_idx=idx,
                mcycle=mcycle,
                minstret=minstret,
                inst_size=mc.inst_size,
                stall_info=mc.stall_info,
            ))
        elif retired and self.sim.history:
            snap = self.sim.history[-1]
            stages = snap.get("stages") or []
            self.mc_html.set_content(build_mc_stage_html(
                pc=snap["pc"],
                mnemonic=snap["inst_name"],
                stages=list(stages),
                active_idx=max(0, len(stages) - 1),
                mcycle=mcycle,
                minstret=minstret,
                inst_size=snap["decoded"].get("_inst_size", 4) if snap.get("decoded") else 4,
                stall_info=snap.get("stall_info"),
            ))
        else:
            self.mc_html.set_content(build_mc_stage_html(
                mcycle=mcycle, minstret=minstret
            ))

    def on_mode_change(self, new_mode: str):
        """Stop Run and transition safely between execution engines."""
        if new_mode not in ("single", "multi", "pipe"):
            return
        if new_mode == self._mode:
            return
        self.run_timer.deactivate()
        reset_for_switch = execution_in_flight(self.sim)
        if reset_for_switch:
            self.reset_loaded_state()
        self._mode = new_mode
        self.apply_mode_ui(new_mode)
        base = getattr(self, "_max_cycles_base", self.sim.max_cycles)
        self.sim.max_cycles = mode_cycle_limit(
            base,
            current_cycles=self.sim.csr.read(0xB00),
            retired=self.sim.csr.read(0xB02),
            mode=new_mode,
        )
        self._max_cycles_base = base
        self.refresh()
        self.update_mc_panel()
        prefix = "Execution reset; " if reset_for_switch else ""
        if self._mode == "multi":
            self.apply_status(f"{prefix}Multi-Cycle mode. Step/Run = one clock", C_CYAN)
        elif self._mode == "pipe":
            self.apply_status(f"{prefix}Pipeline mode. Step/Run = one clock (5 stages)", C_CYAN)
        else:
            self.apply_status(f"{prefix}Single-Cycle mode. Step/Run = one instruction", C_GREEN)

    def apply_mode_ui(self, mode: str) -> None:
        """Apply the visibility contract for controls and diagnostic panels."""

        state = mode_ui_state(mode)
        visibility = (
            ("cache_timing_controls", state.cache_stalls),
            ("pipeline_section", state.pipeline_panel),
            ("mc_section", state.multicycle_panel),
        )
        for name, visible in visibility:
            widget = getattr(self, name, None)
            if widget is not None:
                widget.set_visibility(visible)
        if hasattr(self, "main_container"):
            self.main_container.classes(
                add=f"mode-{mode}",
                remove="mode-single mode-multi mode-pipe",
            )

    def on_pipeline_config_change(self, forwarding: bool | None = None, branch_predict: str | None = None):
        """Apply live forwarding or prediction changes."""
        self.sim.configure_pipeline(forwarding=forwarding, branch_predict=branch_predict)
        if forwarding is not None:
            self.apply_status(
                f"Forwarding {'ON' if self.sim.forwarding else 'OFF'}. Live",
                C_CYAN,
            )
        if branch_predict is not None:
            self.apply_status(
                f"Branch predict: {self.sim.branch_predict}. Live", C_CYAN,
            )

    def run(self):
        if not self.require_program_ready():
            return
        if cycle_limit_reached(self.sim, self._mode):
            self.apply_status("Maximum cycle budget reached -- press Reset", C_YELLOW)
            return
        if not can_advance(self.sim, self._mode):
            self.apply_status("CPU halted -- press Reset", C_RED)
            return
        self.apply_status("Running...", C_GREEN)
        self.run_timer.activate()

    def stop(self):
        self.run_timer.deactivate()
        self.apply_status("Stopped", C_YELLOW)

    def toggle_run(self) -> None:
        """Toggle Run and Stop for the shared keyboard shortcut."""
        if self.run_timer.active:
            self.stop()
        else:
            self.run()

    def reset_loaded_state(self, *, restore_memory: bool = True) -> None:
        """Reset the core and restore the GUI-owned boot image and I/O state."""

        self.run_timer.deactivate()
        self.sim.reset(pc=self.sim.entry_point)
        base = getattr(self, "_max_cycles_base", self.sim.max_cycles)
        self.sim.max_cycles = mode_cycle_limit(
            base,
            current_cycles=self.sim.csr.read(0xB00),
            retired=self.sim.csr.read(0xB02),
            mode=self._mode,
        )
        self._max_cycles_base = base
        self.sim.resume_input()
        self.sim.proc.write_register(2, self._init_sp)
        if self._init_gp is not None:
            self.sim.proc.write_register(3, self._init_gp)
        self.sim.console_buffer.clear()
        self._input_buffer.clear()
        self._term_lines.clear()
        if hasattr(self, "terminal"):
            self.terminal.write("\x1bc")
        if restore_memory and self._mem_snapshot:
            self.sim.restore_memory(self._mem_snapshot)
        self._register_values = tuple(self.sim.proc.registers)
        self._csr_values = self.sim.csr_snapshot()
        self._memory_view_bytes = {}

    def reset(self):
        self.reset_loaded_state()
        self.refresh()
        self.update_mc_panel()
        self.apply_status("Reset", C_CYAN)

    def auto_tick(self):
        if not self.require_program_ready():
            return
        if cycle_limit_reached(self.sim, self._mode):
            self.run_timer.deactivate()
            self.apply_status("Stopped (max cycles)", C_YELLOW)
            return
        if not can_advance(self.sim, self._mode):
            self.run_timer.deactivate()
            self.apply_status("Halted", C_RED)
            return
        if self.sim.waiting_for_input:
            self.apply_status("Waiting for input...", C_CYAN)
            return
        breakpoint_pc = current_breakpoint_pc(self.sim, self._mode)
        if breakpoint_pc in self._breakpoints:
            self.run_timer.deactivate()
            self.apply_status(f"Breakpoint hit @ 0x{breakpoint_pc:08x}", C_RED)
            return
        if self._mode == "multi":
            self.advance_multicycle(report_status=False)
        elif self._mode == "pipe":
            self.advance_pipeline(report_status=False)
        else:
            self.sim.step()
            self.refresh()

    def refresh(self):
        pc = self.sim.proc.read_pc()
        register_values = tuple(self.sim.proc.registers)
        previous_registers = getattr(self, "_register_values", register_values)
        changed_registers = {
            i for i, value in enumerate(register_values)
            if value != previous_registers[i]
        }
        self._register_values = register_values
        self.reg_html.set_content(
            build_register_table_html(list(register_values), changed_registers)
        )
        if self._mem_follow_pc:
            self._mem_base_addr = pc & ~0xF
        self.render_mem_page(pc)
        csr_values = self.sim.csr_snapshot()
        previous_csrs = getattr(self, "_csr_values", csr_values)
        changed_csrs = {
            addr for addr, value in csr_values.items()
            if previous_csrs.get(addr) != value
        }
        self._csr_values = csr_values
        self.csr_html.set_content(build_csr_table_html(csr_values, changed_csrs))
        self.trap_html.set_content(build_trap_log_html(list(self.sim.csr.trap_log)))
        self.update_cache_panel()
        self.cache_header_label.set_text(self.cache_panel_desc())

        self.render_pipeline()

        decode_state = "instruction"
        decoded = None
        decode_pc = None
        mc = self.sim.multicycle_state()
        if self._mode == "multi" and mc is not None:
            inst, decoded, decode_pc = mc.instruction, mc.decoded, mc.pc
        elif self.sim.history and self.sim.history[-1]["decoded"] is None:
            inst = None
            decode_state = "trap"
        elif self.sim.history:
            last = self.sim.history[-1]
            inst, decoded, decode_pc = last["instruction"], last["decoded"], last["pc"]
        else:
            inst = None
            decode_state = "not_started"

        decode_html, bitfield = build_decode_panel(
            inst,
            decoded,
            decode_pc,
            state=decode_state,
        )
        self.decode_html.set_content(decode_html)
        if bitfield is not None:
            payload = json.dumps(bitfield, separators=(",", ":"))
            ui.run_javascript(
                "window.RV32IDecodeBitfield?.render('decode-bitfield', "
                f"{payload});"
            )

        self.update_asm_view(
            assembly_highlight_pc(self.sim, self._mode, self.pc_to_line)
        )

        self.pc_label.set_text(f"PC:0x{pc:08x}")
        self.cycle_label.set_text(f"CYCLE:{self.sim.csr.read(0xB00):04d}")
        if self.sim.timer:
            self.mtime_label.set_text(f"MTIME:{self.sim.timer.mtime}")
            self.mtimecmp_label.set_text(f"MTIMECMP:{self.sim.timer.mtimecmp}")

    def render_pipeline(self):
        """Render the real latch and timing views in Pipeline mode."""
        if self._mode != "pipe":
            return
        pipe = self.sim.pipeline_state()
        self.prediction_stats_label.set_text(
            format_branch_prediction_stats(pipe.branch_prediction)
        )
        latch_html = build_pipeline_latch_html(
            if_id=pipe.if_id,
            id_ex=pipe.id_ex,
            ex_mem=pipe.ex_mem,
            mem_wb=pipe.mem_wb,
            mcycle=pipe.mcycle,
            minstret=pipe.minstret,
            stalls=pipe.stalls,
            flushes=pipe.flushes,
        )
        gantt_html = build_pipeline_gantt_html(list(pipe.trace))
        self.pipeline_latch_html.set_content(latch_html)
        self.pipeline_gantt_html.set_content(gantt_html)

    _CACHE_SIZE_PRESETS = (8, 16, 32, 64, 128, 256)
    _CACHE_BLOCK_PRESETS = (16, 32, 64, 128)
    _CACHE_WAY_PRESETS = (1, 2, 4, 8, 16)

    def valid_cache_sizes(self) -> list[int]:
        """Return valid power-of-two sizes for the selected block and ways."""
        block = self._cache_block
        ways = self._cache_ways
        out = []
        for kb in self._CACHE_SIZE_PRESETS:
            size = kb * 1024
            if size < block * ways:
                continue
            num_sets = size // (block * ways)
            if num_sets >= 1 and (num_sets & (num_sets - 1)) == 0:
                out.append(size)
        return out

    def cache_panel_desc(self) -> str:
        """One-line geometry descriptor for the cache panel header."""
        if self._cache_ways == 1:
            assoc = "Direct-Mapped"
        else:
            policy = "LRU" if self._cache_policy == "lru" else "FIFO"
            assoc = f"{self._cache_ways}-way Set-Assoc ({policy})"
        return f"Split L1 | {assoc} | {self._cache_block}B block | {self._cache_size // 1024}KB"

    def on_cache_config_change(self, size: int, block: int, ways: int, policy: str = "fifo") -> None:
        """Clamp a geometry selection, rebuild caches, and recompile."""
        self._cache_block = block
        self._cache_ways = ways
        self._cache_policy = policy
        valid = self.valid_cache_sizes()
        if size not in valid and valid:
            size = min(valid, key=lambda s: abs(s - size))
        self._cache_size = size
        self.cache_size_select.options = {s: f"{s // 1024} KB" for s in valid}
        self.cache_size_select.value = size
        self._cache_page = 0
        self._cache_lookup_idx = -1
        self.apply_cache_config()
        if self.sim.loaded:
            self.compile()
        else:
            self.refresh()

    def apply_cache_config(self) -> None:
        """Push the current GUI geometry into the simulator (if changed)."""
        self.sim.configure_cache(self._cache_size, self._cache_ways, self._cache_block, self._cache_policy)

    def on_cache_stall_change(self, i, d) -> None:
        """Apply non-negative cache-miss timing penalties."""
        self._i_miss_stall = max(0, int(i or 0))
        self._d_miss_stall = max(0, int(d or 0))
        self.apply_cache_stalls()

    def apply_cache_stalls(self) -> None:
        """Push the current miss-stall penalties into the simulator."""
        self.sim.configure_cache_stalls(self._i_miss_stall, self._d_miss_stall)

    def active_cache(self):
        """The cache instance currently shown in the panel."""
        return self.sim.icache if self._cache_view == "I" else self.sim.dcache

    def set_cache_view(self, view: str):
        self._cache_view = view
        self._cache_page = 0
        self._cache_lookup_idx = -1
        self.refresh_cache_page()

    def update_cache_panel(self):
        i = self.sim.icache.get_stats()
        d = self.sim.dcache.get_stats()
        self.cache_stats_html.set_content(build_cache_stats_html(i, d))
        for label, target in (("D", self.btn_cache_view_d), ("I", self.btn_cache_view_i)):
            if self._cache_view == label:
                target.classes(add="btn-selected")
                target.props("color=primary")
            else:
                target.classes(remove="btn-selected")
                target.props("")

        cache = self.active_cache()
        last = cache.last_access
        self.cache_access_html.set_content(
            build_cache_access_html(last, cache, self._cache_view)
        )

        total_lines = cache.num_lines
        if last is not None:
            way = getattr(last, "way", -1)
            flat = last.index * cache.ways + (way if way >= 0 else 0)
            self._cache_page = flat // self._cache_lines_per_page

        start = self._cache_page * self._cache_lines_per_page
        self.cache_html.set_content(build_cache_table_html(cache, start, self._cache_lines_per_page, last, self._cache_lookup_idx))

        total_pages = (total_lines + self._cache_lines_per_page - 1) // self._cache_lines_per_page
        end = min(start + self._cache_lines_per_page, total_lines)
        self.cache_page_label.set_text(f"Lines {start}-{end - 1} / {total_lines}  (Page {self._cache_page + 1}/{total_pages})")

    def update_asm_view(self, current_pc: int):
        self.asm_html.set_content(
            build_asm_view_html(self.asm_lines, self.pc_to_line, current_pc, self._breakpoints)
        )

    def render_mem_page(self, pc: int | None = None):
        """Re-render the memory table + page label from the current base address."""
        if pc is None:
            pc = self.sim.proc.read_pc()
        current_bytes = {
            addr: self.sim.mem.peek_byte(addr)
            for addr in range(
                self._mem_base_addr,
                self._mem_base_addr + self._mem_page_size,
            )
        }
        previous_bytes = getattr(self, "_memory_view_bytes", {})
        changed_addresses = {
            addr for addr, value in current_bytes.items()
            if addr in previous_bytes and previous_bytes[addr] != value
        }
        self._memory_view_bytes = current_bytes
        self.mem_html.set_content(
            build_memory_table_html(
                self.sim.mem,
                self._mem_base_addr,
                self._mem_page_size // 16,
                pc,
                changed_addresses,
            )
        )
        self.mem_page_label.set_text(
            f"0x{self._mem_base_addr:08x} - 0x{self._mem_base_addr + self._mem_page_size - 1:08x}"
        )

    def mem_prev_page(self):
        self._mem_follow_pc = False
        self._mem_base_addr = max(0, self._mem_base_addr - self._mem_page_size)
        self.render_mem_page()

    def mem_next_page(self):
        self._mem_follow_pc = False
        self._mem_base_addr = min(0xFFFFFFFF - self._mem_page_size + 1, self._mem_base_addr + self._mem_page_size)
        self.render_mem_page()

    def mem_goto_pc(self):
        pc = self.sim.proc.read_pc()
        max_base = 0x100000000 - self._mem_page_size
        self._mem_base_addr = min(pc & ~0xF, max_base)
        self._mem_follow_pc = True
        self.render_mem_page(pc)

    def mem_goto_addr(self):
        addr_str = str(self.mem_addr_input.value or "").strip()
        if not addr_str:
            return
        try:
            addr = int(addr_str, 0)
        except ValueError:
            self.apply_status("Address must be an RV32 value (0x00000000-0xffffffff)", C_RED)
            return
        if not 0 <= addr <= 0xFFFFFFFF:
            self.apply_status("Address must be an RV32 value (0x00000000-0xffffffff)", C_RED)
            return
        max_base = 0x100000000 - self._mem_page_size
        self._mem_base_addr = min(addr & ~0xF, max_base)
        self._mem_follow_pc = False
        self.render_mem_page()

    def cache_prev_page(self):
        cache = self.active_cache()
        total_lines = cache.num_lines
        total_pages = (total_lines + self._cache_lines_per_page - 1) // self._cache_lines_per_page
        self._cache_page = (self._cache_page - 1) % total_pages
        self.refresh_cache_page()

    def cache_next_page(self):
        cache = self.active_cache()
        total_lines = cache.num_lines
        total_pages = (total_lines + self._cache_lines_per_page - 1) // self._cache_lines_per_page
        self._cache_page = (self._cache_page + 1) % total_pages
        self.refresh_cache_page()

    def cache_goto_last(self):
        cache = self.active_cache()
        last = cache.last_access
        if last is not None:
            way = getattr(last, "way", -1)
            flat = last.index * cache.ways + (way if way >= 0 else 0)
            self._cache_page = flat // self._cache_lines_per_page
        self.refresh_cache_page()

    def refresh_cache_page(self):
        cache = self.active_cache()
        last = cache.last_access
        total_lines = cache.num_lines
        self.cache_access_html.set_content(
            build_cache_access_html(last, cache, self._cache_view)
        )
        start = self._cache_page * self._cache_lines_per_page
        self.cache_html.set_content(build_cache_table_html(cache, start, self._cache_lines_per_page, last, self._cache_lookup_idx))
        total_pages = (total_lines + self._cache_lines_per_page - 1) // self._cache_lines_per_page
        end = min(start + self._cache_lines_per_page, total_lines)
        self.cache_page_label.set_text(f"Lines {start}-{end - 1} / {total_lines}  (Page {self._cache_page + 1}/{total_pages})")

    def cache_lookup(self):
        addr_str = self.cache_lookup_input.value.strip()
        if not addr_str:
            return
        try:
            addr = int(addr_str, 0)  # accepts 0x hex or decimal
            cache = self.active_cache()
            set_idx = cache.set_index_of(addr)
            # For ways>1, highlight the whole set: page to the set's first line.
            flat = set_idx * cache.ways
            self._cache_lookup_idx = set_idx
            self._cache_page = flat // self._cache_lines_per_page
            self.refresh_cache_page()
        except ValueError:
            pass

    def cache_lookup_pc(self):
        # PC is an instruction address — switch to the I-cache view for it.
        self._cache_view = "I"
        pc = self.sim.proc.read_pc()
        cache = self.active_cache()
        set_idx = cache.set_index_of(pc)
        flat = set_idx * cache.ways
        self._cache_lookup_idx = set_idx
        self._cache_page = flat // self._cache_lines_per_page
        self.refresh_cache_page()


def build_page() -> None:
    """Build one browser client's simulator workspace."""
    SimulatorUI()


def main() -> None:
    """Launch the NiceGUI web simulator. Entry point for `rv32i-gui`."""
    port = os.environ.get("RV32I_GUI_PORT", os.environ.get("PORT", "8080"))
    try:
        ui.run(
            root=build_page,
            title="RV32I Simulator",
            host=os.environ.get("RV32I_GUI_HOST", "127.0.0.1"),
            port=int(port),
            reload=False,
            dark=False,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
