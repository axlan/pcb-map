#!/usr/bin/env -S uv run
"""Control server for PCB map"""

import json
from pathlib import Path
import sys
import time
import struct
from typing import Annotated

import typer
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]))

from pcb_map.mqtt_client import MQTTClient
from pcb_map.constants import (
    DEFAULT_BROKER,
    MATRIX_HEIGHT,
    MATRIX_WIDTH,
    HostnameOption,
    PortOption,
    UseTlsOption,
    UsernameOption,
    PasswordOption,
    get_port,
    MQTT_BACKGROUND_SHOW_TOPIC,
    MQTT_BACKGROUND_HIDE_TOPIC,
    MQTT_BACKGROUND_SET_ROW_TOPIC,
    MQTT_SPRITE_UPDATE_TOPIC,
    get_matrix_point_for_lat_long
)

# State object for common command arguments
class State:
    verbose: bool = False

TEST_IMAGE_PATH = Path(__file__).parents[2] / 'images/test_image.bmp'

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
    hostname: HostnameOption = DEFAULT_BROKER,
    port: PortOption = 0,
    use_tls: UseTlsOption = False,
    username: UsernameOption = "",
    password: PasswordOption = "",
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
    port = get_port(port, use_tls)
    with MQTTClient(
            host=hostname,
            port=port,
            username=username or None,
            password=password or None,
            use_tls=use_tls,
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
    hostname: HostnameOption = DEFAULT_BROKER,
    port: PortOption = 0,
    use_tls: UseTlsOption = False,
    username: UsernameOption = "",
    password: PasswordOption = ""
) -> None:
    typer.echo("Sending test location marker")

    x, y = get_matrix_point_for_lat_long(latitude, longitude)

    """Setup the MQTT broker for the device"""
    port = get_port(port, use_tls)
    with MQTTClient(
            host=hostname,
            port=port,
            username=username or None,
            password=password or None,
            use_tls=use_tls,
            client_id="control-server",
        ) as client:

        message_str = json.dumps({"name":"test_loc","x":x,"y":y,"color":rgb_to_rgb565(255, 0, 0)})
        client.send(payload=message_str, topic=MQTT_SPRITE_UPDATE_TOPIC)


if __name__ == "__main__":
    app()
