from pathlib import Path
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
MQTT_BACKGROUND_SET_ROW_TOPIC = BASE_NAME + "/background_set_row"
MQTT_BACKGROUND_HIDE_TOPIC = BASE_NAME + "/background_hide"
MQTT_BACKGROUND_SHOW_TOPIC = BASE_NAME + "/background_show"

MATRIX_WIDTH = 64
MATRIX_HEIGHT = 32
START_LATITUDE = 37.90735631520354
START_LONGITUDE = -122.32360276594092
END_LATITUDE = 37.75305011125813
END_LONGITUDE = -122.22494771556514
ROUTE_TILE_MIN_DISTANCE_MILES = 0.05


MQTTHostnameOption = Annotated[
    str, typer.Option("--mqtt-hostname", "-h", help="MQTT broker hostname", envvar="MQTT_HOSTNAME")
]
MQTTPortOption = Annotated[
    int,
    typer.Option(
        "--mqtt-port",
        "-p",
        help="MQTT broker port. Default based on '--mqtt-use-tls'",
        show_default="1883/8883",
        envvar="MQTT_PORT",
    ),
]
MQTTUseTlsOption = Annotated[
    bool, typer.Option("--mqtt-use-tls", "-t", help="Use TLS for connection", envvar="MQTT_USE_TLS")
]
MQTTUsernameOption = Annotated[
    str, typer.Option("--mqtt-username", "-u", help="MQTT broker username", envvar="MQTT_USERNAME")
]
MQTTPasswordOption = Annotated[
    str, typer.Option("--mqtt-password", "-P", help="MQTT broker password", envvar="MQTT_PASSWORD")
]

def get_port(port_arg: int, use_tls: bool) -> int:
    if port_arg == 0:
        return 8883 if use_tls else 1883
    else:
        return port_arg

CACHE_DIR = Path(__file__).parents[2] / '.cache'

# y increases from west to east and x increases from south to north
def get_matrix_point_for_lat_long(latitude: float, longitude: float) -> tuple[int, int]:
    """Maps a GPS coordinate to a pixel point on the LED matrix."""
    # Calculate the normalized ratios for the given coordinates
    lat_ratio = (latitude - END_LATITUDE) / (START_LATITUDE - END_LATITUDE)
    long_ratio = (longitude - START_LONGITUDE) / (END_LONGITUDE - START_LONGITUDE)

    # Scale to matrix dimensions and convert to integers
    x = int(lat_ratio * (MATRIX_WIDTH - 1))
    y = int(long_ratio * (MATRIX_HEIGHT - 1))

    # Clamp values to ensure they remain within valid matrix indices
    return max(0, min(MATRIX_WIDTH - 1, x)), max(0, min(MATRIX_HEIGHT - 1, y))
