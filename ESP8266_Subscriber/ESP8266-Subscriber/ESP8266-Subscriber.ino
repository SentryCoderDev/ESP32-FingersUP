#include <ESP8266WiFi.h>
#include <WiFiClient.h>
#include <WiFiServer.h>
#include <PubSubClient.h>

const char* ssid = "your-wifi";
const char* password = "your-pswd";
const char* mqttServer = "broker.emqx.io";
const int port = 1883;

WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastMsg = 0;
#define MSG_BUFFER_SIZE  (50)
char msg[MSG_BUFFER_SIZE];
int value = 0;

const int pinRed = D0;
const int pinYellow = D1;
const int pinBlue = D2;
const int pinPurple = D3;
const int pinGreen = D4;

void setup() {
  Serial.begin(115200);
  randomSeed(analogRead(0));

  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  wifiConnect();

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  Serial.println(WiFi.macAddress());
  
  String stMac = WiFi.macAddress();
  stMac.replace(":", "_");
  Serial.println(stMac);
  
  client.setServer(mqttServer, port);
  client.setCallback(callback);
  pinMode(pinRed, OUTPUT);
  pinMode(pinYellow, OUTPUT);
  pinMode(pinBlue, OUTPUT);
  pinMode(pinPurple, OUTPUT);
  pinMode(pinGreen, OUTPUT);
}

void wifiConnect() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
}

void mqttReconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    long r = random(1000);
    char clientId[50];
    sprintf(clientId, "clientId-%ld", r);
    if (client.connect(clientId)) {
      Serial.print(clientId);
      Serial.println(" connected");
      client.subscribe("your-interesting-subscriber-name");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

void callback(char* topic, byte* message, unsigned int length) {
  for (int i = 0; i < length; i++) {
    switch (i) {
      case 0:
        digitalWrite(pinRed, message[i] == '1' ? HIGH : LOW);
        break;
      case 1:
        digitalWrite(pinYellow, message[i] == '1' ? HIGH : LOW);
        break;
      case 2:
        digitalWrite(pinBlue, message[i] == '1' ? HIGH : LOW);
        break;
      case 3:
        digitalWrite(pinPurple, message[i] == '1' ? HIGH : LOW);
        break;
      case 4:
        digitalWrite(pinGreen, message[i] == '1' ? HIGH : LOW);
        break;
    }
  }
}

void loop() {
  delay(10);
  if (!client.connected()) {
    mqttReconnect();
  }
  client.loop();
}
