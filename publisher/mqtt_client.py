import json
import paho.mqtt.client as mqtt
from .config import MQTT_BROKER, MQTT_PORT


class MQTTClient:
    def __init__(self, broker=MQTT_BROKER, port=MQTT_PORT):
        self.broker = broker
        self.port = port
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()
        self.web_command = None
        self.esp32_status = None

    def _on_connect(self, client, userdata, flags, rc):
        print(f"MQTT baglantisi kuruldu (kod: {rc})")
        self.client.subscribe("fingersup/webcmd")
        self.client.subscribe("fingersup/status")

    def _on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode('utf-8', errors='ignore')
        except Exception:
            payload_str = ""

        if msg.topic == "fingersup/webcmd":
            self.web_command = payload_str
        elif msg.topic == "fingersup/status":
            print(f"DEBUG MQTT RECEIVE (status): {payload_str}")
            try:
                self.esp32_status = json.loads(payload_str)
            except Exception:
                self.esp32_status = {"raw": payload_str}

    def publish_gesture(self, payload):
        self.client.publish("fingersup/gesture", payload)

    def publish_face(self, payload):
        self.client.publish("fingersup/face", payload)

    def publish_status(self, payload):
        self.client.publish("fingersup/status", json.dumps(payload) if isinstance(payload, dict) else payload)

    def get_web_command(self):
        cmd = self.web_command
        self.web_command = None
        return cmd

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
