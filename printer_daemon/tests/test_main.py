import unittest
from unittest.mock import patch, MagicMock
import logging

from printer_daemon import main as printer_main

class TestPrinterMain(unittest.TestCase):

    @patch('logging.basicConfig')
    def test_setup_logging(self, mock_basic_config):
        printer_main.setup_logging()
        mock_basic_config.assert_called_once_with(
            level=logging.INFO,
            format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s",
        )

    @patch('printer_daemon.main.PrinterSerialHandler')
    @patch('printer_daemon.main.PrinterMqttHandler')
    @patch('printer_daemon.main.setup_logging')
    @patch('time.sleep', side_effect=KeyboardInterrupt) # To break the main loop
    def test_main_starts_and_stops_handlers(
            self, mock_time_sleep, mock_setup_logging,
            MockMqttHandler, MockSerialHandler):

        mock_serial_instance = MagicMock()
        MockSerialHandler.return_value = mock_serial_instance
        mock_serial_instance.is_alive.return_value = True

        mock_mqtt_instance = MagicMock()
        MockMqttHandler.return_value = mock_mqtt_instance
        mock_mqtt_instance.is_alive.return_value = True

        try:
            printer_main.main()
        except KeyboardInterrupt:
            pass # Expected

        mock_setup_logging.assert_called_once()

        MockSerialHandler.assert_called_once_with(
            printer_main.SERIAL_DEVICE_PATH,
            printer_main.SERIAL_BAUDRATE,
            printer_main.SERIAL_TIMEOUT,
            printer_main.mqtt_to_serial_queue
        )
        mock_serial_instance.start.assert_called_once()

        # Determine the expected use_tls value based on the default string
        expected_use_tls = printer_main.MQTT_USE_TLS_DEFAULT

        MockMqttHandler.assert_called_once_with(
            printer_main.MQTT_BROKER_HOST_DEFAULT,
            printer_main.MQTT_BROKER_PORT_DEFAULT,
            printer_main.MQTT_USERNAME_DEFAULT,
            printer_main.MQTT_PASSWORD_DEFAULT,
            printer_main.MQTT_CLIENT_ID_DEFAULT,
            printer_main.MQTT_PRINT_TOPIC_DEFAULT,
            printer_main.MQTT_QOS_DEFAULT,
            printer_main.MQTT_KEEPALIVE_DEFAULT,
            printer_main.mqtt_to_serial_queue,
            use_tls=expected_use_tls
        )
        mock_mqtt_instance.start.assert_called_once()

        mock_mqtt_instance.stop.assert_called_once()
        mock_mqtt_instance.join.assert_called_once()

        mock_serial_instance.stop.assert_called_once()
        mock_serial_instance.join.assert_called_once()

if __name__ == '__main__':
    unittest.main()
