# Scale and Printer MQTT Adapter

This project provides two Python daemons to connect a laboratory scale and an ESC/POS line printer over the network using MQTTv5.

-   **Scale Daemon**: Reads data from a serial-connected scale, processes it, and publishes messages to an MQTT topic. It also listens on another MQTT topic for single-byte commands to send to the scale.
-   **Printer Daemon**: Subscribes to an MQTT topic (where the scale daemon publishes data) and prints received messages to a serial-connected ESC/POS printer.

## Features

*   **Python 3.12+**: Modern Python implementation.
*   **Poetry**: Dependency management and packaging.
*   **MQTTv5**: Utilizes MQTT version 5 with QoS 2 for reliable messaging.
*   **TLS Support**: Connects to the MQTT broker using TLSv1.2/1.3 with basic username/password authentication.
*   **Resilient Connections**: Implements retry and reconnection mechanisms for both serial and MQTT connections.
*   **Threaded Architecture**: Each daemon uses separate threads for serial communication and MQTT handling, with thread-safe queues for inter-thread communication.
*   **Containerized**: Includes `Containerfile`s for building multi-arch (x86_64, arm64) Docker/Podman images using Alpine Linux. Unit tests are run during the image build process.
*   **Kubernetes Ready**: A Helm chart is provided for deployment in a Kubernetes environment, including considerations for node affinity and host device access.
*   **CI/CD**: GitHub Actions workflows for:
    *   Building images, running unit tests, and basic integration tests on push/pull_request.
    *   Publishing images to GHCR on new releases.

## Project Structure

```
scale-printer-mqtt/
├── .github/
│   ├── workflows/            # GitHub Actions CI/CD
│   │   ├── build-test.yml
│   │   └── publish.yml
│   └── dependabot.yml        # Dependabot configuration (to be added)
├── helm_chart/
│   └── scale-printer-mqtt/   # Helm chart for Kubernetes deployment
├── mosquitto/
│   └── config/               # Configuration for local Mosquitto (integration tests)
├── printer_daemon/           # Source code and tests for the printer daemon
│   ├── src/printer_daemon/
│   ├── tests/
│   ├── Containerfile
│   └── pyproject.toml
├── scale_daemon/             # Source code and tests for the scale daemon
│   ├── src/scale_daemon/
│   ├── tests/
│   ├── Containerfile
│   └── pyproject.toml
├── docker-compose.yml        # For local integration testing
├── LICENSE                   # Project license (to be added)
└── README.md                 # This file
```

## Prerequisites

*   Python 3.12+
*   Poetry
*   Docker or Podman (for building and running containers)
*   Access to an MQTTv5 broker (or use the provided `docker-compose.yml` for a local one)
*   Serial devices (scale and printer) or emulated equivalents. Udev rules should be configured on host systems to provide stable device paths (e.g., `/dev/ttyUSB_SCALE`, `/dev/ttyUSB_PRINTER`).

## Quickstart Guide

### 1. Configure Daemons

Constants for device paths, MQTT broker details (host, port, username, password), and topic names are defined at the beginning of:
*   `scale_daemon/src/scale_daemon/main.py`
*   `printer_daemon/src/printer_daemon/main.py`

Update these constants to match your environment. For the MQTT broker, ensure it's accessible and configured for TLS with basic authentication.

### 2. Install Dependencies (Local Development)

Navigate to each daemon's directory and install dependencies using Poetry:

```bash
cd scale_daemon
poetry install
cd ../printer_daemon
poetry install
cd ..
```

### 3. Running Daemons Locally (for development/testing without containers)

You can run each daemon directly using Poetry:

```bash
# Terminal 1: Scale Daemon
cd scale_daemon
poetry run python src/scale_daemon/main.py

# Terminal 2: Printer Daemon
cd printer_daemon
poetry run python src/printer_daemon/main.py
```

### 4. Building and Running with Docker/Podman

Each daemon has a `Containerfile` for building an image.

```bash
# Build scale daemon image
podman build -t scale-daemon-app -f scale_daemon/Containerfile ./scale_daemon

# Build printer daemon image
podman build -t printer-daemon-app -f printer_daemon/Containerfile ./printer_daemon
```

To run the containers, you'll need to map the serial devices from your host and potentially set environment variables if you adapt the code to use them for configuration (currently uses hardcoded constants).

Example (Podman, assuming devices `/dev/ttyUSB_SCALE` and `/dev/ttyUSB_PRINTER` exist on host):
```bash
# Run scale daemon container
podman run -d --rm --name scale_daemon_instance --device /dev/ttyUSB_SCALE:/dev/ttyUSB_SCALE:rwm scale-daemon-app

# Run printer daemon container
podman run -d --rm --name printer_daemon_instance --device /dev/ttyUSB_PRINTER:/dev/ttyUSB_PRINTER:rwm printer-daemon-app
```
*Note: `--device` mapping and permissions might require running Podman/Docker with sufficient privileges or specific SELinux/AppArmor configurations.*

### 5. Integration Testing with Docker Compose

A `docker-compose.yml` file is provided to set up a local Mosquitto MQTT broker and run both daemons for integration testing.

**Important:**
1.  The Mosquitto configuration in `mosquitto/config/mosquitto.conf` uses a password file. You need to generate `mosquitto/config/mosquitto_passwd` with appropriate credentials for `scale_user` and `printer_user` that match the constants in the Python code.
    Example commands (run from the project root, requires `mosquitto-clients` package for `mosquitto_passwd`):
    ```bash
    mkdir -p mosquitto/config # if not exists
    mosquitto_passwd -c -b mosquitto/config/mosquitto_passwd scale_user scale_password
    mosquitto_passwd -b mosquitto/config/mosquitto_passwd printer_user printer_password
    ```
    *(Replace `scale_password` and `printer_password` with the actual passwords defined in the Python constants if they differ from these examples).*

2.  For the daemons to connect to this local Docker Compose Mosquitto instance (named `mosquitto` on port `1883`, non-TLS), you would typically need to:
    *   Modify the `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT` constants in the Python `main.py` files of each daemon to point to `mosquitto` and `1883` respectively.
    *   Modify the Python code to disable TLS for this local test connection (e.g., by adding a conditional check or an environment variable).
    *   Alternatively, configure the Mosquitto container in `docker-compose.yml` to use TLS and listen on port 8883, providing necessary certificates.

To run the integration test environment:
```bash
docker-compose up --build
```

### 6. Kubernetes Deployment

A Helm chart is located in `helm_chart/scale-printer-mqtt/`.
Refer to the `values.yaml` and `NOTES.txt` within the chart directory for configuration and deployment instructions. You will need to:
*   Ensure your Kubernetes nodes have the serial devices accessible.
*   Configure `nodeSelector` or `affinity` in `values.yaml` to schedule pods on the correct nodes.
*   Ensure the container images are pushed to a registry accessible by your Kubernetes cluster and update `values.yaml` with the correct image repository and tags.
*   The chart assumes hostPath for device access, which may require specific cluster permissions and security contexts (`privileged: true` might be needed).

## Development

*   **Unit Tests**: Run unit tests from within each daemon's directory using `poetry run pytest`. Tests are also executed during the Docker image build process.
*   **Linting/Formatting**: Black and Flake8 are included as dev dependencies.
    ```bash
    # Inside scale_daemon or printer_daemon directory
    poetry run black src/ tests/
    poetry run flake8 src/ tests/
    ```

## Contributing

Please refer to `CONTRIBUTING.md` (to be created if contributions are expected).

## License

This project is licensed under the GNU General Public License v2.0 - see the `LICENSE` file for details.
