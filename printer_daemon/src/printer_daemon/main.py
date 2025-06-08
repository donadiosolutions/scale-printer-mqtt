import logging
import queue
import time
import os
from dotenv import load_dotenv

from .serial_handler import PrinterSerialHandler
from .mqtt_handler import PrinterMqttHandler

# --- Constants ---
# Serial Port Configuration
SERIAL_DEVICE_PATH = "/dev/ttyUSB_PRINTER"  # As per udev rule
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT = 1  # seconds

# MQTT Configuration
MQTT_BROKER_HOST_DEFAULT = "mqtt.example.com"
MQTT_BROKER_PORT_DEFAULT = 8883
MQTT_USERNAME_DEFAULT = "printer_user"
MQTT_PASSWORD_DEFAULT = "printer_password"
MQTT_CLIENT_ID_DEFAULT = "printer_daemon_client"
# Subscribes to the scale's data topic
MQTT_PRINT_TOPIC_DEFAULT = "laboratory/scale/data"
MQTT_QOS_DEFAULT = 2
MQTT_KEEPALIVE_DEFAULT = 60  # seconds
MQTT_USE_TLS_DEFAULT = True

# --- Queues ---
# Queue for messages from MQTT to serial (for printing)
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
    load_dotenv()
    setup_logging()
    logging.info("Starting Printer Daemon...")

    # Get MQTT config from environment variables or use defaults
    broker_host = os.environ.get("MQTT_BROKER_HOST", MQTT_BROKER_HOST_DEFAULT)
    broker_port = int(os.environ.get("MQTT_BROKER_PORT", MQTT_BROKER_PORT_DEFAULT))
    username = os.environ.get("MQTT_USERNAME", MQTT_USERNAME_DEFAULT)
    password = os.environ.get("MQTT_PASSWORD", MQTT_PASSWORD_DEFAULT)
    client_id = os.environ.get("MQTT_CLIENT_ID", MQTT_CLIENT_ID_DEFAULT)
    print_topic = os.environ.get("MQTT_PRINT_TOPIC", MQTT_PRINT_TOPIC_DEFAULT)
    qos = int(os.environ.get("MQTT_QOS", MQTT_QOS_DEFAULT))
    keepalive = int(os.environ.get("MQTT_KEEPALIVE", MQTT_KEEPALIVE_DEFAULT))
    use_tls_str = os.environ.get("MQTT_USE_TLS", str(MQTT_USE_TLS_DEFAULT))
    use_tls = use_tls_str.lower() in ("true", "1", "yes")

    logging.info(
        f"MQTT Config: Host={broker_host}, Port={broker_port}, "
        f"User={username}, TLS={use_tls}"
    )
    logging.info(f"MQTT Topics: PrintTopic={print_topic}, QoS={qos}")

    serial_handler = PrinterSerialHandler(
        SERIAL_DEVICE_PATH,
        SERIAL_BAUDRATE,
        SERIAL_TIMEOUT,
        mqtt_to_serial_queue,
    )
    mqtt_handler = PrinterMqttHandler(
        broker_host,
        broker_port,
        username,
        password,
        client_id,
        print_topic,
        qos,
        keepalive,
        mqtt_to_serial_queue,
        use_tls=use_tls,
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
        logging.info("Printer Daemon shut down.")


if __name__ == "__main__":
    main()
