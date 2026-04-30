from typing import Annotated
import typer

DEFAULT_BROKER = "bee.internal"

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