"""Console-input behavior and state parity across execution engines."""

from rv32i import Simulator
from rv32i.devices import register_default_devices

from tests.test_pipeline import EBREAK, encode_i, encode_u, encode_words


# Tiny console-read/store/halt program.
def console_read_prog():
    """Read one byte from MMIO_CONSOLE_IN (0x10000004) into x1, store it to
    0x1000, then ebreak. The load is the console-in read."""
    lui_x5_console = encode_u(0x10000, 5, 0b0110111)        # lui x5, 0x10000  → x5 = 0x10000000
    lb_x1_in = encode_i(4, 5, 4, 1, 0b0000011)              # lb x1, 4(x5)     → x1 = console char
    lui_x6_scratch = encode_u(0x1, 6, 0b0110111)            # lui x6, 0x1      → x6 = 0x1000
    sw_x1_scratch = (                                # sw x1, 0(x6)
        ((0 & 0xFE0) << 20) | (1 << 20) | (6 << 15) | (2 << 12) | ((0 & 0x1F) << 7) | 0b0100011
    ) & 0xFFFFFFFF
    return [lui_x5_console, lb_x1_in, lui_x6_scratch, sw_x1_scratch, EBREAK]


def new_simulator(prog_words, *, forwarding=True, branch_predict="nottaken", max_cycles=4000):
    sim = Simulator(max_cycles=max_cycles, forwarding=forwarding, branch_predict=branch_predict)
    sim.mem.load_bytes(0, encode_words(prog_words))
    return sim


def wire_input(sim, chars):
    """Register devices with a console-read callback that drains ``chars``
    (a list of 1-char strings). When the list empties, returns '' (stall)."""
    queue = list(chars)

    def read():
        return queue.pop(0) if queue else ""

    sim.timer = register_default_devices(
        sim.mem, sim.csr,
        on_console_write=sim.on_console,
        on_console_read=read,
    )
    sim.proc.reset(pc=0)
    # Expose the queue so a test can append more chars mid-run (stall/resume).
    sim._test_input_queue = queue


def run_sc(sim):
    # step() returns None only when waiting for console input; with pre-seeded
    # input that doesn't happen, so loop to halt. (The stall scenario drives
    # step_pipe manually, not this helper.)
    while not sim.proc.halted and sim.proc.cycles < sim.max_cycles:
        sim.step()


def run_clk(sim):
    # step_clk() returns None on every non-retirement clock — that's NORMAL,
    # not a stop condition. Loop to halt.
    while not sim.proc.halted and sim.proc.cycles < sim.max_cycles:
        sim.step_clk()


def run_pipe(sim):
    while True:
        if sim.proc.halted and sim.if_id.bubble and sim.id_ex.bubble \
                and sim.ex_mem.bubble and sim.mem_wb.bubble:
            break
        if not sim.proc.halted and sim.proc.cycles >= sim.max_cycles:
            break
        sim.step_pipe()


def assert_3way(sc, clk, pipe, *, mem_words=None):
    """Assert single-cycle, multi-cycle, and pipeline reach identical state."""
    assert sc.proc.registers == clk.proc.registers == pipe.proc.registers, (
        f"register mismatch: sc={sc.proc.registers[:8]} "
        f"clk={clk.proc.registers[:8]} pipe={pipe.proc.registers[:8]}"
    )
    assert sc.proc.read_pc() == clk.proc.read_pc() == pipe.proc.read_pc(), (
        f"PC mismatch: sc={sc.proc.read_pc():#x} clk={clk.proc.read_pc():#x} "
        f"pipe={pipe.proc.read_pc():#x}"
    )
    if mem_words:
        for off in mem_words:
            a, b, c = sc.mem.read_word(off), clk.mem.read_word(off), pipe.mem.read_word(off)
            assert a == b == c, (
                f"mem[0x{off:08x}] mismatch: sc=0x{a:08x} clk=0x{b:08x} pipe=0x{c:08x}"
            )


# ── Scenario A: input pre-seeded (no stall) ────────────────────────────

def test_console_input_preseeded_3engine_parity():
    """When input is available before the load reaches MEM, all three engines
    read the same char and reach identical state. No stall path exercised
    here (see the next test for that), but this pins the basic MEM-load-on-
    device contract shared by all engines."""
    prog = console_read_prog()
    sc = new_simulator(prog);   wire_input(sc, ["X"]);   run_sc(sc)
    clk = new_simulator(prog);  wire_input(clk, ["X"]);  run_clk(clk)
    pipe = new_simulator(prog); wire_input(pipe, ["X"]); run_pipe(pipe)
    assert_3way(sc, clk, pipe, mem_words=[0x1000])
    # The char read (low byte of x1) must be 'X' = 0x58.
    assert sc.proc.read_register(1) & 0xFF == ord("X")
    assert pipe.proc.read_register(1) & 0xFF == ord("X")
    assert pipe.mem.read_byte(0x1000) == ord("X")


def test_console_input_preseeded_different_chars():
    """Different input chars produce different stored values across all
    engines (sanity: the read isn't stuck at a constant)."""
    for ch in ["A", "Z", "1", "\n"]:
        prog = console_read_prog()
        sc = new_simulator(prog);   wire_input(sc, [ch]);   run_sc(sc)
        pipe = new_simulator(prog); wire_input(pipe, [ch]); run_pipe(pipe)
        assert sc.proc.read_register(1) & 0xFF == ord(ch)
        assert pipe.proc.read_register(1) & 0xFF == ord(ch), (
            f"pipe read wrong char for {ch!r}: got {pipe.proc.read_register(1) & 0xFF:#x}"
        )


# ── Scenario B: stall-then-resume ─────────────────────────────────────

def test_console_input_stall_then_resume_pipe():
    """Freeze behind MEM until delayed input arrives, then match the oracle."""
    prog = console_read_prog()
    pipe = new_simulator(prog)
    wire_input(pipe, [])  # start empty — the first read(s) will stall

    # Step the pipeline manually so we can feed input mid-run. Drive until the
    # load reaches MEM and stalls (or the machine halts / we hit a cap).
    stalled_seen = False
    for _ in range(60):
        if pipe.proc.halted and pipe.if_id.bubble and pipe.id_ex.bubble \
                and pipe.ex_mem.bubble and pipe.mem_wb.bubble:
            break
        if pipe.proc.cycles >= pipe.max_cycles:
            break
        pipe.step_pipe()
        if pipe._pipe_mem_stalled:
            stalled_seen = True
            # Feed input now, clear the stall flags (mirrors the GUI's resume).
            pipe._test_input_queue.append("Q")
            pipe.mem._waiting_for_input = False
            pipe._waiting_for_input = False

    assert stalled_seen, "pipeline never entered the MEM-input stall — test didn't exercise §2.1"
    # Drain to completion (input is now available; no more stalls expected).
    run_pipe(pipe)
    assert pipe.proc.read_register(1) & 0xFF == ord("Q"), (
        f"after stall+resume, pipe read wrong char: got {pipe.proc.read_register(1) & 0xFF:#x}"
    )
    # Parity vs the oracle (which read 'Q' synchronously, no stall).
    sc = new_simulator(prog); wire_input(sc, ["Q"]); run_sc(sc)
    assert_3way(sc, sc, pipe, mem_words=[0x1000])  # sc vs pipe (clk passed as sc — 2-way here)


def test_console_input_stall_then_resume_3engine_parity():
    """Same stall-then-resume scenario, but verify the pipeline ends at the
    same state as single-cycle and multi-cycle (which block on the read).
    This is the headline §2.1 closure: the freeze/resume is correct."""
    prog = console_read_prog()
    # Oracle engines: input pre-seeded (they read synchronously).
    sc = new_simulator(prog);  wire_input(sc, ["K"]);   run_sc(sc)
    clk = new_simulator(prog); wire_input(clk, ["K"]);  run_clk(clk)
    # Pipeline: stall then resume with the same char.
    pipe = new_simulator(prog); wire_input(pipe, [])
    fed = False
    for _ in range(80):
        if pipe.proc.halted and pipe.if_id.bubble and pipe.id_ex.bubble \
                and pipe.ex_mem.bubble and pipe.mem_wb.bubble:
            break
        if pipe.proc.cycles >= pipe.max_cycles:
            break
        pipe.step_pipe()
        if pipe._pipe_mem_stalled and not fed:
            pipe._test_input_queue.append("K")
            pipe.mem._waiting_for_input = False
            pipe._waiting_for_input = False
            fed = True
    run_pipe(pipe)
    assert fed, "pipeline never stalled — scenario didn't trigger"
    assert_3way(sc, clk, pipe, mem_words=[0x1000])
    assert pipe.proc.read_register(1) & 0xFF == ord("K")


def test_single_cycle_input_wait_does_not_consume_a_clock():
    sim = new_simulator(console_read_prog())
    wire_input(sim, [])
    sim.step()  # LUI
    cycles_before = sim.proc.cycles
    mcycle_before = sim.csr.read(0xB00)

    assert sim.step() is None
    assert sim._waiting_for_input
    assert sim.proc.cycles == cycles_before
    assert sim.csr.read(0xB00) == mcycle_before


def test_multicycle_input_wait_retries_mem_not_ex():
    sim = new_simulator(console_read_prog())
    wire_input(sim, [])

    for _ in range(20):
        sim.step_clk()
        if sim._waiting_for_input:
            break

    assert sim._waiting_for_input
    assert sim._mc is not None
    assert sim._mc.stages[sim._mc.stage_idx] == "MEM"
