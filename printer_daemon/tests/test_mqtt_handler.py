import unittest
from unittest.mock import patch, MagicMock, ANY
import queue
import time
import ssl

from printer_daemon.mqtt_handler import PrinterMqttHandler
import paho.mqtt.client as paho_mqtt # type: ignore

# Mock MQTT constants
MOCK_BROKER_HOST = "localhost"
MOCK_BROKER_PORT = 1883
MOCK_USERNAME = "test_printer_user"
MOCK_PASSWORD = "test_printer_password"
MOCK_CLIENT_ID = "test_printer_mqtt_client"
MOCK_PRINT_TOPIC = "test/scale/data" # Printer subscribes to this
MOCK_QOS = 2
MOCK_KEEPALIVE = 60

class TestPrinterMqttHandler(unittest.TestCase):

    def setUp(self):
        self.mqtt_to_serial_queue = queue.Queue() # Messages to serial handler for printing

        self.patcher_mqtt_client = patch('paho.mqtt.client.Client')
        self.mock_mqtt_client_class = self.patcher_mqtt_client.start()

        self.mock_client_instance = MagicMock(spec=paho_mqtt.Client)
        self.mock_client_instance.is_connected.return_value = False
        self.mock_mqtt_client_class.return_value = self.mock_client_instance

        self.handler = PrinterMqttHandler(
            MOCK_BROKER_HOST, MOCK_BROKER_PORT, MOCK_USERNAME, MOCK_PASSWORD,
            MOCK_CLIENT_ID, MOCK_PRINT_TOPIC, MOCK_QOS,
            MOCK_KEEPALIVE, self.mqtt_to_serial_queue
        )
        self.handler.reconnect_delay = 0.05 # Faster reconnects

    def tearDown(self):
        if self.handler.is_alive():
            self.handler.stop()
            self.handler.join(timeout=1)
        self.patcher_mqtt_client.stop()

    def test_initialization(self):
        self.assertEqual(self.handler.print_topic, MOCK_PRINT_TOPIC)
        self.assertFalse(self.handler.running)

    @patch('time.sleep', MagicMock())
    def test_setup_client_success(self):
        self.assertTrue(self.handler._setup_client())
        self.mock_mqtt_client_class.assert_called_once_with(paho_mqtt.CallbackAPIVersion.VERSION2, client_id=MOCK_CLIENT_ID)
        self.mock_client_instance.username_pw_set.assert_called_once_with(MOCK_USERNAME, MOCK_PASSWORD)
        self.mock_client_instance.tls_set.assert_called_once_with(
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT
        )
        self.assertIsNotNone(self.handler.client.on_connect)
        self.assertIsNotNone(self.handler.client.on_message)

    def test_on_connect_success_subscribes_to_print_topic(self):
        self.handler._setup_client()
        self.handler._on_connect(self.mock_client_instance, None, None, 0) # rc=0
        self.mock_client_instance.subscribe.assert_called_once_with(MOCK_PRINT_TOPIC, qos=MOCK_QOS)
        self.assertEqual(self.handler.connection_rc, 0)

    def test_on_message_puts_to_queue(self):
        self.handler._setup_client()
        mock_msg = MagicMock(spec=paho_mqtt.MQTTMessage)
        mock_msg.topic = MOCK_PRINT_TOPIC
        mock_msg.payload = b'Print this text'

        self.handler._on_message(self.mock_client_instance, None, mock_msg)
        self.assertEqual(self.mqtt_to_serial_queue.get_nowait(), 'Print this text')

    def test_on_message_handles_decode_error(self):
        self.handler._setup_client()
        mock_msg = MagicMock(spec=paho_mqtt.MQTTMessage)
        mock_msg.topic = MOCK_PRINT_TOPIC
        mock_msg.payload = b'\xff\xfe' # Invalid UTF-8/ASCII start

        self.handler._on_message(self.mock_client_instance, None, mock_msg)
        # Should put replaced string
        self.assertEqual(self.mqtt_to_serial_queue.get_nowait(), '\ufffd\ufffd') # Replacement char

    def test_on_message_empty_payload(self):
        self.handler._setup_client()
        mock_msg = MagicMock(spec=paho_mqtt.MQTTMessage)
        mock_msg.topic = MOCK_PRINT_TOPIC
        mock_msg.payload = b''

        self.handler._on_message(self.mock_client_instance, None, mock_msg)
        self.assertTrue(self.mqtt_to_serial_queue.empty()) # Should not queue empty messages

    @patch('time.sleep', MagicMock())
    def test_run_connects_and_subscribes_main_loop(self):
        self.mock_client_instance.is_connected.side_effect = [False, True, True]

        def mock_connect(*args, **kwargs):
            self.handler._on_connect(self.mock_client_instance, None, None, 0)
            self.mock_client_instance.is_connected.return_value = True
        self.mock_client_instance.connect.side_effect = mock_connect

        self.handler.start()
        time.sleep(0.1)

        self.mock_client_instance.connect.assert_called_once()
        self.mock_client_instance.loop_start.assert_called_once()
        self.mock_client_instance.subscribe.assert_called_with(MOCK_PRINT_TOPIC, qos=MOCK_QOS)

        self.handler.stop()
        self.handler.join()

    @patch('time.sleep', MagicMock())
    def test_run_handles_connection_failure_and_retries(self):
        self.mock_client_instance.is_connected.return_value = False

        call_count = {'count': 0}
        def connect_side_effect(*args, **kwargs):
            call_count['count'] +=1
            if call_count['count'] == 1:
                raise ConnectionRefusedError("Test refuse")
            else:
                self.handler._on_connect(self.mock_client_instance, None, None, 0)
                self.mock_client_instance.is_connected.return_value = True
        self.mock_client_instance.connect.side_effect = connect_side_effect

        self.handler.start()
        time.sleep(0.2) # Allow for attempt, delay, retry

        self.assertEqual(self.mock_client_instance.connect.call_count, 2)
        self.assertTrue(self.mock_client_instance.is_connected())

        self.handler.stop()
        self.handler.join()

    def test_stop_method_disconnects_client(self):
        self.mock_client_instance.is_connected.return_value = True
        self.handler._setup_client()
        self.handler.client = self.mock_client_instance

        self.handler.start()
        time.sleep(0.05)

        self.handler.stop()
        self.handler.join(timeout=1)

        self.mock_client_instance.loop_stop.assert_called_once()
        self.mock_client_instance.disconnect.assert_called_once()
        self.assertFalse(self.handler.running)

if __name__ == '__main__':
    unittest.main()
