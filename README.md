# RISC-V RV32IMC Simulator

An educational RISC-V instruction-set simulator with three execution engines,
a desktop web interface, and a headless CLI. The simulator executes RV32I,
the M and C extensions, and machine-mode Zicsr instructions while exposing
registers, CSRs, memory, caches, traps, and timing state.

The Single-Cycle, Multi-Cycle, and five-stage Pipeline engines share one
instruction-semantics layer and are tested to produce the same architectural
state. Their timing, stalls, flushes, and in-flight state are intentionally
different.

> **Desktop UI:** the web interface is designed for a desktop browser. Use a
> viewport at least 1280 px wide; 1440 px or wider is recommended. Mobile and
> touch-first layouts are not supported at this stage.

## What is included

- RV32I base integer instructions, M multiplication/division, RV32C compressed
  instructions, and machine-mode Zicsr operations.
- Single-Cycle correctness-oracle execution.
- Variable-CPI Multi-Cycle execution.
- Cycle-stepped five-stage Pipeline execution with forwarding, RAW hazards,
  load-use stalls, static branch prediction, control flushes, and precise
  interrupt entry.
- Configurable split instruction/data caches with direct-mapped through
  16-way layouts, FIFO or LRU replacement, and timing-mode miss penalties.
- Sparse 32-bit memory, timer/console/interrupt MMIO, traps, and machine CSRs.
- C and assembly builds through the GNU RISC-V bare-metal toolchain.
- A NiceGUI desktop workspace with source and linker editors, disassembly,
  register/CSR/memory/cache views, pipeline timing, breakpoints, and terminal
  I/O.
- A headless CLI and a small Python API.
- Unit, integration, architectural-parity, browser, and optional Spike golden
  tests.

## Requirements

- Python 3.12 or newer.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) for the
  reproducible Python environment.
- GNU RISC-V bare-metal tools using the `riscv64-unknown-elf-` prefix, even
  though generated programs target RV32.
- A current desktop Firefox or Chromium-family browser for the web UI.
- Optional: Spike for the golden-reference tests.

The required external executables are:

```text
riscv64-unknown-elf-gcc
riscv64-unknown-elf-objcopy
riscv64-unknown-elf-objdump
riscv64-unknown-elf-readelf
riscv64-unknown-elf-nm
```

The project first checks `~/opt/riscv/bin/`, then checks `PATH`.

On Ubuntu or Debian, the compiler and binutils can usually be installed with:

```bash
sudo apt update
sudo apt install gcc-riscv64-unknown-elf binutils-riscv64-unknown-elf
```

On Windows, WSL2 with an Ubuntu environment is the recommended route. On
other systems, install a bare-metal RISC-V GNU toolchain and ensure the
executables above are on `PATH`.

Confirm the compiler is visible before launching the simulator:

```bash
riscv64-unknown-elf-gcc --version
```

## Quick start

```bash
git clone https://github.com/AtomChidjai/RISC-V-SIM.git
cd RISC-V-SIM
uv sync
uv run rv32i-gui
```

Open <http://127.0.0.1:8080>. The server listens only on the local machine by
default.

Running directly from a source checkout is also supported:

```bash
uv run gui/app.py
```

### First GUI run

1. Choose a program from **Example**, or paste freestanding C/assembly into
   the source editor.
2. Select the compiler ISA and linker mode.
3. Press **Compile**.
4. Choose **Single-Cycle**, **Multi-Cycle**, or **Pipeline**.
5. Use **Step** for one instruction/clock or **Run** for timed execution.
6. Inspect the disassembly, registers, CSRs, memory, cache, decode state, and
   timing panels. Open **Terminal** for MMIO output/input and **Trap Log** for
   exceptions and interrupts.

The example selector includes instruction, terminal, algorithm, cache,
pipeline, compressed-instruction, and timer-interrupt programs. Examples are
packaged with the application, so they also work when the project is installed
from a wheel.

### Execution controls

| Action | Linux / Windows | macOS |
|---|---|---|
| Step | `Ctrl+Enter` | `Cmd+Enter` |
| Run / Stop | `Ctrl+Shift+Enter` | `Cmd+Shift+Enter` |
| Reset | `Ctrl+Alt+R` | `Cmd+Alt+R` |

Shortcuts do not fire while an editor, terminal, input, or select control has
focus.

### Mode behavior

- **Single-Cycle:** one Step is one complete instruction and one modeled
  clock. It is the architectural correctness oracle. Cache misses do not add
  clocks.
- **Multi-Cycle:** one Step is one stage clock. Instructions take different
  numbers of clocks; configured cache misses add timing penalties.
- **Pipeline:** one Step advances the whole five-stage pipeline by one clock.
  Forwarding, branch prediction, hazards, flushes, cache stalls, and pipeline
  drain state are visible in the timing workspace.

Changing modes stops Run. If work is in flight, the simulator resets the
loaded program before transferring control to the new engine.

### Source and linker modes

The source editor accepts freestanding `.c`, `.s`, and `.S` programs. Programs
must provide `_start`; there is no C runtime or standard library.

The default build places text at `0x00010000` without the project linker
script. Select **With linker** when a program needs the bundled section layout
or symbols such as `__stack_top`, `__data_start`, or `__bss_start`.

The GUI offers RV32I, RV32IM, RV32IC, and RV32IMC compiler profiles, all with
Zicsr enabled. These profiles constrain compiler output; the simulator core
continues to implement its full RV32IMC + Zicsr surface.

### Cache, terminal, traps, and breakpoints

- Cache geometry, associativity, block size, replacement policy, and I/D miss
  penalties are available in the Memory System panel.
- Cache penalties affect Multi-Cycle and Pipeline timing only. MMIO bypasses
  cache line-miss penalties.
- Terminal input is delivered through console-in MMIO. An empty read pauses or
  freezes the active engine until input arrives.
- The Trap Log shows exception/interrupt cause, PC, trap value, and target.
- Click a disassembly instruction to toggle a GUI-owned breakpoint.

## Headless CLI

Run a C or assembly program with the Single-Cycle engine:

```bash
uv run rv32i programs/examples/hello_terminal.c --trace --register
```

```text
usage: rv32i [-h] [--trace] [--max-cycles N] [--register] [--memory]
             [--verbose-decode] [--verbose-register]
             source
```

Useful examples:

```bash
# Print the final registers
uv run rv32i programs/isa/demo_all_types.c --register --max-cycles 500

# Print the execution trace and a memory dump
uv run rv32i programs/examples/bubble_sort.c --trace --memory
```

The command exits with status 0 when the processor halts and status 1 when it
stops at the cycle budget first. Console-out MMIO streams to stdout. Terminal
input replay and GUI breakpoints are GUI-only features.

## Python API

The package root intentionally exports only `Simulator`:

```python
from rv32i import Simulator

sim = Simulator(trace=False, max_cycles=500)
sim.load("programs/examples/bubble_sort.c")
sim.run(delay=0)

print(sim.state())
print(sim.cache_stats())
```

For custom frontends, call exactly one engine at a time:

```python
sim.step()       # one Single-Cycle instruction
sim.step_clk()   # one Multi-Cycle clock
sim.step_pipe()  # one Pipeline clock
```

`Simulator` is the stable package entry point. Submodules remain available for
advanced use but are not treated as a compatibility-stable public API.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `RV32I_GUI_HOST` | `127.0.0.1` | NiceGUI bind address |
| `RV32I_GUI_PORT` | `8080` | NiceGUI port |
| `RV32I_DEBUG` | unset | Set to `1` for core instruction diagnostics |

For example:

```bash
RV32I_GUI_PORT=9090 uv run rv32i-gui
```

Binding to `0.0.0.0` exposes the development UI to your network. The app has
no authentication layer, and compiling source executes the local RISC-V
toolchain, so do that only on a trusted network and machine.

## Development and verification

Install every development extra:

```bash
uv sync --extra test --extra browser-test --extra lint
```

Run the complete headless suite:

```bash
uv run pytest -q
```

Run the real-browser smoke separately:

```bash
RUN_BROWSER_TESTS=1 uv run pytest -q tests/test_gui_browser.py
```

Run lint and build the distributable package:

```bash
uv run ruff check .
uv build
```

Golden tests compare final register state against Spike. They run when both
`spike` and the RISC-V compiler are available and skip otherwise. The ordinary
suite and the hand-assembled three-engine parity tests do not require Spike.

### Install the built commands

After `uv build`, install the wheel as a local tool:

```bash
uv tool install dist/rv32i_simulator-0.1.0-py3-none-any.whl
rv32i --help
rv32i-gui
```

Use `uv tool uninstall rv32i-simulator` to remove it.

## Project structure

```text
rv32i/      simulator core, execution engines, caches, devices, loaders
gui/        NiceGUI application, desktop theme, renderers, browser assets
programs/   freestanding C examples and architectural test programs
tests/      unit, parity, toolchain, renderer, and browser tests
```

`rv32i.Simulator` is the only execution orchestrator shared by the CLI and GUI.
The `compute_*` helpers describe instruction effects without mutating
architectural state; each engine controls when those effects commit.

## Scope and limitations

This is an educational instruction-set and timing simulator, not RTL, a Linux
system emulator, or a complete implementation of the RISC-V privileged
specification. Timing is modeled for teaching and engine comparison; it does
not predict a specific physical processor. The web UI is desktop-only.

## License and third-party notices

Project code is released under the [MIT License](LICENSE).

The vendored WaveDrom browser bundle retains its own notice in
[`gui/assets/vendor/WAVEDROM_LICENSE`](gui/assets/vendor/WAVEDROM_LICENSE).
RISC-V names and marks belong to RISC-V International. This independent
educational project is not endorsed by or affiliated with RISC-V
International.
