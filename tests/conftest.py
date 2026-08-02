import pytest

from rv32i.cpu import Processor
from rv32i.memory import Memory
from rv32i.decoder import Decoder
from rv32i.csr import CSRFile
from rv32i.simulator import Simulator


@pytest.fixture
def proc():
    return Processor()


@pytest.fixture
def mem():
    return Memory()


@pytest.fixture
def decoder():
    return Decoder()


@pytest.fixture
def csr():
    return CSRFile()


@pytest.fixture
def simulator():
    sim = Simulator(trace=False, max_cycles=10000)
    yield sim


def compile_c_for_simulator(c_file: str) -> Simulator:
    sim = Simulator(trace=False, max_cycles=10000)
    sim.load(c_file)
    return sim


def run_simulator_to_halt(c_file: str, max_cycles: int = 10000) -> Simulator:
    sim = compile_c_for_simulator(c_file)
    sim.run(max_cycles=max_cycles)
    return sim
