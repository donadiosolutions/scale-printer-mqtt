import logging
import threading
import time
import paho.mqtt.client as mqtt # type: ignore
import ssl

class ScaleMqttHandler(threading.Thread):
    def __init__(self, broker_host, port, username, password, client_id,
                 data_topic, command_topic, qos, keepalive,
                 serial_to_mqtt_queue, mqtt_to_serial_queue, use_tls: bool = True):
        super().__init__(name="ScaleMqttHandlerThread")
        self.broker_host = broker_host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.data_topic = data_topic
        self.command_topic = command_topic
        self.qos = qos
        self.keepalive = keepalive
        self.serial_to_mqtt_queue = serial_to_mqtt_queue # Data from Serial to publish
        self.mqtt_to_serial_queue = mqtt_to_serial_queue # Commands to Serial
        self.use_tls = use_tls
        self.running = False
        self.client: mqtt.Client | None = None
        self.connection_rc = -1 # To store connection result code
        self.reconnect_delay = 5 # seconds

        logging.info(f"ScaleMqttHandler initialized for broker {self.broker_host}:{self.port} (TLS: {self.use_tls}).")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        self.connection_rc = rc # Store result code
        if rc == 0:
            logging.info(f"Successfully connected to MQTT broker {self.broker_host}:{self.port}. Subscribing...")
            # Subscribe to the command topic
            client.subscribe(self.command_topic, qos=self.qos)
            logging.info(f"Subscribed to {self.command_topic} with QoS {self.qos}.")
        else:
            logging.error(f"Failed to connect to MQTT broker: {mqtt.connack_string(rc)}")

    def _on_disconnect(self, client, userdata, flags, reasoncode, properties=None):
        if isinstance(reasoncode, int): # For older paho-mqtt or v1 style rc
            logging.warning(f"Disconnected from MQTT broker: {mqtt.connack_string(reasoncode)}. Will attempt to reconnect.")
        else: # For paho-mqtt v2 ReasonCode object
            logging.warning(f"Disconnected from MQTT broker: {reasoncode}. Will attempt to reconnect.")
        # Reconnection will be handled by the run loop

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage):
        try:
            logging.info(f"Received MQTT message on topic '{msg.topic}': {msg.payload!r}")
            if msg.topic == self.command_topic:
                if msg.payload and len(msg.payload) > 0:
                    # Scale expects single byte commands
                    command_byte = msg.payload[0:1] # Take the first byte
                    self.mqtt_to_serial_queue.put(command_byte)
                    logging.info(f"Command '{command_byte!r}' put to mqtt_to_serial_queue.")
                else:
                    logging.warning("Received empty payload on command topic.")
            else:
                logging.warning(f"Received message on unexpected topic: {msg.topic}")
        except Exception as e:
            logging.error(f"Error processing MQTT message: {e}")

    def _on_publish(self, client, userdata, mid):
        logging.debug(f"MQTT message published successfully (MID: {mid}).")

    def _setup_client(self):
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
            self.client.username_pw_set(self.username, self.password)
            if self.use_tls:
                logging.info("Configuring MQTT client with TLS.")
                self.client.tls_set(
                    # ca_certs=None, # Not needed if server cert is from public CA
                    # certfile=None, # Client cert not required
                    # keyfile=None,  # Client key not required
                    cert_reqs=ssl.CERT_REQUIRED, # Validate server certificate
                    tls_version=ssl.PROTOCOL_TLS_CLIENT,
                )
                # For TLSv1.2 and TLSv1.3, PROTOCOL_TLS_CLIENT should pick the highest.
            else:
                logging.info("Configuring MQTT client without TLS.")

            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_publish = self._on_publish
            return True
        except Exception as e:
            logging.error(f"Error setting up MQTT client: {e}")
            self.client = None
            return False

    def run(self):
        self.running = True
        logging.info("ScaleMqttHandler thread started.")

        if not self._setup_client() or not self.client:
            logging.error("MQTT client setup failed. Thread cannot start.")
            self.running = False # Stop the thread if setup fails
            return

        while self.running:
            if not self.client.is_connected():
                try:
                    logging.info(f"Attempting to connect to MQTT broker {self.broker_host}:{self.port}...")
                    self.connection_rc = -1 # Reset before connect attempt
                    self.client.connect(self.broker_host, self.port, self.keepalive)
                    self.client.loop_start() # Start network loop in background thread
                    # Wait for connection result via _on_connect callback
                    connect_timeout = time.time() + 10 # 10 seconds timeout for connection
                    while self.connection_rc == -1 and time.time() < connect_timeout and self.running:
                        time.sleep(0.1)

                    if self.connection_rc != 0 and self.running: # Check self.running again in case stop was called
                        logging.error(f"MQTT connection failed after attempt. Will retry in {self.reconnect_delay}s.")
                        self.client.loop_stop() # Stop loop if connect failed
                        time.sleep(self.reconnect_delay)
                        continue # Retry connection
                    elif not self.running: # stop() was called during connection attempt
                        break

                except ConnectionRefusedError:
                    logging.error(f"MQTT ConnectionRefusedError. Broker may be down or unreachable. Retrying in {self.reconnect_delay}s.")
                    time.sleep(self.reconnect_delay)
                    continue
                except Exception as e:
                    logging.error(f"Error connecting to MQTT broker: {e}. Retrying in {self.reconnect_delay}s.")
                    if self.client.is_connected(): # Should not happen if connect failed, but good practice
                        self.client.loop_stop()
                    time.sleep(self.reconnect_delay)
                    continue

            # If connected, process outgoing messages
            if self.client.is_connected():
                try:
                    if not self.serial_to_mqtt_queue.empty():
                        message_str: str = self.serial_to_mqtt_queue.get()
                        payload = message_str.encode('utf-8')
                        result = self.client.publish(self.data_topic, payload, qos=self.qos)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            logging.info(f"Published to '{self.data_topic}': {message_str} (MID: {result.mid})")
                        else:
                            logging.error(f"Failed to publish message: {mqtt.error_string(result.rc)}. Re-queuing.")
                            # Basic re-queue, consider more robust dead-letter or retry limit
                            self.serial_to_mqtt_queue.put(message_str)
                            # If publish fails consistently, it might indicate a deeper issue.
                            # For QoS 1 & 2, paho handles retries if broker ACKs are not received.
                            # This error here is more about initial send failure.
                        self.serial_to_mqtt_queue.task_done()
                except Exception as e:
                    logging.error(f"Error publishing MQTT message: {e}")
                    # Potentially re-queue or handle error

            time.sleep(0.01)  # Small delay

        # Cleanup when loop exits
        if self.client:
            if self.client.is_connected():
                logging.info("Disconnecting MQTT client...")
                self.client.loop_stop() # Stop the network loop
                self.client.disconnect()
            else: # If loop_stop was called due to connection failure, ensure disconnect is attempted
                self.client.loop_stop(force=True) # Ensure loop is stopped
        logging.info("ScaleMqttHandler thread stopped.")

    def stop(self):
        self.running = False
        logging.info("Stopping ScaleMqttHandler thread...")
        # The join() in main will wait for the run loop to exit
