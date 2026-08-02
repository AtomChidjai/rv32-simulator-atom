"""Headless single-cycle frontend for C and assembly programs."""

import argparse
import sys

from .elf_loader import print_section_map
from .simulator import Simulator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile and run a C or assembly program in the RV32I simulator",
    )
    parser.add_argument("source", help="C or assembly source file to compile and run")
    parser.add_argument("--trace", action="store_true", help="Print the execution trace")
    parser.add_argument("--max-cycles", type=int, default=100, help="Maximum execution clocks")
    parser.add_argument("--register", action="store_true", help="Dump registers after execution")
    parser.add_argument("--memory", action="store_true", help="Dump memory after execution")
    parser.add_argument(
        "--verbose-decode",
        "--verbose_decode",
        dest="verbose_decode",
        action="store_true",
        help="Print decoder details",
    )
    parser.add_argument(
        "--verbose-register",
        "--verbose_register",
        dest="verbose_register",
        action="store_true",
        help="Print registers after each step",
    )
    args = parser.parse_args(argv)

    sim = Simulator(
        verbose_decoder=args.verbose_decode,
        trace=args.trace,
        max_cycles=args.max_cycles,
        verbose_register=args.verbose_register,
    )

    def write_console(ch: str) -> None:
        print(ch, end="", flush=True)

    sim.on_console_write = write_console
    info = sim.load(args.source)
    print_section_map(info, file=sys.stderr)
    sim.run()

    if args.register:
        print(sim.state(), file=sys.stderr)
    if args.memory:
        print(sim.mem_dump(), file=sys.stderr)
    return 0 if sim.proc.halted else 1


if __name__ == "__main__":
    raise SystemExit(main())
