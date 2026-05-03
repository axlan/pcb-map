#!/usr/bin/env -S uv run
"""Control server for PCB map"""

from pathlib import Path
import sys
import time
import struct

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
    MQTT_SET_BACKGROUND_TOPIC,
)

# State object for common command arguments
class State:
    verbose: bool = False

TEST_IMAGE_PATH = Path(__file__).parents[2] / 'images/test_image.png'

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
        rgb565_pixels.extend(struct.pack(">H", pixel_565))

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

        client.send(rgb565_pixels, MQTT_SET_BACKGROUND_TOPIC)
    




if __name__ == "__main__":
    app()
