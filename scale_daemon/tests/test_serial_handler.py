import unittest
from unittest.mock import patch, MagicMock, call
import queue
import time
import os

# Assuming the daemon's src directory is in PYTHONPATH for test execution
# or using relative imports if tests are run as a module.
# For simplicity, let's assume scale_daemon.serial_handler is findable.
from scale_daemon.serial_handler import ScaleSerialHandler
# If poetry run pytest is used from scale_daemon directory, this should work.
# Alternatively, adjust PYTHONPATH or use `src.scale_daemon.serial_handler`
# if tests are run from the project root and src is a source root.

# Mock serial.Serial attributes that might be accessed
MOCK_SERIAL_PORT = "/dev/ttyTestScale"
MOCK_BAUDRATE = 9600
MOCK_TIMEOUT = 1

class TestScaleSerialHandler(unittest.TestCase):

    def setUp(self):
        self.serial_to_mqtt_queue = queue.Queue()
        self.mqtt_to_serial_queue = queue.Queue()
        # Patch 'serial.Serial' and 'os.path.exists' for all tests in this class
        self.patcher_serial = patch('serial.Serial')
        self.patcher_os_path_exists = patch('os.path.exists')

        self.mock_serial_class = self.patcher_serial.start()
        self.mock_os_path_exists = self.patcher_os_path_exists.start()

        # Configure the mock for os.path.exists to return True by default
        self.mock_os_path_exists.return_value = True

        # Configure the mock serial object that serial.Serial() will return
        self.mock_serial_instance = MagicMock()
        self.mock_serial_instance.is_open = True # Start as open
        self.mock_serial_instance.in_waiting = 0
        self.mock_serial_class.return_value = self.mock_serial_instance

        self.handler = ScaleSerialHandler(
            MOCK_SERIAL_PORT, MOCK_BAUDRATE, MOCK_TIMEOUT,
            self.serial_to_mqtt_queue, self.mqtt_to_serial_queue
        )
        # Shorten reconnect delay for tests to speed them up
        self.handler.reconnect_delay = 0.1

    def tearDown(self):
        if self.handler.is_alive():
            self.handler.stop()
            self.handler.join(timeout=1) # Wait for thread to finish
        self.patcher_serial.stop()
        self.patcher_os_path_exists.stop()

    def test_initialization(self):
        self.assertEqual(self.handler.device_path, MOCK_SERIAL_PORT)
        self.assertEqual(self.handler.baudrate, MOCK_BAUDRATE)
        self.assertFalse(self.handler.running)
        self.assertIsNone(self.handler.ser) # ser is None until _connect_serial is called

    @patch('time.sleep', MagicMock()) # Mock time.sleep to avoid delays
    def test_connect_serial_success(self):
        self.mock_os_path_exists.return_value = True
        self.assertTrue(self.handler._connect_serial())
        self.mock_serial_class.assert_called_once_with(
            MOCK_SERIAL_PORT, MOCK_BAUDRATE,
            timeout=MOCK_TIMEOUT,
            bytesize=serial.EIGHTBITS, # type: ignore
            parity=serial.PARITY_NONE, # type: ignore
            stopbits=serial.STOPBITS_ONE # type: ignore
        )
        self.assertIsNotNone(self.handler.ser)
        self.assertTrue(self.handler.ser.is_open) # type: ignore

    @patch('time.sleep', MagicMock())
    def test_connect_serial_device_not_found(self):
        self.mock_os_path_exists.return_value = False
        self.assertFalse(self.handler._connect_serial())
        self.mock_serial_class.assert_not_called()
        self.assertIsNone(self.handler.ser)

    @patch('time.sleep', MagicMock())
    def test_connect_serial_exception(self):
        self.mock_os_path_exists.return_value = True
        self.mock_serial_class.side_effect = serial.SerialException("Connection failed") # type: ignore
        self.assertFalse(self.handler._connect_serial())
        self.assertIsNone(self.handler.ser)

    def test_disconnect_serial(self):
        # First connect
        self.handler._connect_serial()
        self.assertIsNotNone(self.handler.ser)

        self.handler._disconnect_serial()
        self.mock_serial_instance.close.assert_called_once()
        self.assertIsNone(self.handler.ser)

    def test_disconnect_serial_not_connected(self):
        self.handler._disconnect_serial() # Should not raise error
        self.mock_serial_instance.close.assert_not_called()

    @patch('time.sleep', MagicMock())
    def test_run_reads_from_scale_and_puts_to_queue(self):
        # Simulate data from scale
        self.mock_serial_instance.read.side_effect = [b'1', b'2', b'3', b'.', b'5', b'\n', b'O', b'K', b'\n']
        # Make in_waiting reflect that there's data
        type(self.mock_serial_instance).in_waiting = unittest.mock.PropertyMock(side_effect=[1,1,1,1,1,1,1,1,1,0,0,0])


        self.handler.start()
        time.sleep(0.1) # Give thread time to run and process

        # Check queue
        try:
            msg1 = self.serial_to_mqtt_queue.get(timeout=0.5)
            self.assertEqual(msg1, "123.5")
            msg2 = self.serial_to_mqtt_queue.get(timeout=0.5)
            self.assertEqual(msg2, "OK")
        except queue.Empty:
            self.fail("serial_to_mqtt_queue was empty, expected messages.")

        self.handler.stop()
        self.handler.join()

    @patch('time.sleep', MagicMock())
    def test_run_writes_command_to_scale(self):
        command_to_send = b'T'
        self.mqtt_to_serial_queue.put(command_to_send)

        self.handler.start()
        time.sleep(0.1) # Give thread time to run

        self.mock_serial_instance.write.assert_called_once_with(command_to_send)

        self.handler.stop()
        self.handler.join()

    @patch('time.sleep', MagicMock())
    def test_run_reconnects_on_serial_exception_during_read(self):
        # Simulate initial successful connection
        self.mock_os_path_exists.return_value = True

        # First call to read works, then raises exception, then works again
        self.mock_serial_instance.read.side_effect = [
            b'D', b'A', b'T', b'A', b'\n', # Successful read
            serial.SerialException("Read error"), # type: ignore
            b'R', b'E', b'C', b'O', b'V', b'E', b'R', b'E', b'D', b'\n' # Successful read after reconnect
        ]
        type(self.mock_serial_instance).in_waiting = unittest.mock.PropertyMock(side_effect=[1,1,1,1,1, 0, 1,1,1,1,1,1,1,1,1,1, 0])


        self.handler.start()
        time.sleep(0.2) # Allow time for initial read, exception, and reconnect attempt

        # Check if _connect_serial was called multiple times (initial + reconnect attempt)
        # The first call is in setUp or if run calls it before loop.
        # The second call should happen after the SerialException.
        self.assertGreaterEqual(self.mock_serial_class.call_count, 2)

        try:
            msg1 = self.serial_to_mqtt_queue.get(timeout=0.5)
            self.assertEqual(msg1, "DATA")
            msg2 = self.serial_to_mqtt_queue.get(timeout=0.5) # After reconnect
            self.assertEqual(msg2, "RECOVERED")
        except queue.Empty:
            self.fail("serial_to_mqtt_queue did not contain expected messages after reconnect.")

        self.handler.stop()
        self.handler.join()

    @patch('time.sleep', MagicMock())
    def test_run_handles_device_disappearance_and_reappearance(self):
        # Device exists initially, then disappears, then reappears
        self.mock_os_path_exists.side_effect = [
            True,  # Initial connect
            False, # Device disappears
            False, # Still disappeared
            True,  # Device reappears
            True   # Stays appeared
        ]
        self.mock_serial_instance.read.side_effect = [
            b'L',b'I',b'V',b'E',b'\n', # Before disappearance
            # After reappearance
            b'B',b'A',b'C',b'K',b'\n'
        ]
        type(self.mock_serial_instance).in_waiting = unittest.mock.PropertyMock(side_effect=[1,1,1,1,1, 0, 1,1,1,1,1, 0])


        self.handler.start()
        time.sleep(0.5) # Allow time for connect, disconnect, reconnect cycle

        self.assertGreaterEqual(self.mock_os_path_exists.call_count, 3) # Initial, check fails, check succeeds
        self.assertGreaterEqual(self.mock_serial_class.call_count, 2) # Initial connect, reconnect

        try:
            msg1 = self.serial_to_mqtt_queue.get(timeout=0.5)
            self.assertEqual(msg1, "LIVE")
            msg2 = self.serial_to_mqtt_queue.get(timeout=0.5)
            self.assertEqual(msg2, "BACK")
        except queue.Empty:
            self.fail("Messages not received after device disappearance and reappearance.")

        self.handler.stop()
        self.handler.join()

    def test_stop_method(self):
        self.handler.start()
        self.assertTrue(self.handler.is_alive())
        self.handler.stop()
        self.handler.join(timeout=1) # Give it a second to stop
        self.assertFalse(self.handler.is_alive())
        self.assertFalse(self.handler.running)


if __name__ == '__main__':
    unittest.main()
