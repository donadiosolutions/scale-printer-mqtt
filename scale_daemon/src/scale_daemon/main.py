import logging
import threading
import queue
import time

from .serial_handler import ScaleSerialHandler
from .mqtt_handler import ScaleMqttHandler

# --- Constants ---
# Serial Port Configuration
SERIAL_DEVICE_PATH = "/dev/ttyUSB_SCALE"  # As per udev rule
SERIAL_BAUDRATE = 9600
SERIAL_TIMEOUT = 1  # seconds

# MQTT Configuration
MQTT_BROKER_HOST = "mqtt.example.com"
MQTT_BROKER_PORT = 8883
MQTT_USERNAME = "scale_user"
MQTT_PASSWORD = "scale_password"
MQTT_CLIENT_ID = "scale_daemon_client"
MQTT_DATA_TOPIC = "laboratory/scale/data"
MQTT_COMMAND_TOPIC = "laboratory/scale/command"
MQTT_QOS = 2
MQTT_KEEPALIVE = 60  # seconds

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

    serial_handler = ScaleSerialHandler(
        SERIAL_DEVICE_PATH, SERIAL_BAUDRATE, SERIAL_TIMEOUT,
        serial_to_mqtt_queue, mqtt_to_serial_queue
    )
    mqtt_handler = ScaleMqttHandler(
        MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_USERNAME, MQTT_PASSWORD,
        MQTT_CLIENT_ID, MQTT_DATA_TOPIC, MQTT_COMMAND_TOPIC, MQTT_QOS,
        MQTT_KEEPALIVE, serial_to_mqtt_queue, mqtt_to_serial_queue
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
