"""Multi-cycle panel renderer tests."""

from gui.renderers import build_mc_stage_html


def count(text: str, needle: str) -> int:
    return text.count(needle)


def test_mc_renderer_idle_shows_prompt_and_cpi():
    """Idle state renders the prompt + the CPI readout (CPI=0 with no minstret)."""
    html = build_mc_stage_html(mcycle=0, minstret=0)
    assert "idle" in html
    assert "press Step" in html
    assert "Step CLK" not in html
    assert "mcycle=0" in html
    assert "minstret=0" in html
    assert "CPI=0.00" in html


def test_mc_renderer_idle_with_history_shows_cpi():
    """With non-zero counters, the idle readout shows the live CPI."""
    html = build_mc_stage_html(mcycle=87, minstret=20)
    assert "CPI=4.35" in html


def test_mc_renderer_load_has_five_stage_columns():
    """A load renders five flat stages below the raised instruction context."""
    html = build_mc_stage_html(
        pc=0x10, mnemonic="lw",
        stages=["IF", "ID", "EX", "MEM", "WB"],
        active_idx=3, mcycle=20, minstret=4, inst_size=4,
    )
    assert 'class="panel-context-band mc-context"' in html
    assert count(html, 'class="mc-stage ') == 5
    for s in ("IF", "ID", "EX", "MEM", "WB"):
        assert s in html


def test_mc_renderer_branch_has_three_stage_columns():
    """A branch keeps its variable-length three-stage walk."""
    html = build_mc_stage_html(
        pc=0x20, mnemonic="beq",
        stages=["IF", "ID", "EX"],
        active_idx=2, mcycle=30, minstret=9, inst_size=4,
    )
    assert count(html, 'class="mc-stage ') == 3
    assert "MEM" not in html
    assert "WB" not in html


def test_mc_renderer_active_stage_highlighted_once():
    """Exactly one stage cell is highlighted as the active stage."""
    html = build_mc_stage_html(
        pc=0x10, mnemonic="addi",
        stages=["IF", "ID", "EX", "WB"],
        active_idx=2, mcycle=10, minstret=2, inst_size=4,
    )
    assert html.count('class="mc-stage mc-stage-active"') == 1
    assert html.count('aria-current="step"') == 1
    assert "3/4" in html


def test_mc_renderer_shows_pc_and_mnemonic():
    """The in-flight instruction's PC and mnemonic appear in the row."""
    html = build_mc_stage_html(
        pc=0xABC, mnemonic="mul",
        stages=["IF", "ID", "EX", "WB"],
        active_idx=1, mcycle=5, minstret=1, inst_size=4,
    )
    assert "0x00000abc" in html
    assert "mul" in html


def test_mc_renderer_shows_inst_width():
    """The instruction width (bytes) is shown — useful for RV32C awareness."""
    html_32 = build_mc_stage_html(
        pc=0, mnemonic="addi", stages=["IF", "ID", "EX", "WB"],
        active_idx=0, mcycle=0, minstret=0, inst_size=4,
    )
    html_16 = build_mc_stage_html(
        pc=0, mnemonic="addi", stages=["IF", "ID", "EX", "WB"],
        active_idx=0, mcycle=0, minstret=0, inst_size=2,
    )
    assert "4B" in html_32
    assert "2B" in html_16


def test_mc_renderer_error_renders_banner():
    """An error (e.g. out-of-scope instruction) renders a clear banner."""
    html = build_mc_stage_html(error="step_clk: instruction 'fence' not in scope")
    assert "MC engine error" in html
    assert "fence" in html


def test_mc_renderer_cpi_from_counters():
    """The CPI column is computed from mcycle/minstret."""
    html = build_mc_stage_html(
        pc=0, mnemonic="add", stages=["IF", "ID", "EX", "WB"],
        active_idx=3, mcycle=44, minstret=11, inst_size=4,
    )
    assert "CPI=4.00" in html or "4.00" in html  # CPI column


def test_mc_renderer_active_shows_live_counters():
    """The mcycle/minstret counters stay visible while an instruction is in
    flight (regression: they used to vanish, only the idle view showed them)."""
    html = build_mc_stage_html(
        pc=0, mnemonic="add", stages=["IF", "ID", "EX", "WB"],
        active_idx=1, mcycle=7, minstret=2, inst_size=4,
    )
    # mcycle/minstret must be present as their own columns, not just the CPI.
    assert "mcycle" in html
    assert "minstret" in html
    assert ">7<" in html    # the mcycle value cell
    assert ">2<" in html    # the minstret value cell


# ── STALL(N) badge (cache-miss stall visualization) ──────────────────────

def test_mc_renderer_stall_badge_on_active_if_cell():
    """An I-cache miss stall shows STALL(N) on the active IF cell."""
    html = build_mc_stage_html(
        pc=0, mnemonic="addi", stages=["IF", "ID", "EX", "WB"],
        active_idx=0, mcycle=3, minstret=0, inst_size=4,
        stall_info=("IF", 2),
    )
    assert "STALL(2)" in html


def test_mc_renderer_stall_badge_on_mem_cell():
    """A D-cache miss stall shows STALL(N) on the MEM cell."""
    html = build_mc_stage_html(
        pc=0x10, mnemonic="lw", stages=["IF", "ID", "EX", "MEM", "WB"],
        active_idx=3, mcycle=20, minstret=4, inst_size=4,
        stall_info=("MEM", 4),
    )
    assert "STALL(4)" in html


def test_mc_renderer_no_stall_badge_when_none():
    """With stall_info=None, no STALL marker appears (normal hit/step)."""
    html = build_mc_stage_html(
        pc=0, mnemonic="addi", stages=["IF", "ID", "EX", "WB"],
        active_idx=1, mcycle=5, minstret=1, inst_size=4,
        stall_info=None,
    )
    assert "STALL" not in html


def test_mc_renderer_stall_badge_on_retired_store_mem():
    """Regression: a store retiring on its MEM stall step must still render the
    badge. This mirrors the GUI path where _mc is None (retired) and the panel
    must reconstruct the instruction from history[-1] with active_idx on the
    final stage."""
    html = build_mc_stage_html(
        pc=0x1a, mnemonic="sw", stages=["IF", "ID", "EX", "MEM"],
        active_idx=3, mcycle=38, minstret=9, inst_size=4,
        stall_info=("MEM", 4),
    )
    assert "STALL(4)" in html
