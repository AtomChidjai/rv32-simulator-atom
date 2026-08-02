"""HTML escaping regressions for user-controlled disassembly text."""

from gui.renderers import build_asm_view_html


def test_asm_view_escapes_double_quote():
    line_with_quote = '  10074:\tdead\t"onmouseover=alert(1)'
    html = build_asm_view_html([line_with_quote], {}, current_pc=0xFFFFFFFF, breakpoints=set())

    assert '"onmouseover' not in html
    assert "&quot;" in html


def test_asm_view_escapes_single_quote():
    line = "  10074:\tnop\t; don't inject"
    html = build_asm_view_html([line], {}, current_pc=0xFFFFFFFF, breakpoints=set())

    assert "&#x27;" in html
    assert "don't" not in html


def test_asm_view_still_escapes_angle_brackets_and_amp():
    """Ampersands and angle brackets remain escaped."""
    line = "  10074:\tnop\t<>&"
    html = build_asm_view_html([line], {}, current_pc=0xFFFFFFFF, breakpoints=set())

    assert "&lt;" in html
    assert "&gt;" in html
    assert "&amp;" in html


def test_asm_view_escapes_symbol_names():
    lines = ["00010000 <start&stop>:"]

    html = build_asm_view_html(
        lines, {}, current_pc=0xFFFFFFFF, breakpoints=set()
    )

    assert "start&amp;stop" in html


def test_asm_view_breakpoint_and_current_pc_render_without_error():
    """Edge: breakpoints + current_pc highlight paths must not throw on
    attacker-shaped line content. Pure smoke test.
    """
    lines = ["  10074:\taddi\ta0,a0,1", "  10078:\tbeq\ta0,a1,\"weird\""]
    pc_to_line = {0x10074: 0, 0x10078: 1}
    html = build_asm_view_html(lines, pc_to_line, current_pc=0x10074, breakpoints={0x10078})

    assert isinstance(html, str)
    # The addr attr is rendered as 8-digit hex (see renderers.py:437 f"{addr:08x}").
    assert 'data-addr="00010078"' in html   # breakpoint row carries its addr attr
