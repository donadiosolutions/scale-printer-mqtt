# AI Prompt
This code was generated automatically with Gemini Pro 2.5 with the prompt below. Took about 10min and USD$4.75.

---

# Scale and Printer MQTT Adapter
## Objective
A laboratory scale needs to be connected to a line printer through the network
using MQTTv5. Your job is to write the two daemons that will facilitate this on
each side. You will write them in Python 3.12+ and handle both the virtual
environment and dependencies with Poetry.

## Devices
### Hosts
* Linux host computers on each side with proper Python support will run the
  daemons.
* The hosts are not CPU nor memory constrained.
* Both hosts have Podman available.
* Full time network connectivity should not be relied upon: reconnection and
  retry mechanisms should be implemented.
* Host devices might reboot. The application will be launched again
  automatically, be should be always ready to recover.
* The serial connections are actually emulated via USB. The devices themselves
  might get disconnected temporarily (detectable by the file descriptor being
  closed and the disapearance of the character file in /dev). The daemons should
  restart the serial connection on their own when the device appear again.
* Implement the device paths as constants defined in the code entrypoint. The
  node name invariance is already guaranted by a custom udev rule.

### Printer
* The printer is of the ESC/POS type and only receives data and commands as
  simple ASCII text.
* It handles word-wrapping by itself, but a LF character should be added to the
  stream at the end of every MQTT message.
* No special processing should be done to the ESC/POS signaling, just copied
  over as received.
* It listens on the serial port at a 115200,8,N,1 baud configuration.

### Scale
* The scale listens for single byte commands and writes data as ASCII text
  ending each message with a LF character.
* It is connected on the serial port at a 9600,8,N,1 baud configuration.
* The generated text is already ready for printing without further processing
  except for breaking the stream into MQTT messages every time a LF character is
  received (the LF character shouldn't be sent in the MQTT message).
* It should listen for single ASCII characters commands in a separate MQTT
  topic. The byte should be copied to the scale device as it is received.

### Broker
* The MQTTv5 broker already exists and shouldn't be implemented.
* It accepts TLSv1.2 and TLSv1.3 connections at TCP port 8883.
* Client TLS certificates are not required.
* Client authentication happens with basic user and password.
* Use topic names and credentials from constants in the code entrypoint.

## Code
* Python 3.12+ code should be written.
* The code should follow best practices of object-oriented programming.
* PEP8 formatting style should be followed.
* The daemons should be implemented with at least two threads: one handling the
  serial communication, the other handling the MQTT connection.
* The threads themselves should communicate between each other with in-memory
  thread-safe FIFO queues. No disk persistence is needed.
* MQTTv5 messages should be used with QoS 2.
* Unit tests should be implemented for every class and method.
* Parameters like host, port, device path, topic names, users, passwords and
  similar things should be defined in the code entrypoint as simple constants
  for now.
* All the diagnostic logging should be written into stdout or stderr.
* Minimize the use of external libraries when possible, but the use of mature
  libraries either from PyPi or from the official Python bundle to handle the
  following needs is encouraged:
  * MQTTv5 protocol support (maybe paho-mqtt)
  * TLS support (if not bundled in the MQTT library)
  * Threading
  * In-memory queues
  * Logging

## Containers
* Write two multistage Containerfiles to install, build (if needed), test and
  run the code. Aim for a small footprint final container.
* Support both x86_64 and arm64 in a multi-arch manifest.
* Run the test suite inside the containers.
* Use Alpine as the base for the containers with the code you created.
* Write the default set of opencontainer.org labels in the images.

### Kubernetes
* Write a Helmchart to deploy this solution in Kubernetes taking into account
  that the Deployments should have a provision for node-affinity and usage of
  host devices.
* Implement liveness and readiness checks.

## CI
* Write a docker-compose file for integration testing, adding a Mosquitto
  container as the broker.
* Write a Github Action to build the images and run the unit and integration
  testing.
* Write a Github Action to publish the images into ghcr.io when there's a new
  release created.
* Write dependabot rules to automatically open PRs whenever there's a
  vulnerability disclosed and an available patch for any dependency.

## Misc
* Write a README.md file with the project presentation and a quickstart guide.
* Write a LICENSE file with the GPLv2 license.
