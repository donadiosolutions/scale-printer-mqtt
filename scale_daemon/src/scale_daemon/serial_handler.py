import logging
import threading
import time
import serial # type: ignore
import os

class ScaleSerialHandler(threading.Thread):
    def __init__(self, device_path, baudrate, timeout, serial_to_mqtt_queue, mqtt_to_serial_queue):
        super().__init__(name="ScaleSerialHandlerThread")
        self.device_path = device_path
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_to_mqtt_queue = serial_to_mqtt_queue
        self.mqtt_to_serial_queue = mqtt_to_serial_queue
        self.running = False
        self.ser: serial.Serial | None = None
        self.reconnect_delay = 5 # seconds
        self.mock_mode = os.getenv("MOCK_SERIAL_DEVICES") == "true"

        if self.mock_mode:
            logging.info(
                f"ScaleSerialHandler initialized in MOCK MODE for {self.device_path}."
            )
        else:
            logging.info(
                f"ScaleSerialHandler initialized for {self.device_path} at {self.baudrate} baud."
            )

    def _connect_serial(self):
        """Attempts to connect to the serial port or simulates connection in mock mode."""
        if self.mock_mode:
            logging.info(f"MOCK MODE: Simulating successful connection to {self.device_path}.")
            return True

        if not os.path.exists(self.device_path):
            logging.warning(f"Serial device {self.device_path} not found. Will retry in {self.reconnect_delay}s.")
            return False
        try:
            self.ser = serial.Serial(
                self.device_path,
                self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            logging.info(f"Successfully connected to serial port {self.device_path}.")
            return True
        except serial.SerialException as e:
            logging.error(f"Failed to connect to {self.device_path}: {e}. Will retry.")
            self.ser = None
            return False

    def _disconnect_serial(self):
        """Disconnects the serial port if connected or simulates in mock mode."""
        if self.mock_mode:
            logging.info(f"MOCK MODE: Simulating disconnection from {self.device_path}.")
            self.ser = None # Ensure it's None
            return

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                logging.info(f"Closed serial port {self.device_path}.")
            except Exception as e:
                logging.error(f"Error closing serial port {self.device_path}: {e}")
        self.ser = None

    def run(self):
        self.running = True
        logging.info("ScaleSerialHandler thread started.")
        buffer = bytearray() # Only used in non-mock mode

        while self.running:
            if self.mock_mode:
                # --- MOCK MODE ---
                if not self.mqtt_to_serial_queue.empty():
                    command: bytes = self.mqtt_to_serial_queue.get()
                    logging.info(f"MOCK MODE: Received command for scale: {command!r} (not sent to device)")
                    self.mqtt_to_serial_queue.task_done()

                # Simulate work or just pause to prevent busy loop
                # If mock data needs to be sent to MQTT:
                # self.serial_to_mqtt_queue.put("MOCK_SCALE_DATA")
                time.sleep(0.1)
                continue # Skip real serial logic

            # --- NON-MOCK MODE (original logic mostly from here) ---
            if self.ser is None or not self.ser.is_open:
                self._disconnect_serial()
                if not self._connect_serial():
                    time.sleep(self.reconnect_delay)
                    continue

            try:
                # 1. Read commands from MQTT queue and write to scale
                if not self.mqtt_to_serial_queue.empty():
                    command: bytes = self.mqtt_to_serial_queue.get()
                    # Ensure self.ser is valid before using (it should be if not in mock_mode and connected)
                    if self.ser and self.ser.is_open:
                        logging.info(f"Sending command to scale: {command!r}")
                        self.ser.write(command)
                    self.mqtt_to_serial_queue.task_done()

                # 2. Read data from scale
                # Ensure self.ser is valid before using
                if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                    byte = self.ser.read(1)
                    if byte:
                        if byte == b'\n': # LF character
                            if buffer:
                                message_str = buffer.decode('ascii', errors='replace').strip()
                                if message_str: # Ensure not empty after strip
                                    logging.info(f"Read from scale: {message_str}")
                                    self.serial_to_mqtt_queue.put(message_str)
                                buffer.clear()
                        else:
                            buffer.append(byte[0])
                    else: # Read timed out
                        pass
                elif self.ser and not self.ser.is_open: # Port closed unexpectedly
                    logging.warning(f"Serial port {self.device_path} closed unexpectedly. Attempting to reconnect.")
                    self._disconnect_serial() # Clean up

            except serial.SerialException as e:
                logging.error(f"SerialException in ScaleSerialHandler: {e}. Attempting to reconnect.")
                self._disconnect_serial()
                time.sleep(self.reconnect_delay) # Wait before trying to reconnect
            except OSError as e: # This can happen if the device is unplugged
                 logging.error(f"OSError (device likely disconnected): {e}. Attempting to reconnect.")
                 self._disconnect_serial()
                 time.sleep(self.reconnect_delay)
            except Exception as e:
                logging.error(f"Unexpected error in ScaleSerialHandler: {e}")
                # Decide if a reconnect is appropriate or if it's a fatal error for the thread
                time.sleep(1) # Prevent rapid looping on unexpected errors

            time.sleep(0.01)  # Small delay to prevent busy-looping

        self._disconnect_serial()
        logging.info("ScaleSerialHandler thread stopped.")

    def stop(self):
        self.running = False
        logging.info("Stopping ScaleSerialHandler thread...")
        # The join() in main will wait for the run loop to exit
