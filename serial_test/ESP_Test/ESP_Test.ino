// ESP8266 üzerindeki dahili Mavi LED
const int ledPin = LED_BUILTIN; 
unsigned long lastPing = 0;

void setup() {
  // Sizin donanım projenizdeki RX/TX pinleri için
  Serial.begin(9600);
  pinMode(ledPin, OUTPUT);
  // ESP8266 dahili ledi LOW'da yanar, HIGH'da söner.
  digitalWrite(ledPin, HIGH); 
}

void loop() {
  // Arduino'dan gelen veriyi oku
  if (Serial.available() > 0) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();
    
    // Arduino'dan PING geldiyse, mavi LED'i yakıp söndür
    if (msg == "ARDUINO_PING") {
      digitalWrite(ledPin, LOW); // Yak
      delay(100);
      digitalWrite(ledPin, HIGH); // Söndür
    }
  }

  // Her 3 saniyede bir Arduino'ya Ping at (Asenkron olması için 2.5 sn)
  if (millis() - lastPing > 2500) {
    lastPing = millis();
    Serial.println("ESP_PING");
  }
}
