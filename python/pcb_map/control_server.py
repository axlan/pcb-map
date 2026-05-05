#!/usr/bin/env -S uv run
"""Control server for PCB map"""

import json
from pathlib import Path
import sys
import time
import struct
from typing import Annotated, Optional

import typer
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]))

from pcb_map.mqtt_client import MQTTClient
from pcb_map.route_utils import get_route_coords, quantize_route
from pcb_map.shared_location_interface import (
    fetch_locations,
    COOKIES_FILE,
    get_firefox_location_cookie,
)
from pcb_map.constants import (
    DEFAULT_BROKER,
    MATRIX_HEIGHT,
    MATRIX_WIDTH,
    MQTT_SPRITES_CLEAR_TOPIC,
    RED,
    COLORS,
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


# State object for common command arguments
class State:
    verbose: bool = False


state = State()

app = typer.Typer()


def rgb_to_rgb565(r: int, g: int, b: int) -> int:
    """Convert 8-bit RGB channels to a 16-bit RGB565 value."""
    r5 = (r >> 3) & 0x1F  # 5 bits
    g6 = (g >> 2) & 0x3F  # 6 bits
    b5 = (b >> 3) & 0x1F  # 5 bits
    return (r5 << 11) | (g6 << 5) | b5


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """My CLI tool."""
    state.verbose = verbose


@app.command()
def set_background_image(
    image_file: Annotated[Path, typer.Argument(help="background image to set (32x64)")],
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = "",
) -> None:
    typer.echo("Sending background image")
    if not image_file.exists():
        typer.echo(f"Error: '{image_file}' not found.", err=True)
        raise typer.Exit(code=1)

    """Load an image and return a list of RGB565 pixel values."""
    img = Image.open(image_file).convert("RGB")

    if img.height == 64:
        img = img.transpose(Image.ROTATE_270)

    width, height = img.size
    if width != MATRIX_WIDTH or height != MATRIX_HEIGHT:
        typer.echo(f"Error: Image must be {MATRIX_WIDTH}x{MATRIX_HEIGHT}.", err=True)
        raise typer.Exit(code=1)

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
            client.send(
                struct.pack("<B", row)
                + rgb565_pixels[start_byte : start_byte + BYTES_PER_ROW],
                MQTT_BACKGROUND_SET_ROW_TOPIC,
            )
        client.send(payload=b"", topic=MQTT_BACKGROUND_SHOW_TOPIC)


@app.command()
def send_test_point(
    latitude: Annotated[float, typer.Option("--latitude", help="latitude to draw on")],
    longitude: Annotated[
        float, typer.Option("--longitude", help="longitude to draw on")
    ],
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = "",
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

        message_str = json.dumps(
            {"name": "test_loc", "x": x, "y": y, "color": rgb_to_rgb565(*RED)}
        )
        client.send(payload=message_str, topic=MQTT_SPRITE_UPDATE_TOPIC)


@app.command()
def simulate_route(
    start: Annotated[str, typer.Option("--start", "-s", help="Route start address")],
    dest: Annotated[str, typer.Option("--dest", "-d", help="Route end address")],
    open_route_service_key: Annotated[
        str,
        typer.Option(
            "--open-route-service-key",
            "-k",
            help="Open Route Service API key",
            envvar="OPEN_ROUTE_SERVICE_KEY",
        ),
    ],
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = "",
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
            message_str = json.dumps(
                {
                    "name": f"segment_{i}",
                    "x": segment.row,
                    "y": segment.col,
                    "color": rgb_to_rgb565(*RED),
                    "offset_ms": i * 150,
                }
            )
            client.send(payload=message_str, topic=MQTT_SPRITE_UPDATE_TOPIC)


@app.command()
def display_shared_locations(
    user_colors_file: Annotated[
        Optional[Path],
        typer.Option(
            "--user-colors-file",
            "-c",
            envvar="USER_COLORS_FILE",
            help="Path to a JSON file with display preferences (friend_name: [R, G, B])",
        ),
    ] = None,
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = "",
) -> None:
    """Fetch shared Google locations and display them on the matrix."""
    typer.echo(f"Starting shared location display...")
    REQUESTOR_NAME = "me"

    display_config = None
    if user_colors_file:
        if not user_colors_file.exists():
            typer.echo(f"Error: Config file '{user_colors_file}' not found.", err=True)
            raise typer.Exit(code=1)
        try:
            display_config = json.load(user_colors_file.open())
            typer.echo(f"Loaded display preferences from '{user_colors_file}'.")
        except json.JSONDecodeError as e:
            typer.echo(
                f"Error decoding JSON from config file '{user_colors_file}': {e}",
                err=True,
            )
            raise typer.Exit(code=1)

    mqtt_port = get_port(mqtt_port, mqtt_use_tls)

    try:
        with MQTTClient(
            host=mqtt_hostname,
            port=mqtt_port,
            username=mqtt_username or None,
            password=mqtt_password or None,
            use_tls=mqtt_use_tls,
            client_id="control-server-shared-loc",
        ) as client:
            get_firefox_location_cookie()
            while True:
                people = fetch_locations(COOKIES_FILE, REQUESTOR_NAME)
                if state.verbose:
                    typer.echo(f"\nFound {len(people)} people sharing location:\n")
                    for person in people:
                        typer.echo(f"  Name:      {person.full_name}")
                        typer.echo(f"  Latitude:  {person.latitude}")
                        typer.echo(f"  Longitude: {person.longitude}")
                        typer.echo(f"  Address:   {person.address}")
                        typer.echo(f"  Last seen: {person.datetime}")
                        typer.echo()
                for i, person in enumerate(people):
                    x, y = get_matrix_point_for_lat_long(person.latitude, person.longitude)  # type: ignore

                    if display_config:
                        if person.full_name in display_config:
                            color = display_config[person.full_name]
                        else:
                            continue
                    else:
                        color = COLORS[i % len(COLORS)]

                    message = {
                        "name": person.full_name,
                        "x": x,
                        "y": y,
                        "color": rgb_to_rgb565(*color),
                    }
                    client.send(json.dumps(message), MQTT_SPRITE_UPDATE_TOPIC)

                time.sleep(30)
    except KeyboardInterrupt:
        typer.echo("\nStopping shared location display.")


@app.command()
def clear_display(
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = "",
) -> None:
    """Clear all sprites and hide the background on the matrix."""
    typer.echo("Clearing display...")
    mqtt_port = get_port(mqtt_port, mqtt_use_tls)
    with MQTTClient(
        host=mqtt_hostname,
        port=mqtt_port,
        username=mqtt_username or None,
        password=mqtt_password or None,
        use_tls=mqtt_use_tls,
        client_id="control-server-clear",
    ) as client:
        client.send(payload=b"", topic=MQTT_SPRITES_CLEAR_TOPIC)
        client.send(payload=b"", topic=MQTT_BACKGROUND_HIDE_TOPIC)


if __name__ == "__main__":
    app()
