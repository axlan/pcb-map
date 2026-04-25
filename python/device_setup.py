"""Device setup script for PCB map"""

import time
import socket
import ssl

import paho.mqtt.client as mqtt
import typer
from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

import pywifi

app = typer.Typer()

BASE_NAME='pcb-map'
MDNS_HOSTNAME=BASE_NAME + '.local'
AP_SSID=BASE_NAME + '-ap'
MDNS_SERVICE_TYPE = '_mqtt-config._udp.local.'
MQTT_PING_TOPIC = BASE_NAME + '/ping'
MQTT_PONG_TOPIC = BASE_NAME + '/pong'
UDP_MQTT_CONFIG_PORT = 5432

class MDNSDeviceFinder:
    """Encapsulates mDNS logic for finding pcb-map devices"""

    def __init__(self, verbose=False) -> None:
        self.devices_found: list[str] = []
        self.zeroconf = Zeroconf()
        self.verbose = verbose

        self.browser = ServiceBrowser(self.zeroconf, MDNS_SERVICE_TYPE, handlers=[self._on_service_state_change])

    def _on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        """Handle mDNS service state changes"""
        if state_change == ServiceStateChange.Added:
            if BASE_NAME in name.lower():
                self.devices_found.append(name)
                typer.echo(f"✓ Found mDNS device: {name}")

    def find_devices(self, timeout: float = 3.0) -> bool:
        """Search for pcb-map devices via mDNS"""
        print(f"Resolving {MDNS_HOSTNAME}...")
        try:
            results = socket.getaddrinfo(MDNS_HOSTNAME, None)
            ips = set(r[4][0] for r in results)
            print(f"✓ Found IP addresses: {ips}")
        except socket.gaierror:
            print(f"✗ Could not resolve {MDNS_HOSTNAME}")
            self.zeroconf.close()
            return False

        typer.echo(f"Searching for pcb-map devices via mDNS (timeout: {timeout}s)...")
        time.sleep(timeout)
        self.zeroconf.close()
        return len(self.devices_found) > 0


class MQTTDeviceFinder:
    """Encapsulates MQTT logic for finding pcb-map devices"""

    def __init__(self, hostname: str, port: int, username: str, password: str, use_tls: bool) -> None:
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.device_found = False
        self.mqtt_connected = False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="device-finder")
        if use_tls:
            self.client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client: mqtt.Client, userdata: dict, flags: dict, rc: int, properties=None) -> None:
        """MQTT connection callback"""
        if rc == 0:
            self.mqtt_connected = True
            typer.echo("✓ Connected to MQTT broker")
        else:
            typer.echo(f"✗ Connection failed with code {rc}")

    def _on_message(self, client: mqtt.Client, userdata: dict, msg: mqtt.MQTTMessage) -> None:
        """MQTT message callback"""
        if msg.topic == MQTT_PONG_TOPIC:
            self.device_found = True
            typer.echo("✓ Received pong from pcb-map device")

    def find_device(self) -> bool:
        """Connect to MQTT broker and check for pcb-map device"""
        # Set credentials if provided
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        # Connect to broker
        try:
            self.client.connect(self.hostname, self.port, keepalive=5)
        except Exception as e:
            typer.echo(f"✗ Failed to connect to MQTT broker: {e}", err=True)
            return False

        # Start network loop
        self.client.loop_start()

        # Wait for connection
        timeout = 5
        start_time = time.time()
        while not self.mqtt_connected and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        if not self.mqtt_connected:
            typer.echo("✗ Failed to connect to MQTT broker within timeout", err=True)
            self.client.loop_stop()
            return False

        # Subscribe to pong topic and send ping
        self.client.subscribe(MQTT_PONG_TOPIC)
        typer.echo("Sending ping to pcb-map device...")
        self.client.publish(MQTT_PING_TOPIC, "ping")

        # Wait for pong response
        wait_time = 3
        start_time = time.time()
        while not self.device_found and (time.time() - start_time) < wait_time:
            time.sleep(0.1)

        # Stop the loop and disconnect
        self.client.loop_stop()
        self.client.disconnect()

        return self.device_found

class WiFiAPFinder:
    def find_device(self, verbose=False) -> bool:
        wifi = pywifi.PyWiFi()

        try:
            if len(wifi.interfaces()) == 0:
                typer.echo("No WiFi interfaces")
                return False
        except PermissionError:
            typer.echo("Need root to scan WiFi interface")
            return False

        for iface in wifi.interfaces():
            print(f"Scanning {iface.name()}")
            # Scan for APs
            iface.scan()
            time.sleep(3)  # wait for scan to complete

            results = iface.scan_results()
            for ap in results:
                if verbose:
                    print(ap.ssid, ap.signal, ap.bssid)
                if AP_SSID in ap.ssid:
                    return True
        return False


@app.command()
def find_devices(
    hostname: str = typer.Option("bee.internal", help="MQTT broker hostname"),
    port: int = typer.Option(0, help="MQTT broker port. Default based on '--use_tls'."),
    use_tls: bool = typer.Option(False, help="Use default TLS port"),
    username: str = typer.Option("", help="MQTT broker username"),
    password: str = typer.Option("", help="MQTT broker password"),
    verbose: bool = typer.Option(False, help="Enable verbose logging"),
) -> None:
    """Find available devices"""
    if port == 0:
        port = 8883 if use_tls else 1883

    typer.echo("Using mDNS to find devices")
    mdns_finder = MDNSDeviceFinder(verbose)
    if mdns_finder.find_devices():
        typer.echo("✓ pcb-map device(s) found!")

        # Use MQTT ping/pong to find devices
        typer.echo(f"Pinging device over MQTT: {hostname}:{port}")
        finder = MQTTDeviceFinder(hostname, port, username, password, use_tls)
        if finder.find_device():
            typer.echo("✓ pcb-map device responded")
        else:
            if not finder.mqtt_connected:
                typer.echo("✗ Unable to connect to MQTT broker.")
            else:
                typer.echo("✗ pcb-map device did not respond.")
    else:
        typer.echo("✗ pcb-map device not found via mDNS.")

        typer.echo("Looking for device setup AP ('pcb-map-ap')")
        if not WiFiAPFinder().find_device(verbose):
            typer.echo("✗ pcb-map-ap missing. Device offline or non-functional.")
        else:
            typer.echo("✓ pcb-map-ap found. Connect and enter wifi credentials.")


@app.command()
def setup_mqtt(
    hostname: str = typer.Option(help="MQTT broker hostname"),
    port: int = typer.Option(0, help="MQTT broker port. Default based on '--use_tls'."),
    use_tls: bool = typer.Option(False, help="Use TLS connection"),
    username: str = typer.Option("", help="MQTT broker username"),
    password: str = typer.Option("", help="MQTT broker password"),
    pcb_map_hostname: str = typer.Option(MDNS_HOSTNAME, help="pcb-map device address"),
    verbose: bool = typer.Option(False, help="Enable verbose logging"),
) -> None:
    if port == 0:
        port = 8883 if use_tls else 1883

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(2.0)
        if ',' in username or ',' in password:
            print("',' not allowed in username or password")
            return

        use_tls_val = 1 if use_tls else 0

        message = f'SET_MQTT {hostname},{port},{use_tls_val},{username},{password}'
        sock.sendto(message.encode(), (pcb_map_hostname, UDP_MQTT_CONFIG_PORT))

        data, addr = sock.recvfrom(4096)
        print(data.decode())


if __name__ == "__main__":
    app()
