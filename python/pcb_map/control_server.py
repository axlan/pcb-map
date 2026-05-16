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
from locationsharinglib import Service, InvalidCookies

sys.path.insert(0, str(Path(__file__).parents[1]))

from pcb_map.mqtt_client import MQTTClient
from pcb_map.google_maps_route import get_route_coords, get_route_segments
from pcb_map.route_utils import quantize_route

from pcb_map.constants import (
    DEFAULT_BROKER,
    MATRIX_HEIGHT,
    MATRIX_WIDTH,
    MQTT_SPRITE_DELETE_TOPIC,
    MQTT_SPRITES_CLEAR_TOPIC,
    RED,
    COLORS,
    YELLOW,
    MQTTHostnameOption,
    MQTTPortOption,
    MQTTUseTlsOption,
    MQTTUsernameOption,
    MQTTPasswordOption,
    LEDPulseOption,
    get_port,
    MQTT_SET_BRIGHTNESS_TOPIC,
    MQTT_BACKGROUND_SHOW_TOPIC,
    MQTT_BACKGROUND_HIDE_TOPIC,
    MQTT_BACKGROUND_SET_ROW_TOPIC,
    MQTT_SPRITE_UPDATE_TOPIC,
    get_matrix_point_for_lat_long,
    ROUTE_TILE_MIN_DISTANCE_MILES,
)

COOKIE_IMAGE = Path(__file__).parents[2] / 'example_data/cookie.bmp'

# State object for common command arguments
class State:
    verbose: bool = False


state = State()

app = typer.Typer()

def get_cookie_hash(cookie_file: Path) -> int:
    return hash(cookie_file.read_text())

def rgb_to_rgb565(r: int, g: int, b: int) -> int:
    """Convert 8-bit RGB channels to a 16-bit RGB565 value."""
    r5 = (r >> 3) & 0x1F  # 5 bits
    g6 = (g >> 2) & 0x3F  # 6 bits
    b5 = (b >> 3) & 0x1F  # 5 bits
    return (r5 << 11) | (g6 << 5) | b5


def load_color_config(user_colors_file: Path) -> dict[str, tuple[int, int, int]]:
    if not user_colors_file.exists():
        typer.echo(f"Error: Config file '{user_colors_file}' not found.", err=True)
        raise typer.Exit(code=1)
    try:
        user_colors = json.load(user_colors_file.open())
        typer.echo(f"Loaded display preferences from '{user_colors_file}'.")
        return user_colors
    except json.JSONDecodeError as e:
        typer.echo(
            f"Error decoding JSON from config file '{user_colors_file}': {e}",
            err=True,
        )
        raise typer.Exit(code=1)


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """My CLI tool."""
    state.verbose = verbose


def send_image_to_panel(image: Image.Image, client: MQTTClient):
    if image.height == 64:
        image = image.transpose(Image.ROTATE_270) # type: ignore

    pixels = list(image.getdata()) # type: ignore
    rgb565_pixels = bytearray()
    for r, g, b in pixels:
        pixel_565 = rgb_to_rgb565(r, g, b)
        rgb565_pixels.extend(struct.pack("<H", pixel_565))
    BYTES_PER_ROW = MATRIX_WIDTH * 2
    for row in range(MATRIX_HEIGHT):
        start_byte = row * BYTES_PER_ROW
        client.send(
            struct.pack("<B", row)
            + rgb565_pixels[start_byte : start_byte + BYTES_PER_ROW],
            MQTT_BACKGROUND_SET_ROW_TOPIC,
        )


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

    width, height = img.size
    if not (width == MATRIX_WIDTH and height == MATRIX_HEIGHT) and not (width == MATRIX_HEIGHT and height == MATRIX_WIDTH):
        typer.echo(f"Error: Image must be {MATRIX_WIDTH}x{MATRIX_HEIGHT}.", err=True)
        raise typer.Exit(code=1)

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
        send_image_to_panel(img, client)
        client.send(payload=b"", topic=MQTT_BACKGROUND_SHOW_TOPIC)


@app.command()
def send_test_point(
    lat_long_str: Annotated[
        str, typer.Argument(help="Comma separated latitude and longitude in degrees")
    ],
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = "",
    pulse_leds: LEDPulseOption = False,
) -> None:
    typer.echo("Sending test location marker")
    latitude, longitude = map(float, lat_long_str.split(","))
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
        msg_data = {"name": "test_loc", "x": x, "y": y, "color": rgb_to_rgb565(*RED)}
        if not pulse_leds:
            msg_data["end_color"] = msg_data["color"]

        client.send(payload=json.dumps(msg_data), topic=MQTT_SPRITE_UPDATE_TOPIC)


@app.command()
def simulate_route(
    start: Annotated[str, typer.Option("--start", "-s", help="Route start address")],
    dest: Annotated[str, typer.Option("--dest", "-d", help="Route end address")],
    google_maps_key: Annotated[
        str,
        typer.Option(
            "--google-maps-key",
            "-k",
            help="Google Maps API key",
            envvar="GOOGLE_MAPS_API_KEY",
        ),
    ],
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = "",
    pulse_leds: LEDPulseOption = False,
) -> None:
    typer.echo("Displaying route")

    segments = get_route_segments(start, dest, mode="driving", api_key=google_maps_key)
    coords = get_route_coords(segments)

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
            msg_data = {
                "name": f"segment_{i}",
                "x": segment.row,
                "y": segment.col,
                "color": rgb_to_rgb565(*RED),
                "offset_ms": i * 150,
            }
            if not pulse_leds:
                msg_data["end_color"] = msg_data["color"]

            client.send(payload=json.dumps(msg_data), topic=MQTT_SPRITE_UPDATE_TOPIC)


class RouteManager:
    def __init__(self) -> None:
        self.route_images = {}

    def add_route(self, name: str, points: list[tuple[int,int]], color=YELLOW):
        img = Image.new("RGBA", (64, 32), color=(0, 0, 0, 0))
        for point in points:
            img.putpixel(point, color)
        self.route_images[name] = img

    def get_image(self) -> Image.Image:
        combined = Image.new("RGBA", (64, 32), color=(0, 0, 0, 255))
        for img in self.route_images.values():
            combined = Image.alpha_composite(combined, img)
        return combined.convert("RGB")


@app.command()
def display_shared_locations(
    user_colors_file: Annotated[
        Optional[Path],
        typer.Option(
            "--user-colors-file",
            "-f",
            envvar="USER_COLORS_FILE",
            help="Path to a JSON file with display preferences (friend_name: [R, G, B])",
        ),
    ] = None,
    simulation_file: Annotated[
        Optional[Path],
        typer.Option(
            "--simulation-file",
            "-s",
            envvar="SIMULATION_FILE",
            help="Path to a JSON file with events to simulate.",
        ),
    ] = None,
    cookie_file: Annotated[
        Optional[Path],
        typer.Option(
            "--cookie-file",
            "-c",
            envvar="COOKIE_FILE",
            help="Path to a netscape formatted cookie file with maps.google.com credentials.",
        ),
    ] = None,
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = "",
    pulse_leds: LEDPulseOption = False,
) -> None:
    """Fetch shared Google locations and display them on the matrix."""
    typer.echo(f"Starting shared location display...")
    REQUESTOR_NAME = "me"

    if cookie_file and simulation_file:
        raise typer.BadParameter("--simulation-file and --cookie-file are mutually exclusive.")
    if not cookie_file and not simulation_file:
        raise typer.BadParameter("One of --cookie-file or --simulation-file is required.")

    known_users_only = False
    display_config: dict[str, tuple[int, int, int]] = {}
    if user_colors_file:
        display_config = load_color_config(user_colors_file)
        known_users_only = True

    route_manager = RouteManager()

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

            def _draw_person(name: str, x: int, y: int):
                if name not in display_config:
                    if known_users_only:
                        return
                    else:
                        display_config[name] = COLORS[len(display_config) % len(COLORS)]

                color = display_config[name]

                msg_data = {
                    "name": name,
                    "x": x,
                    "y": y,
                    "color": rgb_to_rgb565(*color),
                }
                if not pulse_leds:
                    msg_data["end_color"] = msg_data["color"]

                client.send(json.dumps(msg_data), MQTT_SPRITE_UPDATE_TOPIC)

            if cookie_file is not None:
                while True:
                    if not cookie_file.exists():
                        typer.echo(f"Error: Cookie file not found: {cookie_file}", err=True)
                        raise typer.Exit(code=1)

                    cookie_hash = 0
                    try:
                        typer.echo(f"Starting location sharing..")
                        cookie_hash = get_cookie_hash(cookie_file)
                        service = Service(cookies_file=cookie_file, authenticating_account=REQUESTOR_NAME)
                        while True:
                            people = list(service.get_all_people())
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
                                _draw_person(person.full_name, x, y)  # type: ignore

                            time.sleep(30)
                    except InvalidCookies:
                        typer.echo(f"Cookie file {cookie_file} invalid. Update to resume sharing location.", err=True)
                        img = Image.open(COOKIE_IMAGE).convert("RGB")
                        send_image_to_panel(img, client)
                        while cookie_hash == get_cookie_hash(cookie_file):
                            time.sleep(10)
                        client.send(payload=b"", topic=MQTT_BACKGROUND_HIDE_TOPIC)
                        
            elif simulation_file is not None:
                with simulation_file.open() as f:
                    events = json.load(f)
                now = 0
                for event in events:
                    time.sleep(event["time"] - now)
                    now = event["time"]
                    if event["type"] == "person":
                        if "delete" in event:
                            client.send(payload=event["name"], topic=MQTT_SPRITE_DELETE_TOPIC)
                            continue
                        elif "x" in event:
                            x, y = event["x"], event["y"]
                        else:
                            x, y = get_matrix_point_for_lat_long(
                                event["lat"], event["lng"]
                            )
                        _draw_person(event["name"], x, y)
                    elif event["type"] == "route":
                        if "delete" in event:
                            route_manager.route_images.pop(event["name"], None)
                        else:
                            route_manager.add_route(event["name"], event["points"])

                        img = route_manager.get_image()
                        send_image_to_panel(img, client)

                        client.send(payload=b"", topic=MQTT_BACKGROUND_SHOW_TOPIC)
                    else:
                        typer.echo(f"Unknown event type: {event['type']}")

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


@app.command()
def set_brightness(
    brightness: Annotated[float, typer.Argument(help="Brightness percentage (0-100)")],
    mqtt_hostname: MQTTHostnameOption = DEFAULT_BROKER,
    mqtt_port: MQTTPortOption = 0,
    mqtt_use_tls: MQTTUseTlsOption = False,
    mqtt_username: MQTTUsernameOption = "",
    mqtt_password: MQTTPasswordOption = "",
) -> None:
    """Set the display brightness (0-100)."""
    if not (0 <= brightness <= 100):
        typer.echo("Error: Brightness must be between 0 and 100.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Setting brightness to {brightness}%...")
    mqtt_port = get_port(mqtt_port, mqtt_use_tls)
    with MQTTClient(
        host=mqtt_hostname,
        port=mqtt_port,
        username=mqtt_username or None,
        password=mqtt_password or None,
        use_tls=mqtt_use_tls,
        client_id="control-server-brightness",
    ) as client:
        # Send brightness as a string to be parsed by the firmware's ParsePercent
        client.send(payload=str(brightness), topic=MQTT_SET_BRIGHTNESS_TOPIC)

@app.command()
def lat_long_to_xy(
    lat_long_str: Annotated[
        str, typer.Argument(help="Comma separated latitude and longitude in degrees")
    ],
) -> None:
    """Print the matrix x and y coordinates for a given latitude and longitude."""
    try:
        parts = lat_long_str.split(",")
        if len(parts) != 2:
            raise ValueError("Expected two values separated by a comma")
        latitude, longitude = map(float, parts)
    except ValueError as e:
        typer.echo(f"Error: Invalid input '{lat_long_str}'. Please provide 'latitude,longitude'.", err=True)
        raise typer.Exit(code=1)

    x, y = get_matrix_point_for_lat_long(latitude, longitude)
    typer.echo(f"X: {x}, Y: {y}")


if __name__ == "__main__":
    app()
