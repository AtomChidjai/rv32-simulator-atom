"""Pipeline timing-grid renderer tests."""

from gui.renderers import build_pipeline_gantt_html


def slot(fetch_id, pc, mnemonic):
    """Build one non-bubble trace slot with stable dynamic identity."""
    return {"fetch_id": fetch_id, "pc": pc, "mnemonic": mnemonic}


def trace_entry(
    cycle, if_id, id_ex, ex_mem, mem_wb, *,
    stall=False, flush=False, retired=None, cache_stall=None,
    hazard_stall_stage=None,
):
    """Build one pipe_trace entry. Each slot is an identity dict or None."""
    return {
        "cycle": cycle,
        "slots": {"IF/ID": if_id, "ID/EX": id_ex, "EX/MEM": ex_mem, "MEM/WB": mem_wb},
        "stall": stall, "flush": flush, "retired": retired,
        "cache_stall": cache_stall, "hazard_stall_stage": hazard_stall_stage,
    }


def cache_stall(stage, index, total, slot):
    return {"stage": stage, "index": index, "total": total, "slot": slot}


def row(html, fetch_id):
    return html.split(f'data-fetch-id="{fetch_id}"', 1)[1].split("</tr>", 1)[0]


def test_gantt_empty_trace():
    """No trace → the 'not started' placeholder, not a crashed render."""
    html = build_pipeline_gantt_html([])
    assert "not started" in html
    assert "<table" not in html


def test_gantt_renders_diagonal():
    """A clean 5-stage flow (one instruction IF→WB across 5 clocks) renders
    one row with IF, ID, EX, MEM, WB in consecutive columns."""
    # Instruction at pc=0x100, mnemonic 'addi', enters IF at c0.
    inst = slot(0, 0x100, "addi")
    trace = [
        trace_entry(0, inst, None, None, None),
        trace_entry(1, None, inst, None, None),
        trace_entry(2, None, None, inst, None),
        trace_entry(3, None, None, None, inst),
        trace_entry(4, None, None, None, None, retired=0),
    ]
    html = build_pipeline_gantt_html(trace)
    assert "<table" in html
    assert "addi" in html
    # All five stage abbreviations should appear.
    for stage in ("IF", "ID", "EX", "MEM", "WB"):
        assert stage in html, f"stage {stage} missing from gantt"
    # Column headers for cycles 0..4.
    for c in range(5):
        assert f"C{c}" in html


def test_gantt_shows_two_overlapping_instructions():
    """Two instructions in flight: the second enters IF one clock after the
    first, forming the classic diagonal. Both should render as rows."""
    a = slot(0, 0x100, "addi")
    b = slot(1, 0x104, "add")
    trace = [
        trace_entry(0, a, None, None, None),
        trace_entry(1, b, a, None, None),
        trace_entry(2, None, b, a, None),
        trace_entry(3, None, None, b, a, retired=0),
        trace_entry(4, None, None, None, b, retired=1),
    ]
    html = build_pipeline_gantt_html(trace)
    assert "addi" in html and "add" in html
    # Both rows present (mnemonic appears at least once each).
    assert html.count("addi") >= 1
    assert html.count("add") >= 1


def test_gantt_window_caps_columns():
    """A trace longer than window_cycles renders only the last window."""
    inst = slot(0, 0x100, "nop")
    trace = [trace_entry(c, inst if c == 0 else None, inst if c == 1 else None, None, None)
             for c in range(40)]
    html = build_pipeline_gantt_html(trace, window_cycles=8)
    # Only the last 8 cycle headers should appear; the earliest ones shouldn't.
    assert "C39" in html   # last cycle
    assert "C0" not in html or "C0<" not in html   # first cycle windowed out


def test_gantt_defaults_to_complete_clock_and_instruction_history():
    """The Pipeline GUI keeps the first clock and instruction visible."""
    trace = [
        trace_entry(c, slot(c, 0x100 + c * 4, "nop"), None, None, None)
        for c in range(40)
    ]

    html = build_pipeline_gantt_html(trace)

    assert ">C0</th>" in html
    assert ">C39*</th>" in html
    assert 'data-fetch-id="0"' in html
    assert 'data-fetch-id="39"' in html
    assert "40 instruction(s) shown" in html


def test_gantt_forwarding_load_use_stalls_consumer_in_id_and_younger_in_if():
    """A forwarding load-use interlock is detected after the consumer enters ID."""
    load = slot(0, 0x100, "lw")
    consumer = slot(1, 0x104, "add")
    younger = slot(2, 0x108, "ebreak")
    trace = [
        trace_entry(0, load, None, None, None),
        trace_entry(1, consumer, load, None, None),
        trace_entry(
            2, consumer, None, load, None,
            stall=True, hazard_stall_stage="ID",
        ),
        trace_entry(3, younger, consumer, None, load),
        trace_entry(4, None, younger, consumer, None, retired=0),
    ]

    html = build_pipeline_gantt_html(trace)
    consumer_row = row(html, 1)
    younger_row = row(html, 2)

    assert consumer_row.count(">IF</td>") == 1
    assert consumer_row.count(">ID</td>") == 2
    assert 'data-stall-stage="ID"' in consumer_row
    assert younger_row.count(">IF</td>") == 2
    assert 'data-stall-stage="IF"' in younger_row


def test_gantt_no_forwarding_load_use_stall_repeats_held_id_stage():
    """Without forwarding, a load-use consumer remains at ID until WB."""
    load = slot(0, 0x100, "lw")
    consumer = slot(1, 0x104, "add")
    trace = [
        trace_entry(0, consumer, load, None, None),
        trace_entry(1, None, consumer, load, None),
        trace_entry(2, None, consumer, None, load, stall=True),
        trace_entry(3, None, consumer, None, None, stall=True, retired=0),
        trace_entry(4, None, None, consumer, None),
    ]

    html = build_pipeline_gantt_html(trace)
    consumer_row = row(html, 1)

    assert consumer_row.count(">ID</td>") == 3
    assert consumer_row.count('data-stall-stage="ID"') == 2


def test_gantt_marks_stall_at_window_boundary():
    """A stall remains visible when it is the first clock in the window."""
    consumer = slot(1, 0x104, "add")
    trace = [
        trace_entry(0, consumer, None, None, None),
        trace_entry(1, consumer, None, None, None, stall=True),
        trace_entry(2, None, consumer, None, None),
    ]

    html = build_pipeline_gantt_html(trace, window_cycles=2)
    consumer_row = html.split('data-fetch-id="1"', 1)[1].split("</tr>", 1)[0]
    assert 'data-stall-stage="IF"' in consumer_row
    assert ">IF</td>" in consumer_row


def test_gantt_icache_miss_repeats_if_with_progress():
    """A pending Inst 2 is visible at IF for both penalty clocks while Inst 1
    continues through ID and EX; later instructions have not entered yet."""
    inst1 = slot(0, 0x3C, "addi")
    inst2 = slot(1, 0x40, "addi")
    inst3 = slot(2, 0x44, "addi")
    trace = [
        trace_entry(1, inst1, None, None, None),
        trace_entry(
            2, None, inst1, None, None, stall=True,
            cache_stall=cache_stall("IF", 1, 2, inst2),
        ),
        trace_entry(
            3, None, None, inst1, None, stall=True,
            cache_stall=cache_stall("IF", 2, 2, inst2),
        ),
        trace_entry(4, inst2, None, None, inst1),
        trace_entry(5, inst3, inst2, None, None, retired=0),
    ]

    html = build_pipeline_gantt_html(trace)
    inst2_row = row(html, 1)
    inst3_row = row(html, 2)

    assert 'data-cycle="2" data-cache-stall-stage="IF"' in inst2_row
    assert 'data-cycle="3" data-cache-stall-stage="IF"' in inst2_row
    assert inst2_row.count(">IF</td>") == 3
    assert ">IF S" not in inst2_row
    assert 'data-cycle="4" data-stage="IF"' in inst2_row
    assert 'data-cycle="5"' in inst3_row
    assert 'data-stage="IF"' in inst3_row
    assert 'aria-current="true"' in inst3_row


def test_gantt_dcache_miss_repeats_mem_and_freezes_younger_stages():
    """A D-miss shows Inst 2 at MEM and holds Inst 3/4 at EX/ID for both
    penalty clocks, matching the requested five-stage schedule."""
    inst1 = slot(0, 0x00, "addi")
    inst2 = slot(1, 0x04, "sw")
    inst3 = slot(2, 0x08, "addi")
    inst4 = slot(3, 0x0C, "addi")
    trace = [
        trace_entry(1, inst1, None, None, None),
        trace_entry(2, inst2, inst1, None, None),
        trace_entry(3, inst3, inst2, inst1, None),
        trace_entry(4, inst4, inst3, inst2, inst1),
        trace_entry(
            5, inst4, inst3, inst2, None, stall=True, retired=0,
            cache_stall=cache_stall("MEM", 1, 2, inst2),
        ),
        trace_entry(
            6, inst4, inst3, inst2, None, stall=True,
            cache_stall=cache_stall("MEM", 2, 2, inst2),
        ),
        trace_entry(7, None, inst4, inst3, inst2),
        trace_entry(8, None, None, inst4, inst3, retired=1),
        trace_entry(9, None, None, None, inst4, retired=2),
        trace_entry(10, None, None, None, None, retired=3),
    ]

    html = build_pipeline_gantt_html(trace)
    inst2_row = row(html, 1)
    inst3_row = row(html, 2)
    inst4_row = row(html, 3)

    assert inst2_row.count('data-cache-stall-stage="MEM"') == 2
    assert ">MEM S" not in inst2_row
    assert inst3_row.count('data-stage="EX"') == 3
    assert inst4_row.count('data-stage="ID"') == 3


def test_gantt_current_cycle_highlighted():
    """The latest cycle has a visible marker and current-state semantics."""
    inst = slot(0, 0x100, "addi")
    trace = [
        trace_entry(0, inst, None, None, None),
        trace_entry(1, None, inst, None, None),
    ]
    html = build_pipeline_gantt_html(trace)
    assert "background:" in html
    assert ">C1*</th>" in html
    assert 'aria-current="true"' in html


def test_gantt_handles_bubbles_only_trace():
    """A trace where every latch is a bubble (e.g. right after reset, before
    the first fetch completes) renders the placeholder or an empty-ish grid
    without crashing."""
    trace = [trace_entry(0, None, None, None, None)]
    html = build_pipeline_gantt_html(trace)
    # No instruction rows, but it must not crash. Either the placeholder or
    # a table with no body rows.
    assert isinstance(html, str)


def test_gantt_loop_visits_same_pc_are_distinct_rows():
    """Two dynamic visits to one loop PC keep separate rows and WB markers."""
    first = slot(10, 0x100, "addi")
    second = slot(11, 0x100, "addi")
    trace = [
        trace_entry(0, first, None, None, None),
        trace_entry(1, second, first, None, None),
        trace_entry(2, None, second, first, None),
        trace_entry(3, None, None, second, first),
        trace_entry(4, None, None, None, second, retired=10),
        trace_entry(5, None, None, None, None, retired=11),
    ]

    html = build_pipeline_gantt_html(trace)
    for fetch_id in (10, 11):
        assert html.count(f'data-fetch-id="{fetch_id}"') == 1
        row = html.split(f'data-fetch-id="{fetch_id}"', 1)[1].split("</tr>", 1)[0]
        assert row.count(">WB</td>") == 1


def test_gantt_flushed_fetch_crosses_last_real_stage_and_never_receives_wb():
    """A wrong-path row ends at its last real stage without a synthetic stage."""
    branch = slot(20, 0x100, "beq")
    wrong_path = slot(21, 0x104, "addi")
    trace = [
        trace_entry(0, branch, None, None, None),
        trace_entry(1, wrong_path, branch, None, None),
        trace_entry(2, None, None, branch, None, flush=True),
        trace_entry(3, None, None, None, branch),
        trace_entry(4, None, None, None, None, retired=20),
    ]

    html = build_pipeline_gantt_html(trace)
    wrong_row = html.split('data-fetch-id="21"', 1)[1].split("</tr>", 1)[0]
    assert ">IF</td>" in wrong_row
    assert 'data-flush-stage="IF"' in wrong_row
    assert "text-decoration:line-through" in wrong_row
    assert ">X</td>" not in wrong_row
    assert ">WB</td>" not in wrong_row


def test_gantt_does_not_flush_older_instruction_retiring_with_branch_redirect():
    """An older WB retirement is not a casualty of a younger branch flush."""
    load = slot(20, 0x100, "lw")
    branch = slot(21, 0x104, "beq")
    wrong_path = slot(22, 0x108, "addi")
    trace = [
        trace_entry(0, wrong_path, branch, None, load),
        trace_entry(1, None, None, branch, None, flush=True, retired=20),
        trace_entry(2, None, None, None, branch),
        trace_entry(3, None, None, None, None, retired=21),
    ]

    html = build_pipeline_gantt_html(trace)
    load_row = row(html, 20)
    wrong_row = row(html, 22)

    assert ">MEM</td>" in load_row
    assert ">WB</td>" in load_row
    assert "text-decoration:line-through" not in load_row
    assert "data-flush-stage" not in load_row
    assert "text-decoration:line-through" in wrong_row
