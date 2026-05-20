#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>

// WiFi ve MQTT Bilgileri
const char* ssid = "Wokwi-GUEST";
const char* password = "";
const char* mqttServer = "broker.emqx.io";
const int port = 1883;

// Pin Tanimlamalari
const int pinRed = 12;
const int pinGreen = 14;
const int pinBlue = 27;
const int pinBuzzer = 19;
const int pinServo = 18;
const int pinLDR = 34; // ADC1_CH6

WiFiClient espClient;
PubSubClient client(espClient);
Servo myServo;

unsigned long lastLDRPublish = 0;
const unsigned long ldrInterval = 1000; // 1 saniyede bir LDR oku ve gonder

// LED Durumlari
bool redState = false;
bool greenState = false;
bool blueState = false;

void setup() {
  Serial.begin(115200);
  
  pinMode(pinRed, OUTPUT);
  pinMode(pinGreen, OUTPUT);
  pinMode(pinBlue, OUTPUT);
  pinMode(pinBuzzer, OUTPUT);
  pinMode(pinLDR, INPUT);

  // Servo Kurulumu
  myServo.attach(pinServo, 500, 2400);
  myServo.write(90); // Baslangic pozisyonu 90 derece
  
  // WiFi Baglantisi
  Serial.print("WiFi Baglaniyor: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Baglandi!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  // MQTT Kurulumu
  client.setServer(mqttServer, port);
  client.setCallback(mqttCallback);
}

void mqttReconnect() {
  while (!client.connected()) {
    Serial.print("MQTT Baglantisi Deneniyor...");
    String clientId = "FingersUP-ESP32-Wokwi-" + String(random(0, 1000));
    if (client.connect(clientId.c_str())) {
      Serial.println("Baglandi!");
      client.subscribe("fingersup/gesture");
      // Baglanti basarili bip sesi
      beep(100, 1);
    } else {
      Serial.print("Hata, rc=");
      Serial.print(client.state());
      Serial.println(" 5 saniye sonra tekrar denenecek.");
      delay(5000);
    }
  }
}

// Buzzer yardimci fonksiyonu
void beep(int duration, int count) {
  for (int i = 0; i < count; i++) {
    digitalWrite(pinBuzzer, HIGH);
    delay(duration);
    digitalWrite(pinBuzzer, LOW);
    if (i < count - 1) delay(duration);
  }
}

void playAlarm() {
  for (int i = 0; i < 5; i++) {
    digitalWrite(pinBuzzer, HIGH);
    delay(150);
    digitalWrite(pinBuzzer, LOW);
    delay(150);
  }
}

void mqttCallback(char* topic, byte* message, unsigned int length) {
  String payload = "";
  for (int i = 0; i < length; i++) {
    payload += (char)message[i];
  }
  
  Serial.print("Komut Alindi [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(payload);

  // 1. Menuye Giris / Onay Bildirimi
  if (payload == "CONF") {
    beep(80, 2); // Cift bip
  }
  // 2. Menuden Cikis Bildirimi
  else if (payload == "CONF_EXIT") {
    digitalWrite(pinBuzzer, HIGH);
    delay(300);
    digitalWrite(pinBuzzer, LOW);
  }
  // 3. Alt Menulere Giris Bildirimi
  else if (payload.startsWith("MENU_")) {
    beep(120, 1);
    // Isiklar menusune girildiyse LED'leri flash et
    if (payload == "MENU_Isiklar") {
      digitalWrite(pinRed, HIGH);
      digitalWrite(pinGreen, HIGH);
      digitalWrite(pinBlue, HIGH);
      delay(150);
      digitalWrite(pinRed, redState ? HIGH : LOW);
      digitalWrite(pinGreen, greenState ? HIGH : LOW);
      digitalWrite(pinBlue, blueState ? HIGH : LOW);
    }
  }
  // 4. Komut Islemleri
  // Işıklar Menüsü (EXEC_1_X)
  else if (payload == "EXEC_1_1") { // Kirmizi LED
    redState = !redState;
    digitalWrite(pinRed, redState ? HIGH : LOW);
    beep(50, 1);
  }
  else if (payload == "EXEC_1_2") { // Yesil LED
    greenState = !greenState;
    digitalWrite(pinGreen, greenState ? HIGH : LOW);
    beep(50, 1);
  }
  else if (payload == "EXEC_1_3") { // Mavi LED
    blueState = !blueState;
    digitalWrite(pinBlue, blueState ? HIGH : LOW);
    beep(50, 1);
  }
  else if (payload == "EXEC_1_4") { // Tum Isiklar
    bool anyOn = redState || greenState || blueState;
    redState = !anyOn;
    greenState = !anyOn;
    blueState = !anyOn;
    digitalWrite(pinRed, redState ? HIGH : LOW);
    digitalWrite(pinGreen, greenState ? HIGH : LOW);
    digitalWrite(pinBlue, blueState ? HIGH : LOW);
    beep(50, 1);
  }
  // Güvenlik Menüsü (Buzzer Alarm Tetikleme)
  else if (payload == "EXEC_3_3") {
    playAlarm();
  }
  // Perde Sabit Acilari (EXEC_4_X)
  else if (payload == "EXEC_4_1") { myServo.write(0); beep(80, 1); }
  else if (payload == "EXEC_4_2") { myServo.write(180); beep(80, 1); }
  else if (payload == "EXEC_4_3") { myServo.write(45); beep(80, 1); }
  else if (payload == "EXEC_4_4") { myServo.write(90); beep(80, 1); }
  else if (payload == "EXEC_4_5") { myServo.write(135); beep(80, 1); }
  
  // Perde Analog Acisi (ANALOG_Perde_{aci})
  else if (payload.startsWith("ANALOG_Perde_")) {
    String angleStr = payload.substring(13);
    int angle = angleStr.toInt();
    if (angle >= 0 && angle <= 180) {
      myServo.write(angle);
      // Surekli bip sesi cikarmayalim ki rahatsiz etmesin, sessizce dondurelim
    }
  }
}

void loop() {
  if (!client.connected()) {
    mqttReconnect();
  }
  client.loop();

  // LDR Sensorunu oku ve gonder
  unsigned long now = millis();
  if (now - lastLDRPublish >= ldrInterval) {
    lastLDRPublish = now;
    int ldrRaw = analogRead(pinLDR);
    
    // MQTT uzerinden gonder (Orn: {"ldr": 1024, "lux": "Aydinlik"})
    String luxStatus = "Orta";
    if (ldrRaw < 1000) luxStatus = "Karanlik";
    else if (ldrRaw > 3000) luxStatus = "Cok Aydinlik";
    
    String statusMsg = "{\"ldr\":" + String(ldrRaw) + ",\"status\":\"" + luxStatus + "\"}";
    client.publish("fingersup/status", statusMsg.c_str());
    Serial.println("LDR Status yollandi: " + statusMsg);
  }
}
