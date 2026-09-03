"""Tests de la capa de transporte (FakeTransport y descubrimiento de puertos)."""

from serial.tools.list_ports_common import ListPortInfo

from dwm3001c_uci.transport.discovery import (
    KNOWN_CANDIDATE_VID_PID,
    list_all_ports,
    list_known_candidates,
)
from tests.fakes import FakeTransport


def test_fake_transport_read_returns_queued_bytes() -> None:
    transport = FakeTransport(rx_data=b"\x01\x02\x03")
    assert transport.read(2) == b"\x01\x02"
    assert transport.read(2) == b"\x03"
    assert transport.read(2) == b""


def test_fake_transport_queue_rx_appends_more_data() -> None:
    transport = FakeTransport()
    transport.queue_rx(b"\xaa")
    transport.queue_rx(b"\xbb")
    assert transport.read(2) == b"\xaa\xbb"


def test_fake_transport_write_is_logged() -> None:
    transport = FakeTransport()
    written = transport.write(b"\x20\x02\x00\x00")
    assert written == 4
    assert transport.tx_log == [b"\x20\x02\x00\x00"]


def _make_port_info(device: str, vid: int | None, pid: int | None) -> ListPortInfo:
    info = ListPortInfo(device)
    info.vid = vid
    info.pid = pid
    return info


def test_list_all_ports_maps_pyserial_info(monkeypatch) -> None:
    fake_ports = [_make_port_info("COM29", 0x1915, 0x520F), _make_port_info("COM3", 0x0403, 0x6001)]
    monkeypatch.setattr("dwm3001c_uci.transport.discovery.list_ports.comports", lambda: fake_ports)

    candidates = list_all_ports()

    assert [c.device for c in candidates] == ["COM29", "COM3"]


def test_list_known_candidates_filters_by_vid_pid(monkeypatch) -> None:
    known_vid, known_pid = next(iter(KNOWN_CANDIDATE_VID_PID))
    fake_ports = [
        _make_port_info("COM29", known_vid, known_pid),
        _make_port_info("COM3", 0x0403, 0x6001),
    ]
    monkeypatch.setattr("dwm3001c_uci.transport.discovery.list_ports.comports", lambda: fake_ports)

    candidates = list_known_candidates()

    assert [c.device for c in candidates] == ["COM29"]
