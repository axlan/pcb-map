from typing import Annotated
import typer

DEFAULT_BROKER = "bee.internal"
BASE_NAME = "pcb-map"
MDNS_HOSTNAME = BASE_NAME + ".local"
AP_SSID = BASE_NAME + "-ap"
MDNS_SERVICE_TYPE = "_mqtt-config._udp.local."
UDP_MQTT_CONFIG_PORT = 5432
MQTT_PING_TOPIC = BASE_NAME + "/ping"
MQTT_PONG_TOPIC = BASE_NAME + "/pong"
MQTT_SET_BRIGHTNESS_TOPIC = BASE_NAME + "/set_brightness"
MQTT_SPRITE_DELETE_TOPIC = BASE_NAME + "/sprite_delete"
MQTT_SPRITE_UPDATE_TOPIC = BASE_NAME + "/sprite_update"
MQTT_SPRITES_CLEAR_TOPIC = BASE_NAME + "/sprites_clear"
MQTT_SET_BACKGROUND_TOPIC = BASE_NAME + "/set_background"
MQTT_CLEAR_BACKGROUND_TOPIC = BASE_NAME + "/clear_background"

MATRIX_WIDTH = 64
MATRIX_HEIGHT = 32
START_LATITUDE = 0
START_LONGITUDE = 0
END_LATITUDE = 0
END_LONGITUDE = 0

HostnameOption = Annotated[
    str, typer.Option("--hostname", "-h", help="MQTT broker hostname")
]
PortOption = Annotated[
    int,
    typer.Option(
        "--port",
        "-p",
        help="MQTT broker port. Default based on '--use-tls'",
        show_default="1883/8883",
    ),
]
UseTlsOption = Annotated[
    bool, typer.Option("--use-tls", "-t", help="Use TLS for connection")
]
UsernameOption = Annotated[
    str, typer.Option("--username", "-u", help="MQTT broker username")
]
PasswordOption = Annotated[
    str, typer.Option("--password", "-P", help="MQTT broker password")
]

def get_port(port_arg: int, use_tls: bool) -> int:
    if port_arg == 0:
        return 8883 if use_tls else 1883
    else:
        return port_arg
