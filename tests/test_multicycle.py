"""Multi-cycle timing and single-cycle state-parity tests."""

import pytest

from rv32i import Simulator
from rv32i.devices import register_default_devices


# ---- a tiny hand-assembled program covering all in-scope types -------------
#   0x00 addi x1, x0, 5      (ALU, 4 clocks)
#   0x04 addi x2, x0, 7      (ALU, 4)
#   0x08 add  x3, x1, x2     (ALU, 4)
#   0x0c sw   x3, 0(x10)     (store, 4 clocks: IF ID EX MEM)
#   0x10 lw   x4, 0(x10)     (load, 5 clocks: IF ID EX MEM WB)
#   0x14 beq  x1, x1, +8     (branch taken, 3 clocks) -> skips 0x18
#   0x18 addi x5, x0, 99     (skipped)
#   0x1c ebreak              (halt, 3 clocks)
def program_bytes() -> bytes:
    addi_x1_5 = 0x00500093
    addi_x2_7 = 0x00700113
    add_x3 = (0 << 25) | (2 << 20) | (1 << 15) | (0 << 12) | (3 << 7) | 0x33
    sw_x3_x10 = (0 << 25) | (3 << 20) | (10 << 15) | (2 << 12) | (0 << 7) | 0x23
    lw_x4_x10 = (0 << 20) | (10 << 15) | (2 << 12) | (4 << 7) | 0x03
    # beq x1,x1,+8 : B-type imm=8 → imm[12|10:5|4:1|11] = 0|000000|0100|0
    beq = (0 << 31) | (0b000000 << 25) | (1 << 20) | (1 << 15) | (0b000 << 12) | (0b0100 << 8) | (0 << 7) | 0b1100011
    addi_x5_99 = 0x06300293
    ebreak = 0x00100073
    words = [addi_x1_5, addi_x2_7, add_x3, sw_x3_x10, lw_x4_x10, beq, addi_x5_99, ebreak]
    return b"".join(w.to_bytes(4, "little") for w in words)


def fresh_sim(max_cycles: int = 200) -> Simulator:
    sim = Simulator(max_cycles=max_cycles)
    sim.mem.load_bytes(0, program_bytes())
    sim.timer = register_default_devices(sim.mem, sim.csr)
    sim.proc.reset(pc=0)
    sim.proc.write_register(10, 0x100)  # data base for sw/lw
    return sim


# ----- helpers -------------------------------------------------------------

def run_to_halt_step_clk(sim: Simulator):
    """Drive step_clk() until halted or max_cycles; return retire snapshots."""
    snaps = []
    while not sim.proc.halted and sim.proc.cycles < sim.max_cycles:
        snap = sim.step_clk()
        if snap is not None:
            snaps.append(snap)
    return snaps


def run_to_halt_step(sim: Simulator):
    while not sim.proc.halted and sim.proc.cycles < sim.max_cycles:
        if sim.step() is None:
            break


# ----- per-type clock accounting ------------------------------------------

@pytest.mark.parametrize(
    "name,find_opcode,expected_clocks",
    [
        ("addi",  lambda d: d["inst_name"] == "addi" and d["rd"] == 1, 4),
        ("add",   lambda d: d["inst_name"] == "add",                    4),
        ("sw",    lambda d: d["inst_name"] == "sw",                     4),
        ("lw",    lambda d: d["inst_name"] == "lw",                     5),
        ("beq",   lambda d: d["inst_name"] == "beq",                    3),
        ("ebreak",lambda d: d["inst_name"] == "ebreak",                 3),
    ],
)
def test_step_clk_per_type_clock_count(name, find_opcode, expected_clocks):
    """Each in-scope instruction type retires in exactly its stage-list length."""
    sim = fresh_sim()
    snaps = run_to_halt_step_clk(sim)
    match = next(s for s in snaps if find_opcode(s["decoded"]))
    assert len(match["stages"]) == expected_clocks, (
        f"{name}: expected {expected_clocks} clocks, got stages {match['stages']}"
    )


def test_step_clk_alu_stage_sequence():
    """An addi walks exactly IF -> ID -> EX -> WB (observable in the snapshot)."""
    sim = fresh_sim()
    snaps = run_to_halt_step_clk(sim)
    addi = next(s for s in snaps if s["decoded"]["inst_name"] == "addi")
    assert addi["stages"] == ["IF", "ID", "EX", "WB"]


def test_step_clk_load_stage_sequence():
    """A lw walks exactly IF -> ID -> EX -> MEM -> WB (5 stages, MEM does dcache)."""
    sim = fresh_sim()
    snaps = run_to_halt_step_clk(sim)
    lw = next(s for s in snaps if s["decoded"]["inst_name"] == "lw")
    assert lw["stages"] == ["IF", "ID", "EX", "MEM", "WB"]


def test_step_clk_branch_stage_sequence():
    """A branch walks exactly IF -> ID -> EX (3 stages, no MEM/WB)."""
    sim = fresh_sim()
    snaps = run_to_halt_step_clk(sim)
    beq = next(s for s in snaps if s["decoded"]["inst_name"] == "beq")
    assert beq["stages"] == ["IF", "ID", "EX"]


# ----- per-stage commit location ------------------------------------------

def test_step_clk_store_commits_at_mem_not_wb():
    """A store hits the dcache at its MEM tick (its last stage), not WB."""
    sim = fresh_sim()
    before = sim.dcache.total_accesses
    run_to_halt_step_clk(sim)
    after = sim.dcache.total_accesses
    # The store is the ONLY dcache access in this program (lw also reads dcache,
    # so total dcache accesses should be 2: one sw write + one lw read).
    assert after - before == 2, f"expected 2 dcache accesses (sw + lw), got {after - before}"


def test_step_clk_alu_never_touches_dcache():
    """An ALU-only program never accesses the dcache (no MEM stage for ALU)."""
    sim = Simulator(max_cycles=100)
    # addi x1,x0,5 ; addi x2,x0,7 ; add x3,x1,x2 ; ebreak
    prog = [
        0x00500093,
        0x00700113,
        (0 << 25) | (2 << 20) | (1 << 15) | (0 << 12) | (3 << 7) | 0x33,
        0x00100073,
    ]
    sim.mem.load_bytes(0, b"".join(w.to_bytes(4, "little") for w in prog))
    sim.timer = register_default_devices(sim.mem, sim.csr)
    sim.proc.reset(pc=0)
    before = sim.dcache.total_accesses
    run_to_halt_step_clk(sim)
    assert sim.dcache.total_accesses == before, "ALU ops must not touch dcache"


# Architectural state parity

def test_step_clk_matches_step_oracle_state():
    """For the same program, step_clk() and step() reach identical state."""
    # Multi-cycle run
    mc = fresh_sim()
    run_to_halt_step_clk(mc)

    # Single-cycle run
    sc = fresh_sim()
    run_to_halt_step(sc)

    assert mc.proc.registers == sc.proc.registers, "register file mismatch"
    assert mc.proc.read_pc() == sc.proc.read_pc(), "PC mismatch"
    assert mc.mem.read_word(0x100) == sc.mem.read_word(0x100), "memory mismatch"


def test_step_clk_cpi_above_single_cycle():
    """Multi-cycle CPI must be > 1 (the whole point: it pays all stages)."""
    sim = fresh_sim()
    run_to_halt_step_clk(sim)
    mcycle = sim.csr.read(0xB00)
    minstret = sim.csr.read(0xB02)
    cpi = mcycle / max(1, minstret)
    assert cpi > 1.0, f"multi-cycle CPI should be > 1, got {cpi}"
    # And in a sane range for this instruction mix.
    assert 3.0 <= cpi <= 5.0, f"multi-cycle CPI should land ~3.5-4.5, got {cpi}"


def test_step_clk_mcycle_is_sum_of_stage_counts():
    """mcycle after a clean run equals the sum of each instruction's stage count."""
    sim = fresh_sim()
    snaps = run_to_halt_step_clk(sim)
    # The ebreak's halting clock is counted in mcycle even though ebreak itself
    # isn't counted in minstret (matches step()'s accounting for halting instrs).
    expected = sum(len(s["stages"]) for s in snaps)
    assert sim.csr.read(0xB00) == expected, (
        f"mcycle={sim.csr.read(0xB00)} but sum of stage counts={expected}"
    )


# Cache-miss penalties

def alu_program() -> bytes:
    """addi x1,5 ; addi x2,7 ; ebreak  (two ALU instrs in the same cache block)."""
    words = [0x00500093, 0x00700113, 0x00100073]
    return b"".join(w.to_bytes(4, "little") for w in words)


def lw_program() -> bytes:
    """addi x10,0x200 ; lw x5,0(x10) ; ebreak  (lw hits a cold dcache at 0x200)."""
    addi_x10_200 = (0x200 << 20) | (0 << 15) | (0 << 12) | (10 << 7) | 0x13
    lw_x5_x10 = (0 << 20) | (10 << 15) | (2 << 12) | (5 << 7) | 0x03
    ebreak = 0x00100073
    return b"".join(w.to_bytes(4, "little") for w in [addi_x10_200, lw_x5_x10, ebreak])


def sw_program() -> bytes:
    """addi x10,0x300 ; addi x5,42 ; sw x5,0(x10) ; ebreak (cold store miss)."""
    addi_x10_300 = (0x300 << 20) | (0 << 15) | (0 << 12) | (10 << 7) | 0x13
    addi_x5_42 = (42 << 20) | (0 << 15) | (0 << 12) | (5 << 7) | 0x13
    sw_x5_x10 = (0 << 25) | (5 << 20) | (10 << 15) | (2 << 12) | (0 << 7) | 0x23
    ebreak = 0x00100073
    return b"".join(w.to_bytes(4, "little") for w in [addi_x10_300, addi_x5_42, sw_x5_x10, ebreak])


def mmio_lw_program() -> bytes:
    """lui x10,0x10000 ; lw x5,16(x10) ; ebreak  (load mtime at 0x10000010 = device)."""
    lui_x10 = (0x10000 << 12) | (10 << 7) | 0x37
    lw_x5_x10 = (16 << 20) | (10 << 15) | (2 << 12) | (5 << 7) | 0x03
    ebreak = 0x00100073
    return b"".join(w.to_bytes(4, "little") for w in [lui_x10, lw_x5_x10, ebreak])


def fresh_stall_sim(prog: bytes, ic: int = 0, dc: int = 0, max_cycles: int = 500) -> Simulator:
    """Fresh sim with cache-miss stall config + a hand-assembled program loaded."""
    sim = Simulator(max_cycles=max_cycles, icache_miss_stall=ic, dcache_miss_stall=dc)
    sim.mem.load_bytes(0, prog)
    sim.timer = register_default_devices(sim.mem, sim.csr)
    sim.proc.reset(pc=0)
    return sim


def step_n(sim: Simulator, n: int):
    """Drive step_clk() exactly n times (ignoring snapshots)."""
    for _ in range(n):
        if sim.proc.halted:
            break
        sim.step_clk()


# ----- config -------------------------------------------------------------

def test_stall_config_defaults_to_zero():
    """With no kwargs, both stall penalties default to 0 (no penalty)."""
    sim = Simulator(max_cycles=10)
    assert sim.icache_miss_stall == 0
    assert sim.dcache_miss_stall == 0


def test_stall_config_via_constructor():
    """Constructor kwargs are stored (negatives clamped to 0)."""
    sim = Simulator(max_cycles=10, icache_miss_stall=5, dcache_miss_stall=7)
    assert sim.icache_miss_stall == 5
    assert sim.dcache_miss_stall == 7
    neg = Simulator(max_cycles=10, icache_miss_stall=-3, dcache_miss_stall=-1)
    assert neg.icache_miss_stall == 0
    assert neg.dcache_miss_stall == 0


def test_stall_config_via_setter():
    """configure_cache_stalls updates both knobs live (non-destructive)."""
    sim = Simulator(max_cycles=10)
    sim.configure_cache_stalls(3, 9)
    assert sim.icache_miss_stall == 3
    assert sim.dcache_miss_stall == 9
    # Non-destructive: caches/history untouched.
    assert sim.icache.total_accesses == 0
    assert sim.history == []
    # Clamping.
    sim.configure_cache_stalls(-1, -2)
    assert sim.icache_miss_stall == 0
    assert sim.dcache_miss_stall == 0


# ----- I-cache miss stall (IF stage) --------------------------------------

def test_icache_miss_burns_one_plus_n_and_lands_in_id():
    """A cold I-cache miss at IF costs exactly 1+N clocks and lands in ID."""
    sim = fresh_stall_sim(alu_program(), ic=2)
    assert sim.proc.cycles == 0
    sim.step_clk()  # IF for instr 0 (PC=0) — cold miss
    # 1 (the per-clock +1) + 2 (stall) = 3 total.
    assert sim.proc.cycles == 1 + 2
    assert sim._mc is not None
    assert sim._mc.stage_idx == 1            # advanced to ID
    assert sim._mc.stages[1] == "ID"
    assert sim._mc.stall_info == ("IF", 2)   # visualization hook


def test_icache_zero_stall_costs_one_cycle():
    """With icache_miss_stall=0, even a cold miss costs only 1 cycle."""
    sim = fresh_stall_sim(alu_program(), ic=0)
    sim.step_clk()  # IF — cold miss but no penalty configured
    assert sim.proc.cycles == 1
    assert sim._mc.stall_info is None


def test_icache_hit_costs_one_cycle():
    """After the first fetch fills the block, the next fetch (same block) hits → +1."""
    sim = fresh_stall_sim(alu_program(), ic=5)
    # Run instr 0 (addi) to retirement: IF(miss) ID EX WB = 4 step_clk calls.
    step_n(sim, 4)
    assert sim._mc is None  # retired
    cycles_before = sim.proc.cycles
    # Next fetch is PC=4 — same 64B block as PC=0 → I-cache HIT.
    sim.step_clk()
    assert sim.proc.cycles - cycles_before == 1, "I-cache hit must cost exactly 1 cycle"
    assert sim._mc.stall_info is None


# ----- D-cache miss stall (MEM stage) -------------------------------------

def test_dcache_miss_on_load_burns_one_plus_n_and_lands_in_wb():
    """A cold D-cache miss on lw at MEM costs exactly 1+N clocks and lands in WB."""
    sim = fresh_stall_sim(lw_program(), dc=4)
    # addi x10,0x200 retires in 4 clocks (IF ID EX WB). Then lw walks IF ID EX
    # (3 more clocks) → lw is now at stage_idx=3 (MEM about to run). Total 7.
    step_n(sim, 7)
    assert sim._mc.stages[sim._mc.stage_idx] == "MEM"
    assert sim._mc.decoded["inst_name"] == "lw"
    cycles_before = sim.proc.cycles
    sim.step_clk()  # MEM: cold dcache miss at 0x200
    assert sim.proc.cycles - cycles_before == 1 + 4
    assert sim._mc.stage_idx == 4            # advanced to WB
    assert sim._mc.stages[4] == "WB"
    assert sim._mc.stall_info == ("MEM", 4)


def test_dcache_miss_on_store_burns_one_plus_n():
    """A cold D-cache miss on sw at MEM also burns 1+N (stores stall too)."""
    sim = fresh_stall_sim(sw_program(), dc=4)
    # addi x10,0x300 (4 clk) + addi x5,42 (4 clk) retire. Then sw walks IF ID EX
    # (3 clk) → sw at MEM. Total = 4+4+3 = 11.
    step_n(sim, 11)
    assert sim._mc.stages[sim._mc.stage_idx] == "MEM"
    assert sim._mc.decoded["inst_name"] == "sw"
    cycles_before = sim.proc.cycles
    sim.step_clk()  # MEM: cold store miss at 0x300 (sw retires here too)
    assert sim.proc.cycles - cycles_before == 1 + 4


def test_dcache_zero_stall_costs_one_cycle():
    """With dcache_miss_stall=0, even a cold miss at MEM costs only 1 cycle."""
    sim = fresh_stall_sim(lw_program(), dc=0)
    step_n(sim, 7)
    cycles_before = sim.proc.cycles
    sim.step_clk()  # MEM: cold miss but no penalty
    assert sim.proc.cycles - cycles_before == 1
    assert sim._mc.stall_info is None


# ----- device/MMIO bypass does NOT stall ----------------------------------

def test_dcache_device_access_does_not_stall():
    """A load from MMIO (way == -1) is a device bypass, not a miss → no stall."""
    sim = fresh_stall_sim(mmio_lw_program(), dc=10)
    # lui x10 (4 clk) retires. lw walks IF ID EX (3 clk) → MEM. Total = 7.
    step_n(sim, 7)
    assert sim._mc.decoded["inst_name"] == "lw"
    cycles_before = sim.proc.cycles
    sim.step_clk()  # MEM: device read at 0x10000010 → way == -1, no stall
    assert sim.proc.cycles - cycles_before == 1, "device bypass must not stall"
    assert sim._mc.stall_info is None


# ----- architectural correctness is preserved -----------------------------

def test_stall_does_not_change_architectural_state():
    """Stalls add clocks but the final register/memory state is unchanged."""
    sim = fresh_stall_sim(lw_program(), ic=3, dc=6)
    run_to_halt_step_clk(sim)
    ref = fresh_stall_sim(lw_program(), ic=0, dc=0)
    run_to_halt_step_clk(ref)
    assert sim.proc.registers == ref.proc.registers, "stalls must not alter registers"
    assert sim.mem.read_word(0x200) == ref.mem.read_word(0x200)
    # But the stalled run used strictly more cycles.
    assert sim.proc.cycles > ref.proc.cycles


def test_stall_mcycle_increments_in_lockstep():
    """A miss stall advances mcycle and mtime alongside proc.cycles (1+N total)."""
    sim = fresh_stall_sim(alu_program(), ic=2)
    sim.step_clk()  # IF cold miss
    # All three counters moved by 1+N = 3.
    assert sim.proc.cycles == 3
    assert sim.csr.read(0xB00) == 3       # mcycle
    assert sim.timer.mtime == 3           # mtime


# ----- stall_info survives retirement (GUI regression) --------------------

def test_stall_info_in_snapshot_when_retiring_on_stall_step():
    """Regression: when an instruction retires ON its stall step (e.g. a store
    at MEM), _mc is cleared but the returned snapshot must still carry
    stall_info. The GUI relies on this to render the STALL(N) badge after
    retirement."""
    sim = fresh_stall_sim(sw_program(), dc=4)
    # Run to the store's MEM step: addi x10(4) + addi x5(4) + sw IF ID EX(3) = 11.
    step_n(sim, 11)
    assert sim._mc.stages[sim._mc.stage_idx] == "MEM"
    snap = sim.step_clk()  # MEM: cold miss → retires THIS step
    # Retired → _mc cleared, but the snapshot must carry the stall marker.
    assert snap is not None
    assert snap["stall_info"] == ("MEM", 4)
    assert sim.history[-1]["stall_info"] == ("MEM", 4)
