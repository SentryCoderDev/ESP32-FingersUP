// Kırmızı LED (Arduino Pin 2) ESP'den veri geldiğinde yanıp sönecek
const int ledPin = 2;
unsigned long lastPing = 0;

void setup() {
  // Sizin donanım projenizdeki gerilim bölücü ve RX/TX pinleri için (0 ve 1)
  Serial.begin(9600);
  pinMode(ledPin, OUTPUT);
}

void loop() {
  // ESP'den gelen veriyi oku
  if (Serial.available() > 0) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();
    
    // ESP'den PING geldiyse, kırmızı LED'i yakıp söndür
    if (msg == "ESP_PING") {
      digitalWrite(ledPin, HIGH);
      delay(100);
      digitalWrite(ledPin, LOW);
    }
  }

  // Her 3 saniyede bir ESP'ye Ping at
  if (millis() - lastPing > 3000) {
    lastPing = millis();
    Serial.println("ARDUINO_PING");
  }
}
