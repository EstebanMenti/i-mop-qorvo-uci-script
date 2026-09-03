"""Tests de cli_bridge/client.py y del regex de prompt de ble_transport.py.

No requieren hardware ni una conexion BLE real: `CliBridgeClient` recibe un
transporte falso que cumple la misma interfaz minima que `BleShellTransport`
(`connect`/`disconnect`/`send_line`), analogo a `FakeTransport` para UCI.
"""

import pytest

from dwm3001c_uci.cli_bridge.ble_transport import _PROMPT_RE
from dwm3001c_uci.cli_bridge.client import CliBridgeClient, _build_fira_command
from dwm3001c_uci.cli_bridge.errors import CliBridgeError


class FakeShellTransport:
    """Cumple la interfaz minima que usa `CliBridgeClient`."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.sent_lines: list[str] = []
        self._responses = responses or {}
        self.connected_to: str | None = None
        self.disconnected = False

    def connect(self, name_or_address: str) -> str:
        self.connected_to = name_or_address
        return "AA:BB:CC:DD:EE:FF"

    def disconnect(self) -> None:
        self.disconnected = True

    def send_line(self, text: str, timeout_s: float = 9.0) -> str:
        self.sent_lines.append(text)
        return self._responses.get(text, "ok")


def test_build_fira_command_formats_options_as_dash_key_equals_value() -> None:
    command = _build_fira_command("RESPF", {"CHAN": 9, "PCODE": 10, "RRU": "DSTWR"})
    assert command == "RESPF -CHAN=9 -PCODE=10 -RRU=DSTWR"


def test_build_fira_command_with_no_options() -> None:
    assert _build_fira_command("INITF", {}) == "INITF"


def test_connect_delegates_to_transport() -> None:
    transport = FakeShellTransport()
    client = CliBridgeClient(transport)

    address = client.connect("UWB-Node-2")

    assert transport.connected_to == "UWB-Node-2"
    assert address == "AA:BB:CC:DD:EE:FF"


def test_power_on_sends_expected_command_without_duration(monkeypatch) -> None:
    transport = FakeShellTransport()
    client = CliBridgeClient(transport)
    monkeypatch.setattr("dwm3001c_uci.cli_bridge.client.time.sleep", lambda _s: None)

    client.power_on()

    assert transport.sent_lines == ["qorvo on"]


def test_power_on_sends_expected_command_with_duration(monkeypatch) -> None:
    transport = FakeShellTransport()
    client = CliBridgeClient(transport)
    monkeypatch.setattr("dwm3001c_uci.cli_bridge.client.time.sleep", lambda _s: None)

    client.power_on(duration="10m")

    assert transport.sent_lines == ["qorvo on -t 10m"]


def test_power_off_sends_expected_command() -> None:
    transport = FakeShellTransport()
    client = CliBridgeClient(transport)

    client.power_off()

    assert transport.sent_lines == ["qorvo off"]


def test_send_qorvo_command_prefixes_with_qorvo() -> None:
    transport = FakeShellTransport(responses={"qorvo STAT": "JS0109{...}\nok"})
    client = CliBridgeClient(transport)

    response = client.send_qorvo_command("STAT")

    assert transport.sent_lines == ["qorvo STAT"]
    assert response == "JS0109{...}\nok"


def test_send_qorvo_command_raises_on_bridge_error_response() -> None:
    transport = FakeShellTransport(
        responses={"qorvo STAT": "Error: sin respuesta del modulo Qorvo (timeout)"}
    )
    client = CliBridgeClient(transport)

    with pytest.raises(CliBridgeError, match="timeout"):
        client.send_qorvo_command("STAT")


def test_stat_stop_respf_initf_convenience_methods() -> None:
    transport = FakeShellTransport()
    client = CliBridgeClient(transport)

    client.stat()
    client.stop()
    client.respf(CHAN=9, PCODE=10, RRU="DSTWR", ADDR=1, PADDR=0)
    client.initf(CHAN=9, ADDR=0, PADDR=1)

    assert transport.sent_lines == [
        "qorvo STAT",
        "qorvo STOP",
        "qorvo RESPF -CHAN=9 -PCODE=10 -RRU=DSTWR -ADDR=1 -PADDR=0",
        "qorvo INITF -CHAN=9 -ADDR=0 -PADDR=1",
    ]


def test_disconnect_delegates_to_transport() -> None:
    transport = FakeShellTransport()
    client = CliBridgeClient(transport)

    client.disconnect()

    assert transport.disconnected is True


@pytest.mark.parametrize(
    "text",
    [
        "bt_nus:~$ ",
        "bt_nus:~$",
        "Available commands:\n  qorvo : ...\nbt_nus:~$ ",
    ],
)
def test_prompt_regex_matches_known_prompt_forms(text: str) -> None:
    assert _PROMPT_RE.search(text) is not None


def test_prompt_regex_does_not_match_ordinary_output() -> None:
    assert _PROMPT_RE.search("Qorvo status changed to: ON") is None
