#!/usr/bin/env -S uv run
"""Control server for PCB map"""

import json
from pathlib import Path
import sys
import struct
from typing import Annotated

import typer
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]))

from pcb_map.mqtt_client import MQTTClient
from pcb_map.route_utils import get_route_coords, quantize_route
from pcb_map.constants import (
    DEFAULT_BROKER,
    MATRIX_HEIGHT,
    MATRIX_WIDTH,
    MQTTHostnameOption,
    MQTTPortOption,
    MQTTUseTlsOption,
    MQTTUsernameOption,
    MQTTPasswordOption,
    get_port,
    MQTT_BACKGROUND_SHOW_TOPIC,
    MQTT_BACKGROUND_HIDE_TOPIC,
    MQTT_BACKGROUND_SET_ROW_TOPIC,
    MQTT_SPRITE_UPDATE_TOPIC,
    get_matrix_point_for_lat_long,
    ROUTE_TILE_MIN_DISTANCE_MILES,
)

TEST_IMAGE_PATH = Path(__file__).parents[2] / 'images/test_image.bmp'

# State object for common command arguments
class State:
    verbose: bool = False


state = State()

app = typer.Typer()


def rgb_to_rgb565(r: int, g: int, b: int) -> int:
    """Convert 8-bit RGB channels to a 16-bit RGB565 value."""
    r5 = (r >> 3) & 0x1F   # 5 bits
    g6 = (g >> 2) & 0x3F   # 6 bits
    b5 = (b >> 3) & 0x1F   # 5 bits
    return (r5 << 11) | (g6 << 5) | b5


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """My CLI tool."""
    state.verbose = verbose

@app.command()
def send_test_image(
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = "",
) -> None:
    typer.echo("Sending test image")

    """Load an image and return a list of RGB565 pixel values."""
    img = Image.open(TEST_IMAGE_PATH).convert("RGB")
    width, height = img.size
    assert width == MATRIX_WIDTH
    assert height == MATRIX_HEIGHT

    pixels = list(img.getdata())
    rgb565_pixels = bytearray()
    for r, g, b in pixels:
        pixel_565 = rgb_to_rgb565(r, g, b)
        rgb565_pixels.extend(struct.pack("<H", pixel_565))

    """Setup the MQTT broker for the device"""
    mqtt_port = get_port(mqtt_port, mqtt_use_tls)
    with MQTTClient(
            host=mqtt_hostname,
            port=mqtt_port,
            username=mqtt_username or None,
            password=mqtt_password or None,
            use_tls=mqtt_use_tls,
            client_id="control-server",
        ) as client:

        BYTES_PER_ROW = MATRIX_WIDTH * 2
        for row in range(MATRIX_HEIGHT):
            start_byte = row * BYTES_PER_ROW
            client.send(struct.pack("<B", row) +rgb565_pixels[start_byte : start_byte + BYTES_PER_ROW], MQTT_BACKGROUND_SET_ROW_TOPIC)
        client.send(payload=b'', topic=MQTT_BACKGROUND_SHOW_TOPIC)

@app.command()
def send_test_point(
    latitude: Annotated[
        float,
        typer.Option(
            "--latitude",
            help="latitude to draw on"
        )
    ],
    longitude: Annotated[
        float,
        typer.Option(
            "--longitude",
            help="longitude to draw on"
        )
    ],
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = ""
) -> None:
    typer.echo("Sending test location marker")

    x, y = get_matrix_point_for_lat_long(latitude, longitude)

    """Setup the MQTT broker for the device"""
    mqtt_port = get_port(mqtt_port, mqtt_use_tls)
    with MQTTClient(
            host=mqtt_hostname,
            port=mqtt_port,
            username=mqtt_username or None,
            password=mqtt_password or None,
            use_tls=mqtt_use_tls,
            client_id="control-server",
        ) as client:

        message_str = json.dumps({"name":"test_loc","x":x,"y":y,"color":rgb_to_rgb565(255, 0, 0)})
        client.send(payload=message_str, topic=MQTT_SPRITE_UPDATE_TOPIC)

@app.command()
def simulate_route(
    start: Annotated[
        str, typer.Option("--start", "-s", help="Route start address")
    ],
    dest: Annotated[
        str, typer.Option("--dest", "-d", help="Route end address")
    ],
    open_route_service_key: Annotated[
        str, typer.Option("--open-route-service-key", "-k", help="Open Route Service API key", envvar="OPEN_ROUTE_SERVICE_KEY")
    ],
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = ""
) -> None:
    typer.echo("Getting Route from Open Route Service")

    coords = get_route_coords(start, dest, open_route_service_key)
    typer.echo(f"Route has {len(coords)} coordinate points.\n")

    segments = quantize_route(coords)


    """Setup the MQTT broker for the device"""
    mqtt_port = get_port(mqtt_port, mqtt_use_tls)
    with MQTTClient(
            host=mqtt_hostname,
            port=mqtt_port,
            username=mqtt_username or None,
            password=mqtt_password or None,
            use_tls=mqtt_use_tls,
            client_id="control-server",
        ) as client:

        for i, segment in enumerate(segments):
            if segment.distance_miles < ROUTE_TILE_MIN_DISTANCE_MILES:
                continue
            message_str = json.dumps({"name":f"segment_{i}","x":segment.row,"y":segment.col,"color":rgb_to_rgb565(255, 0, 0), "offset_ms": i * 150})
            client.send(payload=message_str, topic=MQTT_SPRITE_UPDATE_TOPIC)

if __name__ == "__main__":
    app()
