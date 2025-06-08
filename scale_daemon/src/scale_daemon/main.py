import logging
import queue
import time
import os
import sys
from dotenv import load_dotenv

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


def stop_handlers_and_exit(exit_code, serial_h, mqtt_h):
    """Stop handlers and exit."""
    logging.info(
        f"Integration test: Stopping threads and exiting with code {exit_code}..."
    )
    if mqtt_h and mqtt_h.is_alive():
        mqtt_h.stop()
        mqtt_h.join(timeout=5)  # Add timeout to join
    if serial_h and serial_h.is_alive():
        serial_h.stop()
        serial_h.join(timeout=5)  # Add timeout to join
    logging.info(f"Integration test: Exiting with {exit_code}.")
    sys.exit(exit_code)


def run_integration_test(mqtt_handler, serial_handler, serial_to_mqtt_q):
    """Runs a defined integration test sequence."""
    logging.info("Integration test: Starting test sequence...")

    serial_handler.start()
    mqtt_handler.start()

    logging.info("Integration test: Waiting for MQTT connection...")
    connect_wait_start = time.time()
    mqtt_connection_timeout = 20  # seconds
    while not mqtt_handler.is_connected_for_test():
        if time.time() - connect_wait_start > mqtt_connection_timeout:
            logging.error("Integration test: MQTT connection timed out.")
            stop_handlers_and_exit(1, serial_handler, mqtt_handler)
            return
        time.sleep(0.2)
    logging.info("Integration test: MQTT connected successfully.")

    test_message = (
        '{"type": "integration_test", "value": "ping_from_scale_daemon_test"}'
    )
    logging.info(f"Integration test: Queuing test message for MQTT: {test_message}")
    serial_to_mqtt_q.put(test_message)

    logging.info("Integration test: Soak time (10s)...")
    time.sleep(10)

    logging.info("Integration test: Sequence completed successfully.")
    stop_handlers_and_exit(0, serial_handler, mqtt_handler)


def main():
    """Main function to start the daemon."""
    load_dotenv()
    setup_logging()
    logging.info("Starting Scale Daemon...")

    is_integration_test_mode = os.getenv("RUN_INTEGRATION_TEST") == "true"

    # Get MQTT config from environment variables or use defaults
    broker_host = os.environ.get("MQTT_BROKER_HOST", MQTT_BROKER_HOST_DEFAULT)
    broker_port = int(os.environ.get("MQTT_BROKER_PORT", MQTT_BROKER_PORT_DEFAULT))
    username = os.environ.get("MQTT_USERNAME", MQTT_USERNAME_DEFAULT)
    password = os.environ.get("MQTT_PASSWORD", MQTT_PASSWORD_DEFAULT)
    client_id = os.environ.get(
        "MQTT_CLIENT_ID", MQTT_CLIENT_ID_DEFAULT
    )  # Though client_id is often fixed per device type
    data_topic = os.environ.get("MQTT_DATA_TOPIC", MQTT_DATA_TOPIC_DEFAULT)
    command_topic = os.environ.get("MQTT_COMMAND_TOPIC", MQTT_COMMAND_TOPIC_DEFAULT)
    qos = int(os.environ.get("MQTT_QOS", MQTT_QOS_DEFAULT))
    keepalive = int(os.environ.get("MQTT_KEEPALIVE", MQTT_KEEPALIVE_DEFAULT))
    use_tls_str = os.environ.get("MQTT_USE_TLS", str(MQTT_USE_TLS_DEFAULT))
    use_tls = use_tls_str.lower() in ("true", "1", "yes")

    logging.info(
        f"MQTT Config: Host={broker_host}, Port={broker_port}, "
        f"User={username}, TLS={use_tls}"
    )
    logging.info(
        f"MQTT Topics: Data={data_topic}, Command={command_topic}, QoS={qos}"
    )

    serial_handler = ScaleSerialHandler(
        SERIAL_DEVICE_PATH,
        SERIAL_BAUDRATE,
        SERIAL_TIMEOUT,
        serial_to_mqtt_queue,
        mqtt_to_serial_queue,
    )
    mqtt_handler = ScaleMqttHandler(
        broker_host,
        broker_port,
        username,
        password,
        client_id,
        data_topic,
        command_topic,
        qos,
        keepalive,
        serial_to_mqtt_queue,
        mqtt_to_serial_queue,
        use_tls=use_tls,
    )

    # serial_handler.start()  # Moved into conditional blocks
    # mqtt_handler.start()  # Moved into conditional blocks

    if is_integration_test_mode:
        try:
            # Handlers are started inside run_integration_test
            run_integration_test(mqtt_handler, serial_handler, serial_to_mqtt_queue)
        except Exception as e:
            logging.error(f"Unhandled exception during integration test: {e}")
            # Ensure handlers are created before trying to stop them if error is early
            stop_handlers_and_exit(2, serial_handler, mqtt_handler)
    else:
        # Original long-running service logic:
        serial_handler.start()
        mqtt_handler.start()
        try:
            while True:
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
