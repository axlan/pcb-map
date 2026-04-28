
`pio run -t upload --upload-port pcb-map.local`

`clang-format -style=Google -i firmware/src/*`

`source ~/hivemq_creds.sh`

`mosquitto_sub -h $MQTT_HOST -p 8883 -t "#" -v -d -u $MQTT_USER -P $MQTT_PASS`

`openssl s_client -showcerts -connect $MQTT_HOST:8883 </dev/null`

`sudo -E env PATH=$PATH uv run device-setup find-devices --hostname=$MQTT_HOST --use-tls --username=$MQTT_USER --password=$MQTT_PASS`

`uv run device-setup setup-mqtt --hostname=$MQTT_HOST --use-tls --username=$MQTT_USER --password=$MQTT_PASS`

`uv run device-setup setup-mqtt --hostname=$MQTT_HOST --use-tls --username=$MQTT_USER --password=$MQTT_PASS`
`uv run device-setup setup-mqtt --hostname=$MQTT_HOST --use-tls --username=$MQTT_USER --password=$MQTT_PASS`
