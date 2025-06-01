import unittest
from unittest.mock import patch, MagicMock, call
import queue
import time
import os
import serial # type: ignore # To reference serial.SerialException, serial.SerialTimeoutException

from printer_daemon.serial_handler import PrinterSerialHandler

MOCK_PRINTER_PORT = "/dev/ttyTestPrinter"
MOCK_PRINTER_BAUDRATE = 115200
MOCK_PRINTER_TIMEOUT = 1

class TestPrinterSerialHandler(unittest.TestCase):

    def setUp(self):
        self.mqtt_to_serial_queue = queue.Queue()

        # Get the original class BEFORE it's patched
        self.original_serial_class_ref = serial.Serial

        self.patcher_serial = patch('serial.Serial')
        self.patcher_os_path_exists = patch('os.path.exists')

        self.mock_serial_class = self.patcher_serial.start() # serial.Serial is now a mock
        self.mock_os_path_exists = self.patcher_os_path_exists.start()

        self.mock_os_path_exists.return_value = True # Device exists by default

        # Create an instance mock, specced against the *original* class
        self.mock_serial_instance = MagicMock(spec=self.original_serial_class_ref)
        self.mock_serial_instance.is_open = True
        # Make the class mock return our instance mock
        self.mock_serial_class.return_value = self.mock_serial_instance

        self.handler = PrinterSerialHandler(
            MOCK_PRINTER_PORT, MOCK_PRINTER_BAUDRATE, MOCK_PRINTER_TIMEOUT,
            self.mqtt_to_serial_queue
        )
        self.handler.reconnect_delay = 0.05 # Faster reconnects for tests

    def tearDown(self):
        if self.handler.is_alive():
            self.handler.stop()
            self.handler.join(timeout=1)
        self.patcher_serial.stop()
        self.patcher_os_path_exists.stop()
        # Ensure queue is empty if a test fails to consume
        while not self.mqtt_to_serial_queue.empty():
            try:
                self.mqtt_to_serial_queue.get_nowait()
                self.mqtt_to_serial_queue.task_done()
            except queue.Empty:
                break


    def test_initialization(self):
        self.assertEqual(self.handler.device_path, MOCK_PRINTER_PORT)
        self.assertFalse(self.handler.running)
        self.assertIsNone(self.handler.ser)

    @patch('time.sleep', MagicMock())
    def test_connect_serial_success(self):
        self.assertTrue(self.handler._connect_serial())
        self.mock_serial_class.assert_called_once_with(
            MOCK_PRINTER_PORT, MOCK_PRINTER_BAUDRATE,
            timeout=MOCK_PRINTER_TIMEOUT,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE
        )
        self.assertTrue(self.handler.ser.is_open) # type: ignore

    @patch('time.sleep', MagicMock())
    def test_connect_serial_device_not_found(self):
        self.mock_os_path_exists.return_value = False
        self.assertFalse(self.handler._connect_serial())
        self.mock_serial_class.assert_not_called()

    @patch('time.sleep', MagicMock())
    def test_connect_serial_exception(self):
        self.mock_serial_class.side_effect = serial.SerialException("Printer connection failed")
        self.assertFalse(self.handler._connect_serial())

    def test_disconnect_serial(self):
        self.handler._connect_serial() # Connect first
        self.handler._disconnect_serial()
        self.mock_serial_instance.close.assert_called_once()
        self.assertIsNone(self.handler.ser)

    @patch('time.sleep', MagicMock())
    def test_run_writes_message_to_printer(self):
        message = "Hello Printer"
        self.mqtt_to_serial_queue.put(message)

        self.handler.start()
        time.sleep(0.1) # Allow thread to process

        expected_payload = message.encode('ascii') + b'\n'
        self.mock_serial_instance.write.assert_called_once_with(expected_payload)
        self.assertTrue(self.mqtt_to_serial_queue.empty())

        self.handler.stop()
        self.handler.join()

    @patch('time.sleep', MagicMock())
    def test_run_requeues_on_serial_timeout_exception(self):
        message = "Timeout Test"
        self.mqtt_to_serial_queue.put(message)

        # Simulate write timeout
        self.mock_serial_instance.write.side_effect = serial.SerialTimeoutException("Write timed out")

        self.handler.start()
        time.sleep(0.1) # Allow for at least one attempt, failure, and requeue cycle

        self.handler.stop()
        self.handler.join()

        # Assertions after stopping the handler
        self.mock_serial_instance.write.assert_called() # It might be called multiple times quickly
        self.assertFalse(self.mqtt_to_serial_queue.empty()) # Message should be re-queued
        self.assertEqual(self.mqtt_to_serial_queue.get_nowait(), message)
        # Check if disconnect was called to force reconnect
        self.mock_serial_instance.close.assert_called() # _disconnect_serial should be called

    @patch('time.sleep', MagicMock())
    def test_run_requeues_on_serial_exception_during_write(self):
        message = "SerialExc Test"
        self.mqtt_to_serial_queue.put(message)
        self.mock_serial_instance.write.side_effect = serial.SerialException("General Serial Error")

        self.handler.start()
        time.sleep(0.1) # Allow for at least one attempt, failure, and requeue cycle

        self.handler.stop()
        self.handler.join()

        # Assertions after stopping the handler
        self.mock_serial_instance.write.assert_called() # It might be called multiple times quickly
        self.assertFalse(self.mqtt_to_serial_queue.empty()) # Message should be re-queued
        self.assertEqual(self.mqtt_to_serial_queue.get_nowait(), message)
        self.mock_serial_instance.close.assert_called() # _disconnect_serial should be called

    @patch('time.sleep', MagicMock())
    def test_run_requeues_on_os_error_during_write(self):
        message = "OSError Test"
        self.mqtt_to_serial_queue.put(message)
        self.mock_serial_instance.write.side_effect = OSError("Device not configured")

        self.handler.start()
        time.sleep(0.1) # Allow for at least one attempt, failure, and requeue cycle

        self.handler.stop()
        self.handler.join()

        # Assertions after stopping the handler
        self.mock_serial_instance.write.assert_called() # It might be called multiple times quickly
        self.assertFalse(self.mqtt_to_serial_queue.empty()) # Message should be re-queued
        self.assertEqual(self.mqtt_to_serial_queue.get_nowait(), message)
        self.mock_serial_instance.close.assert_called() # _disconnect_serial should be called

    @patch('time.sleep', MagicMock())
    def test_run_reconnects_after_write_failure_and_prints_requeued_message(self):
        message = "Recover Print"
        self.mqtt_to_serial_queue.put(message)

        # Fail first write, then succeed
        def write_side_effect(*args):
            if write_side_effect.call_count == 1:
                write_side_effect.call_count += 1
                raise serial.SerialException("Simulated write fail")
            # On subsequent calls, write normally (no return value for write)
        write_side_effect.call_count = 1
        self.mock_serial_instance.write.side_effect = write_side_effect

        # Mock os.path.exists to allow reconnect
        self.mock_os_path_exists.return_value = True
        # Mock serial.Serial to return a new mock instance on reconnect attempt
        new_mock_serial_instance = MagicMock(spec=self.original_serial_class_ref) # Use the stored original class ref
        new_mock_serial_instance.is_open = True

        # First call to serial.Serial is the initial one in setUp.
        # Second call will be after the write failure.
        self.mock_serial_class.side_effect = [self.mock_serial_instance, new_mock_serial_instance]


        self.handler.start()
        time.sleep(0.2) # Allow for fail, requeue, reconnect, retry

        self.assertEqual(self.mock_serial_instance.write.call_count, 1) # Original mock called once (failed)
        new_mock_serial_instance.write.assert_called_once_with(message.encode('ascii') + b'\n') # New mock called
        self.assertTrue(self.mqtt_to_serial_queue.empty()) # Message should be processed

        self.handler.stop()
        self.handler.join()

    def test_stop_method(self):
        self.handler.start()
        self.assertTrue(self.handler.is_alive())
        self.handler.stop()
        self.handler.join(timeout=1)
        self.assertFalse(self.handler.is_alive())
        self.assertFalse(self.handler.running)

if __name__ == '__main__':
    unittest.main()
