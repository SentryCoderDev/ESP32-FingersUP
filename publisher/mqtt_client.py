import paho.mqtt.client as mqtt


class MQTTClient:
    def __init__(self, broker='broker.emqx.io', port=1883, topic='Sentry'):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client()
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

    def publish(self, payload):
        self.client.publish(self.topic, payload)

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
