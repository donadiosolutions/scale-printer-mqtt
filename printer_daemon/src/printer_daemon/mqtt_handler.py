import logging
import threading
import time
import paho.mqtt.client as mqtt # type: ignore
import ssl
import queue

class PrinterMqttHandler(threading.Thread):
    def __init__(self, broker_host, port, username, password, client_id,
                 print_topic, qos, keepalive,
                 mqtt_to_serial_queue: queue.Queue, use_tls: bool = True):
        super().__init__(name="PrinterMqttHandlerThread")
        self.broker_host = broker_host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.print_topic = print_topic
        self.qos = qos
        self.keepalive = keepalive
        self.mqtt_to_serial_queue = mqtt_to_serial_queue # Messages to PrinterSerialHandler
        self.use_tls = use_tls
        self.running = False
        self.client: mqtt.Client | None = None
        self.connection_rc = -1 # To store connection result code
        self.reconnect_delay = 5  # seconds

        logging.info(f"PrinterMqttHandler initialized for broker {self.broker_host}:{self.port} (TLS: {self.use_tls}).")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        self.connection_rc = rc
        if rc == 0:
            logging.info(f"Successfully connected to MQTT broker {self.broker_host}:{self.port}. Subscribing...")
            client.subscribe(self.print_topic, qos=self.qos)
            logging.info(f"Subscribed to {self.print_topic} with QoS {self.qos}.")
        else:
            logging.error(f"Failed to connect to MQTT broker: {mqtt.connack_string(rc)}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        logging.warning(f"Disconnected from MQTT broker: {mqtt.connack_string(rc)}. Will attempt to reconnect.")

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage):
        try:
            logging.info(f"Received MQTT message on topic '{msg.topic}': {len(msg.payload)} bytes")
            if msg.topic == self.print_topic:
                if msg.payload:
                    try:
                        # The printer expects ASCII text. The scale already provides this.
                        # The serial handler will add LF.
                        message_str = msg.payload.decode('ascii', errors='replace')
                        self.mqtt_to_serial_queue.put(message_str)
                        logging.info(f"Message from '{msg.topic}' put to mqtt_to_serial_queue for printing.")
                    except UnicodeDecodeError as ude:
                        logging.error(f"Could not decode MQTT payload from {msg.topic} as ASCII: {ude}. Payload: {msg.payload!r}")
                else:
                    logging.warning(f"Received empty payload on print topic {self.print_topic}.")
            else:
                logging.warning(f"Received message on unexpected topic: {msg.topic}")
        except Exception as e:
            logging.error(f"Error processing MQTT message for printer: {e}")

    def _setup_client(self):
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
            self.client.username_pw_set(self.username, self.password)
            if self.use_tls:
                logging.info("Configuring MQTT client with TLS for printer.")
                self.client.tls_set(
                    cert_reqs=ssl.CERT_REQUIRED,
                    tls_version=ssl.PROTOCOL_TLS_CLIENT,
                )
            else:
                logging.info("Configuring MQTT client without TLS for printer.")
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            return True
        except Exception as e:
            logging.error(f"Error setting up MQTT client for printer: {e}")
            self.client = None
            return False

    def run(self):
        self.running = True
        logging.info("PrinterMqttHandler thread started.")

        if not self._setup_client() or not self.client:
            logging.error("Printer MQTT client setup failed. Thread cannot start.")
            self.running = False
            return

        while self.running:
            if not self.client.is_connected():
                try:
                    logging.info(f"Attempting to connect to MQTT broker {self.broker_host}:{self.port} for printer...")
                    self.connection_rc = -1
                    self.client.connect(self.broker_host, self.port, self.keepalive)
                    self.client.loop_start()

                    connect_timeout = time.time() + 10
                    while self.connection_rc == -1 and time.time() < connect_timeout and self.running:
                        time.sleep(0.1)

                    if self.connection_rc != 0 and self.running:
                        logging.error(f"Printer MQTT connection failed. Will retry in {self.reconnect_delay}s.")
                        self.client.loop_stop()
                        time.sleep(self.reconnect_delay)
                        continue
                    elif not self.running:
                        break
                except ConnectionRefusedError:
                    logging.error(f"Printer MQTT ConnectionRefusedError. Retrying in {self.reconnect_delay}s.")
                    time.sleep(self.reconnect_delay)
                    continue
                except Exception as e:
                    logging.error(f"Error connecting printer MQTT client: {e}. Retrying in {self.reconnect_delay}s.")
                    if self.client.is_connected():
                        self.client.loop_stop()
                    time.sleep(self.reconnect_delay)
                    continue

            # Unlike scale, printer MQTT handler is mostly reactive (receives messages).
            # The loop_start() handles receiving messages in its own thread.
            # We just need to keep this thread alive and check `self.running`.
            time.sleep(0.1) # Keep alive, check running flag

        if self.client:
            if self.client.is_connected():
                logging.info("Disconnecting printer MQTT client...")
                self.client.loop_stop()
                self.client.disconnect()
            else:
                self.client.loop_stop(force=True)
        logging.info("PrinterMqttHandler thread stopped.")

    def stop(self):
        self.running = False
        logging.info("Stopping PrinterMqttHandler thread...")
