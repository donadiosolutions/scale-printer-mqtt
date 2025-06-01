import unittest
from unittest.mock import patch, MagicMock
import logging

# Assuming scale_daemon.main is accessible
from scale_daemon import main as scale_main
# from scale_daemon.main import setup_logging, main as run_main_logic # More specific imports

class TestScaleMain(unittest.TestCase):

    @patch('logging.basicConfig')
    def test_setup_logging(self, mock_basic_config):
        scale_main.setup_logging()
        mock_basic_config.assert_called_once_with(
            level=logging.INFO,
            format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s",
        )

    @patch('scale_daemon.main.ScaleSerialHandler')
    @patch('scale_daemon.main.ScaleMqttHandler')
    @patch('scale_daemon.main.setup_logging')
    @patch('time.sleep', side_effect=KeyboardInterrupt) # To break the main loop
    def test_main_starts_and_stops_handlers(
            self, mock_time_sleep, mock_setup_logging,
            MockMqttHandler, MockSerialHandler):

        mock_serial_instance = MagicMock()
        MockSerialHandler.return_value = mock_serial_instance
        mock_serial_instance.is_alive.return_value = True # Simulate alive then stopped

        mock_mqtt_instance = MagicMock()
        MockMqttHandler.return_value = mock_mqtt_instance
        mock_mqtt_instance.is_alive.return_value = True # Simulate alive then stopped

        try:
            scale_main.main()
        except KeyboardInterrupt:
            pass # Expected

        mock_setup_logging.assert_called_once()

        MockSerialHandler.assert_called_once_with(
            scale_main.SERIAL_DEVICE_PATH,
            scale_main.SERIAL_BAUDRATE,
            scale_main.SERIAL_TIMEOUT,
            scale_main.serial_to_mqtt_queue,
            scale_main.mqtt_to_serial_queue
        )
        mock_serial_instance.start.assert_called_once()

        # Determine the expected use_tls value based on the default string
        expected_use_tls = scale_main.MQTT_USE_TLS_DEFAULT

        MockMqttHandler.assert_called_once_with(
            scale_main.MQTT_BROKER_HOST_DEFAULT,
            scale_main.MQTT_BROKER_PORT_DEFAULT,
            scale_main.MQTT_USERNAME_DEFAULT,
            scale_main.MQTT_PASSWORD_DEFAULT,
            scale_main.MQTT_CLIENT_ID_DEFAULT,
            scale_main.MQTT_DATA_TOPIC_DEFAULT,
            scale_main.MQTT_COMMAND_TOPIC_DEFAULT,
            scale_main.MQTT_QOS_DEFAULT,
            scale_main.MQTT_KEEPALIVE_DEFAULT,
            scale_main.serial_to_mqtt_queue,
            scale_main.mqtt_to_serial_queue,
            use_tls=expected_use_tls
        )
        mock_mqtt_instance.start.assert_called_once()

        # Check stop and join calls
        # Need to manage is_alive return values if testing join order strictly
        mock_mqtt_instance.stop.assert_called_once()
        mock_mqtt_instance.join.assert_called_once()

        mock_serial_instance.stop.assert_called_once()
        mock_serial_instance.join.assert_called_once()

if __name__ == '__main__':
    unittest.main()
