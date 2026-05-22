from openflow.instruments.base import Instrument


class FakeInstrument(Instrument):
    def __init__(self, resource: str) -> None:
        super().__init__(resource)
        self.opened = False
        self.closed = False
        self.last_write: str | None = None
        self.next_query_response = "model XYZ"

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def write(self, scpi: str) -> None:
        self.last_write = scpi

    def query(self, scpi: str) -> str:
        self.last_write = scpi
        return self.next_query_response


def test_instrument_stores_resource():
    inst = FakeInstrument("TCPIP::x::INSTR")
    assert inst.resource == "TCPIP::x::INSTR"


def test_instrument_context_manager_opens_and_closes():
    inst = FakeInstrument("res")
    with inst as opened:
        assert opened.opened is True
        assert opened.closed is False
    assert inst.closed is True


def test_instrument_identify_returns_idn_string():
    inst = FakeInstrument("res")
    inst.next_query_response = "Rohde&Schwarz,CMW100,1234,3.7.30"
    assert inst.identify() == "Rohde&Schwarz,CMW100,1234,3.7.30"
    assert inst.last_write == "*IDN?"
