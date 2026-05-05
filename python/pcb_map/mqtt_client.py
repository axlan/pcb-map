import logging
import queue
import threading
from typing import List, Optional, Tuple

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTClient:
    """
    Encapsulates an MQTT connection with automatic reconnection, thread-safe
    publishing, and a poll-style inbox for subscribed topics.

    Usage:
        client = MQTTClient(
            host="broker.example.com",
            subscribe_topics=["sensors/temp", "sensors/#"],
        )
        if client.connect():
            client.send(payload="hello", topic="commands/out")
            messages = client.get_messages()   # [(topic, payload), ...]
        client.disconnect()

    Or as a context manager:
        with MQTTClient(host="broker.example.com", subscribe_topics=["my/topic"]) as c:
            time.sleep(1)
            for topic, payload in c.get_messages():
                print(topic, payload)
    """

    def __init__(
        self,
        host: str,
        port: int = 1883,
        client_id: str = "",
        username: Optional[str] = None,
        password: Optional[str] = None,
        keepalive: int = 60,
        use_tls: bool = False,
        connect_timeout: float = 10.0,
        subscribe_topics: Optional[List[str]] = None,
    ):
        self._host = host
        self._port = port
        self._keepalive = keepalive
        self._connect_timeout = connect_timeout
        self._subscribe_topics: List[str] = subscribe_topics or []

        self._connected = False
        self._connect_event = threading.Event()

        # Thread-safe inbox — the network thread puts, the caller thread drains.
        self._inbox: queue.Queue[Tuple[str, str]] = queue.Queue()

        self._client = mqtt.Client(client_id=client_id)

        if username is not None:
            self._client.username_pw_set(username, password)

        if use_tls:
            self._client.tls_set()

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """
        Establish the MQTT connection and start the network loop.

        Returns:
            True if the connection succeeded, False otherwise.
        """
        if self._connected:
            return True

        try:
            self._connect_event.clear()
            self._client.connect(self._host, self._port, self._keepalive)
            self._client.loop_start()

            if not self._connect_event.wait(timeout=self._connect_timeout):
                logger.error(
                    "Connection to %s:%s timed out after %.1fs",
                    self._host,
                    self._port,
                    self._connect_timeout,
                )
                self._client.loop_stop()
                return False

            return self._connected

        except Exception as exc:
            logger.error("Failed to connect to %s:%s — %s", self._host, self._port, exc)
            return False

    def send(
        self,
        payload: mqtt.PayloadType,
        topic: str,
        qos: int = 0,
        retain: bool = False,
    ) -> bool:
        """
        Publish a message to the broker.

        Args:
            payload: Message content. Strings, bytes, int, float, or None are
                     passed straight to paho; anything else is converted with str().
            topic:   MQTT topic string.

        Returns:
            True if the message was queued successfully, False otherwise.
        """
        if not self._connected:
            logger.error("Cannot send — client is not connected.")
            return False

        if not topic:
            logger.error("Cannot send — topic must not be empty.")
            return False

        try:
            result = self._client.publish(topic, payload, qos=qos, retain=retain)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error("Publish to '%s' failed with code %s", topic, result.rc)
                return False

            return True

        except Exception as exc:
            logger.error("Exception while publishing to '%s': %s", topic, exc)
            return False

    def get_messages(self) -> List[Tuple[str, str]]:
        """
        Return all messages received since the last call and clear the inbox.

        Returns:
            A list of (topic, payload) tuples in arrival order.  The payload
            is always a str (decoded from bytes if necessary).  Returns an
            empty list if no messages have arrived.
        """
        messages = []
        while True:
            try:
                messages.append(self._inbox.get_nowait())
            except queue.Empty:
                return messages

    def disconnect(self) -> None:
        """Gracefully disconnect from the broker and stop the network loop."""
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self):
        if not self.connect():
            raise ConnectionError(
                f"Could not connect to MQTT broker at {self._host}:{self._port}"
            )
        return self

    def __exit__(self, *_):
        self.disconnect()

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        if rc == mqtt.CONNACK_ACCEPTED:
            self._connected = True
            logger.info("Connected to %s:%s", self._host, self._port)
            for topic in self._subscribe_topics:
                client.subscribe(topic)
                logger.debug("Subscribed to '%s'", topic)
        else:
            self._connected = False
            logger.error(
                "Connection refused by broker (rc=%s): %s",
                rc,
                mqtt.connack_string(rc),
            )
        self._connect_event.set()

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            logger.warning("Unexpected disconnection (rc=%s). Reconnecting…", rc)
        else:
            logger.info("Disconnected from %s:%s", self._host, self._port)

    def _on_message(self, client, userdata, message):
        topic = message.topic
        payload = message.payload.decode("utf-8", errors="replace")
        logger.debug("Received message on '%s'", topic)
        self._inbox.put_nowait((topic, payload))
