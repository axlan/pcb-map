#!/usr/bin/env -S uv run
"""Device setup script for PCB map"""

from pathlib import Path
import sys
import time
import socket

import typer

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

import pywifi

sys.path.insert(0, str(Path(__file__).parents[1]))

from pcb_map.mqtt_client import MQTTClient
from pcb_map.constants import (
    AP_SSID,
    DEFAULT_BROKER,
    BASE_NAME,
    MDNS_HOSTNAME,
    MDNS_SERVICE_TYPE,
    MQTT_PING_TOPIC,
    MQTT_PONG_TOPIC,
    UDP_MQTT_CONFIG_PORT,
    HostnameOption,
    PortOption,
    UseTlsOption,
    UsernameOption,
    PasswordOption,
    get_port,
)

# State object for common command arguments
class State:
    verbose: bool = False


state = State()

app = typer.Typer()


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """My CLI tool."""
    state.verbose = verbose


class MDNSDeviceFinder:
    """Encapsulates mDNS logic for finding pcb-map devices"""

    def __init__(self) -> None:
        self.devices_found: list[str] = []
        self.zeroconf = Zeroconf()

        self.browser = ServiceBrowser(
            self.zeroconf, MDNS_SERVICE_TYPE, handlers=[self._on_service_state_change]
        )

    def _on_service_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        """Handle mDNS service state changes"""
        if state_change == ServiceStateChange.Added:
            if BASE_NAME in name.lower():
                self.devices_found.append(name)
                typer.echo(f"✓ Found mDNS device: {name}")

    def find_devices(self, timeout: float = 3.0) -> bool:
        """Search for pcb-map devices via mDNS"""
        typer.echo("Using mDNS to find devices")
        typer.echo(f"Resolving {MDNS_HOSTNAME}...")
        try:
            results = socket.getaddrinfo(MDNS_HOSTNAME, None)
            ips = set(r[4][0] for r in results)
            typer.echo(f"✓ Found IP addresses: {ips}")
        except socket.gaierror:
            typer.echo(f"Could not resolve {MDNS_HOSTNAME}")
            typer.echo("✗ pcb-map device not found via mDNS.")
            self.zeroconf.close()
            return False

        typer.echo(f"Searching for pcb-map service via mDNS (timeout: {timeout}s)...")
        time.sleep(timeout)
        self.zeroconf.close()
        found = len(self.devices_found) > 0
        if found:
            typer.echo("✓ pcb-map service found!")
        else:
            typer.echo("✗ pcb-map service not found via mDNS.")

        return found


class MQTTDeviceFinder:
    """Encapsulates MQTT logic for finding pcb-map devices"""

    def __init__(
        self, hostname: str, port: int, username: str, password: str, use_tls: bool
    ) -> None:
        self.client = MQTTClient(
            host=hostname,
            port=port,
            username=username or None,
            password=password or None,
            use_tls=use_tls,
            subscribe_topics=[MQTT_PONG_TOPIC],
            client_id="device-finder",
        )

    def find_device(self) -> bool:
        """Connect to MQTT broker and check for pcb-map device"""
        typer.echo(f"Pinging device over MQTT: {self.client._host}:{self.client._port}")

        if not self.client.connect():
            typer.echo("✗ Unable to connect to MQTT broker.", err=True)
            return False

        typer.echo("✓ Connected to MQTT broker")

        # Subscribe to pong topic and send ping
        typer.echo("Sending ping to pcb-map device...")
        self.client.send("ping", MQTT_PING_TOPIC)

        # Wait for pong response
        wait_time = 3
        start_time = time.time()
        device_found = False
        while (time.time() - start_time) < wait_time:
            messages = self.client.get_messages()
            for topic, payload in messages:
                if topic == MQTT_PONG_TOPIC:
                    device_found = True
                    typer.echo("✓ Received pong from pcb-map device")
                    break
            if device_found:
                break
            time.sleep(0.1)

        if not device_found:
            typer.echo("✗ pcb-map device did not respond to MQTT ping")

        self.client.disconnect()
        return device_found


class WiFiAPFinder:
    def find_device(self) -> bool:
        typer.echo("Scanning for pcb-map configuration AP")
        wifi = pywifi.PyWiFi()

        try:
            if len(wifi.interfaces()) == 0:
                typer.echo("✗ No WiFi interfaces")
                return False
        except PermissionError:
            typer.echo("✗ Need root to scan WiFi interface")
            return False

        for iface in wifi.interfaces():
            typer.echo(f"Scanning {iface.name()}")
            # Scan for APs
            iface.scan()
            time.sleep(3)  # wait for scan to complete

            results = iface.scan_results()
            for ap in results:
                if state.verbose:
                    typer.echo(ap.ssid, ap.signal, ap.bssid)
                if AP_SSID in ap.ssid:
                    typer.echo(
                        "✓ pcb-map-ap found. Connect and enter wifi credentials."
                    )
                    return True

        typer.echo("✗ pcb-map-ap missing. Device powered off or non-functional.")
        return False


@app.command()
def find_devices(
    hostname: HostnameOption = DEFAULT_BROKER,
    port: PortOption = 0,
    use_tls: UseTlsOption = False,
    username: UsernameOption = "",
    password: PasswordOption = "",
) -> None:
    """Find if there pcb-map is online and connected"""
    port = get_port(port, use_tls)
    mdns_finder = MDNSDeviceFinder()
    if mdns_finder.find_devices():
        finder = MQTTDeviceFinder(hostname, port, username, password, use_tls)
        finder.find_device()
    else:
        WiFiAPFinder().find_device()


@app.command()
def setup_mqtt(
    hostname: HostnameOption = DEFAULT_BROKER,
    port: PortOption = 0,
    use_tls: UseTlsOption = False,
    username: UsernameOption = "",
    password: PasswordOption = "",
) -> None:
    """Setup the MQTT broker for the device"""
    port = get_port(port, use_tls)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(2.0)
        if "," in username or "," in password:
            typer.echo("',' not allowed in username or password")
            return

        use_tls_val = 1 if use_tls else 0

        message = f"SET_MQTT {hostname},{port},{use_tls_val},{username},{password}"
        sock.sendto(message.encode(), (MDNS_HOSTNAME, UDP_MQTT_CONFIG_PORT))

        data, addr = sock.recvfrom(4096)
        typer.echo(data.decode())


if __name__ == "__main__":
    app()
