import logging
import threading
import queue
import time
import os

from .serial_handler import ScaleSerialHandler
from .mqtt_handler import ScaleMqttHandler

# --- Constants ---
# Serial Port Configuration
SERIAL_DEVICE_PATH = "/dev/ttyUSB_SCALE"  # As per udev rule
SERIAL_BAUDRATE = 9600
SERIAL_TIMEOUT = 1  # seconds

# MQTT Configuration
MQTT_BROKER_HOST_DEFAULT = "mqtt.example.com"
MQTT_BROKER_PORT_DEFAULT = 8883
MQTT_USERNAME_DEFAULT = "scale_user"
MQTT_PASSWORD_DEFAULT = "scale_password"
MQTT_CLIENT_ID_DEFAULT = "scale_daemon_client"
MQTT_DATA_TOPIC_DEFAULT = "laboratory/scale/data"
MQTT_COMMAND_TOPIC_DEFAULT = "laboratory/scale/command"
MQTT_QOS_DEFAULT = 2
MQTT_KEEPALIVE_DEFAULT = 60  # seconds
MQTT_USE_TLS_DEFAULT = True

# --- Queues ---
# Queue for messages from serial to MQTT
serial_to_mqtt_queue = queue.Queue()
# Queue for commands from MQTT to serial
mqtt_to_serial_queue = queue.Queue()


def setup_logging():
    """Sets up basic logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s",
    )
    logging.info("Logging configured.")


def main():
    """Main function to start the daemon."""
    setup_logging()
    logging.info("Starting Scale Daemon...")

    # Get MQTT config from environment variables or use defaults
    broker_host = os.environ.get("MQTT_BROKER_HOST", MQTT_BROKER_HOST_DEFAULT)
    broker_port = int(os.environ.get("MQTT_BROKER_PORT", MQTT_BROKER_PORT_DEFAULT))
    username = os.environ.get("MQTT_USERNAME", MQTT_USERNAME_DEFAULT)
    password = os.environ.get("MQTT_PASSWORD", MQTT_PASSWORD_DEFAULT)
    client_id = os.environ.get("MQTT_CLIENT_ID", MQTT_CLIENT_ID_DEFAULT) # Though client_id is often fixed per device type
    data_topic = os.environ.get("MQTT_DATA_TOPIC", MQTT_DATA_TOPIC_DEFAULT)
    command_topic = os.environ.get("MQTT_COMMAND_TOPIC", MQTT_COMMAND_TOPIC_DEFAULT)
    qos = int(os.environ.get("MQTT_QOS", MQTT_QOS_DEFAULT))
    keepalive = int(os.environ.get("MQTT_KEEPALIVE", MQTT_KEEPALIVE_DEFAULT))
    use_tls_str = os.environ.get("MQTT_USE_TLS", str(MQTT_USE_TLS_DEFAULT))
    use_tls = use_tls_str.lower() in ('true', '1', 'yes')

    logging.info(f"MQTT Config: Host={broker_host}, Port={broker_port}, User={username}, TLS={use_tls}")
    logging.info(f"MQTT Topics: Data={data_topic}, Command={command_topic}, QoS={qos}")


    serial_handler = ScaleSerialHandler(
        SERIAL_DEVICE_PATH, SERIAL_BAUDRATE, SERIAL_TIMEOUT,
        serial_to_mqtt_queue, mqtt_to_serial_queue
    )
    mqtt_handler = ScaleMqttHandler(
        broker_host, broker_port, username, password,
        client_id, data_topic, command_topic, qos,
        keepalive, serial_to_mqtt_queue, mqtt_to_serial_queue, use_tls=use_tls
    )

    serial_handler.start()
    mqtt_handler.start()

    try:
        while True:
            # Keep main thread alive, or implement other logic
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received. Shutting down...")
    finally:
        logging.info("Stopping threads...")
        if mqtt_handler.is_alive():
            mqtt_handler.stop()
            mqtt_handler.join()
        if serial_handler.is_alive():
            serial_handler.stop()
            serial_handler.join()
        logging.info("Scale Daemon shut down.")


if __name__ == "__main__":
    main()
