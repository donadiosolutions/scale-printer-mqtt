# Printer Daemon

This application subscribes to an MQTTv5 topic and prints any received messages to a serial-connected ESC/POS printer.

## Features

- **MQTTv5 Support**: Utilizes MQTT version 5 with QoS 2 for reliable messaging.
- **TLS and Authentication**: Connects to the MQTT broker using TLSv1.2/1.3 and username/password authentication.
- **Resilient Connections**: Automatically retries and reconnects to both the serial port and the MQTT broker in case of failures.
- **Environment-based Configuration**: All settings are managed through environment variables, with sensible defaults.

## Prerequisites

- Python 3.12+
- Poetry
- A serial-connected ESC/POS printer or an emulated device.
- Access to an MQTTv5 broker.

## Installation

1.  **Clone the repository** (or receive this directory).
2.  **Navigate to the `printer_daemon` directory**:
    ```bash
    cd printer_daemon
    ```
3.  **Install dependencies** using Poetry:
    ```bash
    poetry install
    ```

## Configuration

The daemon is configured entirely through environment variables. You can create a `.env` file in this directory to manage your settings.

| Environment Variable      | Description                               | Default Value                  |
| ------------------------- | ----------------------------------------- | ------------------------------ |
| `SERIAL_DEVICE_PATH`      | Path to the serial device for the printer.| `/dev/ttyUSB_PRINTER`          |
| `SERIAL_BAUDRATE`         | Baud rate for the serial connection.      | `115200`                       |
| `MQTT_BROKER_HOST`        | MQTT broker hostname or IP address.       | `mqtt.example.com`             |
| `MQTT_BROKER_PORT`        | MQTT broker port.                         | `8883`                         |
| `MQTT_USERNAME`           | Username for MQTT authentication.         | `printer_user`                 |
| `MQTT_PASSWORD`           | Password for MQTT authentication.         | `printer_password`             |
| `MQTT_USE_TLS`            | Set to `true` or `false` to enable/disable TLS. | `true`                         |
| `MQTT_PRINT_TOPIC`        | Topic to subscribe to for printing messages. | `laboratory/scale/data`        |
| `MOCK_SERIAL_DEVICES`     | Set to `true` to use a mock serial device for testing without hardware. | `false` |

**Example `.env` file:**

```dotenv
# .env
SERIAL_DEVICE_PATH=/dev/ttyS1
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=my_user
MQTT_PASSWORD=my_secret_password
MQTT_USE_TLS=false
```

## Running the Daemon

Once configured, you can run the daemon using the Poetry script entry point:

```bash
poetry run printer-daemon
```

The application will start, connect to the serial device and the MQTT broker, and begin listening for messages to print.

## Running Unit Tests

To run the suite of unit tests, execute the following command:

```bash
poetry run pytest
