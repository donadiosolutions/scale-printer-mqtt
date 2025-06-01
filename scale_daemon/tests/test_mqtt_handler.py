import unittest
from unittest.mock import patch, MagicMock, ANY
import queue
import time
import ssl

from scale_daemon.mqtt_handler import ScaleMqttHandler
import paho.mqtt.client as paho_mqtt # type: ignore

# Mock MQTT constants
MOCK_BROKER_HOST = "localhost"
MOCK_BROKER_PORT = 1883 # Standard non-TLS port for mock
MOCK_USERNAME = "test_user"
MOCK_PASSWORD = "test_password"
MOCK_CLIENT_ID = "test_scale_mqtt_client"
MOCK_DATA_TOPIC = "test/scale/data"
MOCK_COMMAND_TOPIC = "test/scale/command"
MOCK_QOS = 2
MOCK_KEEPALIVE = 60

class TestScaleMqttHandler(unittest.TestCase):

    def setUp(self):
        self.serial_to_mqtt_queue = queue.Queue() # Data from serial to publish
        self.mqtt_to_serial_queue = queue.Queue() # Commands to serial

        # Get the original class before it's patched
        original_client_class = paho_mqtt.Client

        self.patcher_mqtt_client = patch('paho.mqtt.client.Client')
        self.mock_mqtt_client_class = self.patcher_mqtt_client.start() # This is the mock for the CLASS

        # Create an instance mock, specced against the original class
        self.mock_client_instance = MagicMock(spec=original_client_class)
        self.mock_client_instance.is_connected.return_value = False # Start as not connected
        # Make the class mock return our instance mock
        self.mock_mqtt_client_class.return_value = self.mock_client_instance

        self.handler = ScaleMqttHandler(
            MOCK_BROKER_HOST, MOCK_BROKER_PORT, MOCK_USERNAME, MOCK_PASSWORD,
            MOCK_CLIENT_ID, MOCK_DATA_TOPIC, MOCK_COMMAND_TOPIC, MOCK_QOS,
            MOCK_KEEPALIVE, self.serial_to_mqtt_queue, self.mqtt_to_serial_queue
        )
        # Shorten reconnect delay for tests
        self.handler.reconnect_delay = 0.1

    def tearDown(self):
        if self.handler.is_alive():
            self.handler.stop()
            self.handler.join(timeout=1)
        self.patcher_mqtt_client.stop()

    def test_initialization(self):
        self.assertEqual(self.handler.broker_host, MOCK_BROKER_HOST)
        self.assertFalse(self.handler.running)
        self.assertIsNone(self.handler.client) # Client is None until _setup_client

    @patch('time.sleep', MagicMock())
    def test_setup_client_success(self):
        self.assertTrue(self.handler._setup_client())
        self.mock_mqtt_client_class.assert_called_once_with(paho_mqtt.CallbackAPIVersion.VERSION2, client_id=MOCK_CLIENT_ID)
        self.mock_client_instance.username_pw_set.assert_called_once_with(MOCK_USERNAME, MOCK_PASSWORD)
        self.mock_client_instance.tls_set.assert_called_once_with(
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT
        )
        self.assertIsNotNone(self.handler.client)
        self.assertIsNotNone(self.handler.client.on_connect)
        self.assertIsNotNone(self.handler.client.on_disconnect)
        self.assertIsNotNone(self.handler.client.on_message)
        self.assertIsNotNone(self.handler.client.on_publish)

    @patch('time.sleep', MagicMock())
    def test_setup_client_failure_exception(self):
        self.mock_mqtt_client_class.side_effect = Exception("Setup error")
        self.assertFalse(self.handler._setup_client())
        self.assertIsNone(self.handler.client)

    def test_on_connect_success(self):
        self.handler._setup_client() # To initialize self.client
        self.handler._on_connect(self.mock_client_instance, None, None, 0) # rc=0 for success
        self.mock_client_instance.subscribe.assert_called_once_with(MOCK_COMMAND_TOPIC, qos=MOCK_QOS)
        self.assertEqual(self.handler.connection_rc, 0)

    def test_on_connect_failure(self):
        self.handler._setup_client()
        self.handler._on_connect(self.mock_client_instance, None, None, 5) # rc=5 for auth error
        self.mock_client_instance.subscribe.assert_not_called()
        self.assertEqual(self.handler.connection_rc, 5)

    def test_on_message_command_topic(self):
        self.handler._setup_client()
        mock_msg = MagicMock(spec=paho_mqtt.MQTTMessage)
        mock_msg.topic = MOCK_COMMAND_TOPIC
        mock_msg.payload = b'T' # Single byte command

        self.handler._on_message(self.mock_client_instance, None, mock_msg)
        self.assertEqual(self.mqtt_to_serial_queue.get_nowait(), b'T')

    def test_on_message_command_topic_empty_payload(self):
        self.handler._setup_client()
        mock_msg = MagicMock(spec=paho_mqtt.MQTTMessage)
        mock_msg.topic = MOCK_COMMAND_TOPIC
        mock_msg.payload = b''

        self.handler._on_message(self.mock_client_instance, None, mock_msg)
        self.assertTrue(self.mqtt_to_serial_queue.empty())

    def test_on_message_unexpected_topic(self):
        self.handler._setup_client()
        mock_msg = MagicMock(spec=paho_mqtt.MQTTMessage)
        mock_msg.topic = "some/other/topic"
        mock_msg.payload = b'data'

        self.handler._on_message(self.mock_client_instance, None, mock_msg)
        self.assertTrue(self.mqtt_to_serial_queue.empty())

    def test_run_connects_and_subscribes(self):
        # is_connected will be called once before connect, should return False.
        # After connect, mock_connect will set return_value to True.
        self.mock_client_instance.is_connected.side_effect = [False]

        # Simulate successful connection via callback
        def mock_connect(*args, **kwargs):
            self.handler._on_connect(self.mock_client_instance, None, None, 0) # rc=0
            self.mock_client_instance.is_connected.return_value = True # Update connected state
            # Clear side_effect so that return_value is used for subsequent calls
            self.mock_client_instance.is_connected.side_effect = None
        self.mock_client_instance.connect.side_effect = mock_connect

        self.handler.start()
        time.sleep(0.1) # Allow thread to run

        self.mock_client_instance.connect.assert_called_once_with(MOCK_BROKER_HOST, MOCK_BROKER_PORT, MOCK_KEEPALIVE)
        self.mock_client_instance.loop_start.assert_called_once()
        # Subscription happens in _on_connect, which is called by mock_connect
        self.mock_client_instance.subscribe.assert_called_with(MOCK_COMMAND_TOPIC, qos=MOCK_QOS)

        self.handler.stop()
        self.handler.join()

    @patch('time.sleep', MagicMock())
    def test_run_publishes_message_from_queue(self):
        self.mock_client_instance.is_connected.return_value = True # Assume connected

        # Simulate successful connection and _on_connect being called
        self.handler._setup_client()
        self.handler.client = self.mock_client_instance # Ensure client is set
        self.handler._on_connect(self.mock_client_instance, None, None, 0)


        message_to_publish = "scale_data_123"
        self.serial_to_mqtt_queue.put(message_to_publish)

        # Mock publish result
        mock_publish_result = MagicMock()
        mock_publish_result.rc = paho_mqtt.MQTT_ERR_SUCCESS
        mock_publish_result.mid = 123
        self.mock_client_instance.publish.return_value = mock_publish_result

        self.handler.start() # Start the thread after setup for this specific test flow
        time.sleep(0.1)

        self.mock_client_instance.publish.assert_called_once_with(
            MOCK_DATA_TOPIC, message_to_publish.encode('utf-8'), qos=MOCK_QOS
        )
        self.assertTrue(self.serial_to_mqtt_queue.empty())

        self.handler.stop()
        self.handler.join()

    def test_run_handles_connection_refused_and_retries(self):
        self.mock_client_instance.is_connected.return_value = False
        # First connect attempt raises ConnectionRefusedError, second succeeds
        call_count = {'count': 0}
        def connect_side_effect(*args, **kwargs):
            call_count['count'] +=1
            if call_count['count'] == 1:
                raise ConnectionRefusedError("Connection refused by broker")
            else: # Second attempt
                self.handler._on_connect(self.mock_client_instance, None, None, 0) # Simulate success
                self.mock_client_instance.is_connected.return_value = True # Update state
        self.mock_client_instance.connect.side_effect = connect_side_effect

        self.handler.start()
        time.sleep(0.3) # Allow for initial attempt, delay, and retry

        self.assertEqual(self.mock_client_instance.connect.call_count, 2)
        self.assertTrue(self.mock_client_instance.is_connected())

        self.handler.stop()
        self.handler.join()

    def test_stop_method_disconnects_client(self):
        self.mock_client_instance.is_connected.return_value = True
        self.handler._setup_client() # Ensure self.client is set
        self.handler.client = self.mock_client_instance

        self.handler.start()
        time.sleep(0.05) # Let it run briefly

        self.handler.stop()
        self.handler.join(timeout=1)

        self.mock_client_instance.loop_stop.assert_called_once()
        self.mock_client_instance.disconnect.assert_called_once()
        self.assertFalse(self.handler.running)

if __name__ == '__main__':
    unittest.main()
