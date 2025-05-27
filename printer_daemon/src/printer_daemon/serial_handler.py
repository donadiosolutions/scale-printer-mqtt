import logging
import threading
import time
import serial # type: ignore
import os
import queue

class PrinterSerialHandler(threading.Thread):
    def __init__(self, device_path, baudrate, timeout, mqtt_to_serial_queue: queue.Queue):
        super().__init__(name="PrinterSerialHandlerThread")
        self.device_path = device_path
        self.baudrate = baudrate
        self.timeout = timeout # Write timeout
        self.mqtt_to_serial_queue = mqtt_to_serial_queue # Messages from MQTT to print
        self.running = False
        self.ser: serial.Serial | None = None
        self.reconnect_delay = 5  # seconds
        logging.info(
            f"PrinterSerialHandler initialized for {self.device_path} at {self.baudrate} baud."
        )

    def _connect_serial(self):
        """Attempts to connect to the serial port."""
        if not os.path.exists(self.device_path):
            logging.warning(f"Serial device {self.device_path} not found. Will retry in {self.reconnect_delay}s.")
            return False
        try:
            self.ser = serial.Serial(
                self.device_path,
                self.baudrate,
                # write_timeout=self.timeout, # pyserial uses timeout for read, write_timeout for write
                timeout=self.timeout, # General timeout for operations
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            # For some printers, DTR/RTS might need to be managed if flow control is an issue
            # self.ser.dtr = True
            # self.ser.rts = True
            logging.info(f"Successfully connected to printer serial port {self.device_path}.")
            return True
        except serial.SerialException as e:
            logging.error(f"Failed to connect to printer {self.device_path}: {e}. Will retry.")
            self.ser = None
            return False
        except Exception as e: # Catch other potential errors like permission denied
            logging.error(f"An unexpected error occurred connecting to printer {self.device_path}: {e}. Will retry.")
            self.ser = None
            return False


    def _disconnect_serial(self):
        """Disconnects the serial port if connected."""
        if self.ser and self.ser.is_open:
            try:
                # Ensure output buffer is flushed before closing if necessary, though
                # for many printers, just closing is fine.
                # self.ser.flush()
                self.ser.close()
                logging.info(f"Closed printer serial port {self.device_path}.")
            except Exception as e:
                logging.error(f"Error closing printer serial port {self.device_path}: {e}")
        self.ser = None

    def run(self):
        self.running = True
        logging.info("PrinterSerialHandler thread started.")

        while self.running:
            if self.ser is None or not self.ser.is_open:
                self._disconnect_serial()
                if not self._connect_serial():
                    time.sleep(self.reconnect_delay)
                    continue

            try:
                if not self.mqtt_to_serial_queue.empty():
                    message_to_print: str = self.mqtt_to_serial_queue.get()
                    if self.ser and self.ser.is_open:
                        try:
                            # Ensure message is bytes and add LF
                            payload = message_to_print.encode('ascii', errors='replace') + b'\n'
                            logging.info(f"Printing to {self.device_path}: {payload!r}")
                            self.ser.write(payload)
                            # self.ser.flush() # Ensure data is sent, might be needed for some devices/drivers
                            self.mqtt_to_serial_queue.task_done()
                        except serial.SerialTimeoutException:
                            logging.error(f"Write timeout to {self.device_path}. Re-queuing message.")
                            self.mqtt_to_serial_queue.put(message_to_print) # Re-queue
                            self._disconnect_serial() # Assume port issue, force reconnect
                        except serial.SerialException as se_write:
                            logging.error(f"SerialException during write to {self.device_path}: {se_write}. Re-queuing.")
                            self.mqtt_to_serial_queue.put(message_to_print) # Re-queue
                            self._disconnect_serial() # Assume port issue
                        except OSError as ose_write:
                            logging.error(f"OSError during write to {self.device_path} (device likely disconnected): {ose_write}. Re-queuing.")
                            self.mqtt_to_serial_queue.put(message_to_print) # Re-queue
                            self._disconnect_serial() # Assume port issue
                    else:
                        # Port not open, re-queue message
                        logging.warning("Serial port not open while trying to print. Re-queuing message.")
                        self.mqtt_to_serial_queue.put(message_to_print)
                        self._disconnect_serial() # Force reconnect attempt
                else:
                    # No message in queue, sleep briefly
                    time.sleep(0.05) # Check queue periodically

            except serial.SerialException as e: # Catch exceptions during ser.is_open or other ser ops
                logging.error(f"SerialException in PrinterSerialHandler: {e}. Attempting to reconnect.")
                self._disconnect_serial()
                time.sleep(self.reconnect_delay)
            except OSError as e:
                 logging.error(f"OSError in PrinterSerialHandler (device likely disconnected): {e}. Attempting to reconnect.")
                 self._disconnect_serial()
                 time.sleep(self.reconnect_delay)
            except Exception as e:
                logging.error(f"Unexpected error in PrinterSerialHandler: {e}")
                time.sleep(1) # Prevent rapid looping

        self._disconnect_serial()
        logging.info("PrinterSerialHandler thread stopped.")

    def stop(self):
        self.running = False
        logging.info("Stopping PrinterSerialHandler thread...")
