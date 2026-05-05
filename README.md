
`./scripts/upload_firmware.sh`

`clang-format -style=Google -i firmware/src/*`

`uv --directory=python sync && source python/.venv/bin/activate`

`control-server display-shared-locations`
`device-setup find-devices`

`source ~/pcb_map_args.sh`
```sh
export MQTT_HOSTNAME=2919292921930120931032912309.s1.eu.hivemq.cloud
export MQTT_USE_TLS=1
export MQTT_USERNAME=user
export MQTT_PASSWORD=pass
export OPEN_ROUTE_SERVICE_KEY=asidasoidjewojjosaidjasoidjoi3242349023409234092
export USER_COLORS_FILE=$HOME/user_colors.json
```

user_colors.json
```json
{
    "me": [0, 255, 0],
    "Joe Smith": [0, 0, 255],
    "Mary Sue": [255, 0, 0]
}
```
