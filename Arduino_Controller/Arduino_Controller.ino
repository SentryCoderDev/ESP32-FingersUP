/*
 * FingersUP - Arduino Controller
 *
 * GOREVLER:
 *   - UART uzerinden ESP8266'dan komut alir
 *   - Komutlari filtreleyerek LCD titremesini ve hatali komutlari engeller
 *   - Tum cevre birimlerini kontrol eder
 *   - Donanim sensor durumlarini JSON olarak Seri porttan ESP8266'ya yollar (1 saniyede bir)
 *
 * BAGLANTILAR:
 *   16x2 LCD (non-I2C) -> RS=12, E=11, D4=10, D5=9, D6=8, D7=7
 *   Kirmizi LED -> 2
 *   Yesil LED   -> 3
 *   Mavi LED    -> 4
 *   Buzzer      -> 5
 *   Servo       -> 6
 *   HC-SR04     -> Trig=13, Echo=A0
 *   LDR         -> A1 (analog)
 *   Sicaklik    -> A2 (analog)
 *   IR Modulu   -> A3 (digital input)
 */

#include <Servo.h>
#include <LiquidCrystal.h>
#include <OneWire.h>
#include <DallasTemperature.h>

LiquidCrystal lcd(12, 11, 10, 9, 8, 7);

Servo myServo;
const int servoPin = 6;

const int ledKirmizi = 2;
const int ledYesil = 3;
const int ledMavi = 4;
const int buzzerPin = 5;

const int trigPin = 13;
const int echoPin = A0;
const int irPin = A3;

const int ldrPin = A1;
const int oneWirePin = A2;  // DS18B20 1-Wire pin (A2 yerine 1-Wire pin)

// DS18B20 Setup
OneWire oneWire(oneWirePin);
DallasTemperature sensors(&oneWire);
DeviceAddress insideThermometer;

bool alarmAktif = false;
int servoAci = 90;
int menuLevel = 0;
int menuSecim = 0;
unsigned long lastLCDUpdate = 0;
unsigned long lastTelemetrySend = 0;
const unsigned long telemetryInterval = 1000; // 1 saniyede bir veri gonder

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(50);

  lcd.begin(16, 2);
  lcd.print("FingersUP");
  lcd.setCursor(0, 1);
  lcd.print("Basliyor...");
  delay(1000);

  pinMode(ledKirmizi, OUTPUT);
  pinMode(ledYesil, OUTPUT);
  pinMode(ledMavi, OUTPUT);
  pinMode(buzzerPin, OUTPUT);
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(irPin, INPUT_PULLUP);

  myServo.attach(servoPin);
  myServo.write(90);

  // DS18B20 Baslatma
  sensors.begin();
  sensors.getAddress(insideThermometer, 0);
  sensors.setResolution(insideThermometer, 9);

  // Baslangic test animasyonu
  for (int i = 0; i < 3; i++) {
    digitalWrite(ledKirmizi, HIGH); delay(100); digitalWrite(ledKirmizi, LOW);
    digitalWrite(ledYesil, HIGH);  delay(100); digitalWrite(ledYesil, LOW);
    digitalWrite(ledMavi, HIGH);   delay(100); digitalWrite(ledMavi, LOW);
  }

  beep(200, 1);
  lcd.clear();
  lcd.print("Hazir!");
  delay(500);
  lcd.clear();
}

void loop() {
  // Gelen komutlari oku
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      processCommand(cmd);
    }
  }

  unsigned long now = millis();
  
  // LCD Ekranini Periyodik Guncelle (Menude degilsek)
  if (now - lastLCDUpdate > 500) {
    updateLCD();
    lastLCDUpdate = now;
  }

  // Telemetri Verisini ESP8266'ya Yolla
  if (now - lastTelemetrySend > telemetryInterval) {
    sendTelemetry();
    lastTelemetrySend = now;
  }

  checkIR();
  checkDistanceAlarm();
}

void processCommand(String cmd) {
  // Gürültüyü temizle: Ilgili komut kelimesinin baslangicini bul ve gürültüden arındır
  int index = -1;
  String cleanCmd = "";
  
  if ((index = cmd.indexOf("CONF_EXIT")) != -1) cleanCmd = "CONF_EXIT";
  else if ((index = cmd.indexOf("CONF")) != -1) cleanCmd = "CONF";
  else if ((index = cmd.indexOf("MENU_TIMEOUT")) != -1) cleanCmd = "MENU_TIMEOUT";
  else if ((index = cmd.indexOf("BUZZER_TEST")) != -1) cleanCmd = "BUZZER_TEST";
  else if ((index = cmd.indexOf("YENIDEN_BASLAT")) != -1) cleanCmd = "YENIDEN_BASLAT";
  else if ((index = cmd.indexOf("SISTEM_DURUM")) != -1) cleanCmd = "SISTEM_DURUM";
  else if ((index = cmd.indexOf("ALARM_AC")) != -1) cleanCmd = "ALARM_AC";
  else if ((index = cmd.indexOf("ALARM_KAPA")) != -1) cleanCmd = "ALARM_KAPA";
  else if ((index = cmd.indexOf("MENU_")) != -1) cleanCmd = cmd.substring(index);
  else if ((index = cmd.indexOf("EXEC_")) != -1) cleanCmd = cmd.substring(index);
  else if ((index = cmd.indexOf("DIRECT_")) != -1) cleanCmd = cmd.substring(index);
  else if ((index = cmd.indexOf("FINGERS_")) != -1) cleanCmd = cmd.substring(index);
  else if ((index = cmd.indexOf("ANALOG_")) != -1) cleanCmd = cmd.substring(index);
  else if ((index = cmd.indexOf("WEB_")) != -1) cleanCmd = cmd.substring(index);
  else if ((index = cmd.indexOf("SISTEM_")) != -1) cleanCmd = cmd.substring(index);
  else if ((index = cmd.indexOf("ALARM_")) != -1) cleanCmd = cmd.substring(index);

  if (cleanCmd == "") return; // Gecersiz veya gurultulu veri, yoksay

  // 1. Menuden Cikis / Kapanis
  if (cleanCmd == "CONF" || cleanCmd == "CONF_EXIT" || cleanCmd == "MENU_TIMEOUT") {
    menuLevel = 0;
    menuSecim = 0;
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Komut: ");
    lcd.print(cleanCmd);
    lcd.setCursor(0, 1);
    lcd.print("Menu kapandi");
    delay(400);
    lcd.clear();
    return;
  }

  // 2. LCD'de Komutu Goster
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Komut: ");
  lcd.print(cleanCmd.substring(0, 9)); // Ilk 9 karakteri yazdır

  // 3. Alt Komutlari Yonlendir
  if (cleanCmd.startsWith("MENU_")) { handleMenu(cleanCmd); return; }
  if (cleanCmd.startsWith("EXEC_")) { handleExec(cleanCmd); return; }
  if (cleanCmd.startsWith("DIRECT_")) { handleDirect(cleanCmd); return; }
  if (cleanCmd.startsWith("FINGERS_")) { handleFingers(cleanCmd); return; }
  if (cleanCmd.startsWith("ANALOG_")) { handleAnalog(cleanCmd); return; }
  
  // 4. Web Dashboard Arayuz Komutlari
  if (cleanCmd.startsWith("WEB_LED_")) {
    String leds = cleanCmd.substring(8);
    if (leds.length() >= 3) {
      digitalWrite(ledKirmizi, leds[0] == '1' ? HIGH : LOW);
      digitalWrite(ledYesil,   leds[1] == '1' ? HIGH : LOW);
      digitalWrite(ledMavi,    leds[2] == '1' ? HIGH : LOW);
      lcd.setCursor(0, 1);
      lcd.print("WEB LED: ");
      lcd.print(leds.substring(0,3));
      delay(400);
    }
    return;
  }
  if (cleanCmd.startsWith("WEB_SERVO_")) {
    int val = cleanCmd.substring(10).toInt();
    int pos = constrain(val, 0, 180);
    myServo.write(pos);
    servoAci = pos;
    lcd.setCursor(0, 1);
    lcd.print("WEB Servo: ");
    lcd.print(pos);
    delay(400);
    return;
  }
  if (cleanCmd == "SISTEM_DURUM") {
    handleSystem(1); // Durum bilgisi goster
    return;
  }
  if (cleanCmd == "ALARM_AC") {
    alarmAktif = true;
    digitalWrite(ledKirmizi, HIGH);
    lcd.setCursor(0, 1);
    lcd.print("Alarm: ACIK");
    beep(80, 2);
    delay(400);
    return;
  }
  if (cleanCmd == "ALARM_KAPA") {
    alarmAktif = false;
    digitalWrite(ledKirmizi, LOW);
    lcd.setCursor(0, 1);
    lcd.print("Alarm: KAPALI");
    beep(200, 1);
    delay(400);
    return;
  }
  if (cleanCmd == "BUZZER_TEST") {
    lcd.setCursor(0, 1);
    lcd.print("Buzzer Testi...");
    beep(500, 1);
    delay(600);
    return;
  }
  if (cleanCmd == "YENIDEN_BASLAT") {
    lcd.setCursor(0, 1);
    lcd.print("Resetleniyor...");
    delay(500);
    void (*resetFunc)(void) = 0;
    resetFunc();
    return;
  }
}

void handleMenu(String cmd) {
  menuLevel = 1;
  lcd.setCursor(0, 1);
  lcd.print(cmd.substring(5));
}

void handleExec(String cmd) {
  int first_ = cmd.indexOf('_');
  int second_ = cmd.indexOf('_', first_ + 1);
  if (first_ == -1 || second_ == -1) return;

  int menuNo = cmd.substring(first_ + 1, second_).toInt();
  int subNo = cmd.substring(second_ + 1).toInt();

  lcd.setCursor(0, 1);
  lcd.print("Giris: ");
  lcd.print(menuNo);
  lcd.print("-");
  lcd.print(subNo);
  delay(400);

  switch (menuNo) {
    case 1: handleLights(subNo); break;
    case 2: handleTemperature(subNo); break;
    case 3: handleSecurity(subNo); break;
    case 4: handleServo(subNo); break;
    case 5: handleSystem(subNo); break;
  }
}

void handleDirect(String cmd) {
  String fingerStr = cmd.substring(7);
  if (fingerStr.length() < 3) return;

  digitalWrite(ledKirmizi, fingerStr[0] == '1' ? HIGH : LOW);
  digitalWrite(ledYesil,   fingerStr[1] == '1' ? HIGH : LOW);
  digitalWrite(ledMavi,    fingerStr[2] == '1' ? HIGH : LOW);

  lcd.setCursor(0, 1);
  lcd.print("LED: ");
  lcd.print(fingerStr.substring(0, 3));
  delay(300);
}

void handleFingers(String cmd) {
  if (cmd.length() < 9) return;
  int fingerCount = cmd[8] - '0';
  if (fingerCount < 0 || fingerCount > 5) return;
  
  lcd.setCursor(0, 1);
  lcd.print("Parmak: ");
  lcd.print(fingerCount);
  lcd.print("     ");
}

void handleAnalog(String cmd) {
  int last_ = cmd.lastIndexOf('_');
  if (last_ == -1) return;

  int spreadVal = cmd.substring(last_ + 1).toInt();
  int servoPos = constrain(spreadVal, 0, 180);
  myServo.write(servoPos);
  servoAci = servoPos;

  lcd.setCursor(0, 1);
  lcd.print("Servo: ");
  lcd.print(servoPos);
  lcd.print(" deg   ");
}

void handleLights(int sub) {
  switch (sub) {
    case 1:
      digitalWrite(ledKirmizi, !digitalRead(ledKirmizi));
      lcd.setCursor(0, 1);
      lcd.print(digitalRead(ledKirmizi) ? "Kirmizi ACIK" : "Kirmizi KAPALI");
      break;
    case 2:
      digitalWrite(ledYesil, !digitalRead(ledYesil));
      lcd.setCursor(0, 1);
      lcd.print(digitalRead(ledYesil) ? "Yesil ACIK" : "Yesil KAPALI");
      break;
    case 3:
      digitalWrite(ledMavi, !digitalRead(ledMavi));
      lcd.setCursor(0, 1);
      lcd.print(digitalRead(ledMavi) ? "Mavi ACIK" : "Mavi KAPALI");
      break;
    case 4:
      int ldrVal = analogRead(ldrPin);
      lcd.setCursor(0, 1);
      lcd.print("Isik: ");
      lcd.print(ldrVal);
      break;
  }
  delay(500);
}

void handleTemperature(int sub) {
  if (sub == 1) {
    sensors.requestTemperatures();
    float tempC = sensors.getTempC(insideThermometer);
    
    // -127 veya 85 (başarısız okuma) kontrolü
    if (tempC < -50 || tempC > 80) {
      lcd.setCursor(0, 1);
      lcd.print("Sensor Hatasi!");
    } else {
      lcd.setCursor(0, 1);
      lcd.print("Sicaklik: ");
      lcd.print(tempC, 1);
      lcd.print(" C");
    }
  } else if (sub == 2) {
    lcd.setCursor(0, 1);
    lcd.print("Alarm siniri: 30C");
  }
  delay(1000);
}

void handleSecurity(int sub) {
  if (sub == 1) {
    // Mesafe 15 saniye boyunca göster
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Mesafe Tarama...");
    unsigned long startTime = millis();
    
    while (millis() - startTime < 15000) {
      // Serial komutlarını kontrol et (loop'u kilitleme)
      if (Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd.length() > 0) {
          processCommand(cmd);
          return;  // Menu'yu iptal et
        }
      }
      
      // Mesafe oku
      digitalWrite(trigPin, LOW);
      delayMicroseconds(2);
      digitalWrite(trigPin, HIGH);
      delayMicroseconds(10);
      digitalWrite(trigPin, LOW);
      long duration = pulseIn(echoPin, HIGH, 20000);
      int distance = duration * 0.034 / 2;
      if (distance == 0 || distance > 400) distance = 999;
      
      lcd.setCursor(0, 1);
      lcd.print("Mesafe: ");
      if (distance == 999) {
        lcd.print("--  cm  ");
      } else {
        lcd.print(distance);
        lcd.print(" cm ");
        // Buzzer sesi: mesafe küçüldükçe sıklık artsın
        if (distance < 20 && distance > 0) {
          beep(50, 1);
        } else if (distance < 50 && distance > 0) {
          beep(100, 1);
        }
      }
      delay(300);
    }
    
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Tarama Bitti");
    delay(500);
    
  } else if (sub == 2) {
    // Alarm modu - LED açık, mesafeye göre buzzer
    alarmAktif = !alarmAktif;
    lcd.setCursor(0, 1);
    lcd.print(alarmAktif ? "Alarm AKTIF" : "Alarm PASIF");
    if (alarmAktif) {
      digitalWrite(ledKirmizi, HIGH);  // Kırmızı LED aç
      beep(100, 2);
    } else {
      digitalWrite(ledKirmizi, LOW);
      beep(200, 1);
    }
    
  } else if (sub == 3) {
    // Buzzer Test
    lcd.setCursor(0, 1);
    lcd.print("Buzzer Testi");
    for (int i = 0; i < 3; i++) {
      beep(300, 1);
      delay(200);
    }
  }
  
  delay(800);
}

void handleServo(int sub) {
  int angles[] = {0, 180, 45, 90, 135};
  if (sub >= 1 && sub <= 5) {
    int angle = angles[sub - 1];
    myServo.write(angle);
    servoAci = angle;
    lcd.setCursor(0, 1);
    lcd.print("Servo: ");
    lcd.print(angle);
    lcd.print(" derece");
  }
  delay(500);
}

void handleSystem(int sub) {
  switch (sub) {
    case 1:
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("LED:");
      lcd.print(digitalRead(ledKirmizi));
      lcd.print(digitalRead(ledYesil));
      lcd.print(digitalRead(ledMavi));
      lcd.setCursor(0, 1);
      lcd.print("Srv:");
      lcd.print(servoAci);
      lcd.print(" Alm:");
      lcd.print(alarmAktif ? "A" : "P");
      delay(2000);
      break;
    case 2:
      lcd.setCursor(0, 1);
      lcd.print("Segment Test...");
      delay(500);
      break;
    case 3:
      lcd.setCursor(0, 1);
      lcd.print("Yeniden Baslat");
      delay(500);
      void (*resetFunc)(void) = 0;
      resetFunc();
      break;
  }
}

void updateLCD() {
  if (menuLevel == 0) {
    lcd.setCursor(0, 0);
    lcd.print("FingersUP Hazir ");

    int ldrVal = analogRead(ldrPin);
    lcd.setCursor(0, 1);
    lcd.print("Isik:");
    lcd.print(ldrVal);
    lcd.print(" LED:");
    lcd.print(digitalRead(ledKirmizi));
    lcd.print(digitalRead(ledYesil));
    lcd.print(digitalRead(ledMavi));
    lcd.print(" ");
  }
}

void checkIR() {
  if (digitalRead(irPin) == LOW) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("IR Sinyal Alindi");
    beep(100, 1);
    delay(250);
    lcd.clear();
  }
}

void beep(int duration, int count) {
  for (int i = 0; i < count; i++) {
    tone(buzzerPin, 1000); // 1 kHz frekansında aktif ses üret
    delay(duration);
    noTone(buzzerPin);
    if (i < count - 1) delay(duration);
  }
}

void checkDistanceAlarm() {
  if (!alarmAktif) return;
  
  static unsigned long lastDistanceCheck = 0;
  unsigned long now = millis();
  if (now - lastDistanceCheck > 200) {
    lastDistanceCheck = now;
    
    // Mesafe oku (HC-SR04)
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);
    long duration = pulseIn(echoPin, HIGH, 20000);
    int distance = duration * 0.034 / 2;
    if (distance == 0 || distance > 400) distance = 999;
    
    // Mesafeye göre buzzer sesi
    if (distance > 0 && distance < 20) {
      // Çok yakın - hızlı buzzer
      beep(50, 2);
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("UYARI!");
      lcd.setCursor(0, 1);
      lcd.print("Mesafe: ");
      lcd.print(distance);
      lcd.print(" cm");
      lastLCDUpdate = millis() + 1000;
    } else if (distance >= 20 && distance < 50) {
      // Orta - normal buzzer
      beep(100, 1);
    } else if (distance >= 50 && distance < 100) {
      // Uzak - nadir buzzer
      beep(200, 1);
    }
  }
}

void sendTelemetry() {
  // LDR oku
  int ldrVal = analogRead(ldrPin);
  
  // Sicaklik oku (DS18B20)
  sensors.requestTemperatures();
  float tempC = sensors.getTempC(insideThermometer);
  
  // Sensorhata kontrolü - hatalı veri gelirse -999 gönder
  if (tempC < -50 || tempC > 80) {
    tempC = -999;
  }
  
  // Mesafe oku (HC-SR04)
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, 20000); // 20ms zaman asimi (yaklasik 3.4 metre maks)
  int distance = duration * 0.034 / 2;
  if (distance == 0) distance = 999;
  
  // IR oku
  int irVal = (digitalRead(irPin) == LOW) ? 1 : 0;
  
  // JSON formatında paketle ve Seri porttan doğrudan yolla (Bellek şişmesini önlemek için)
  Serial.print("{\"sicaklik\":"); Serial.print(tempC, 1);
  Serial.print(",\"isik\":"); Serial.print(ldrVal);
  Serial.print(",\"mesafe\":"); Serial.print(distance);
  Serial.print(",\"ir\":"); Serial.print(irVal);
  Serial.print(",\"ledler\":{\"r\":"); Serial.print(digitalRead(ledKirmizi));
  Serial.print(",\"g\":"); Serial.print(digitalRead(ledYesil));
  Serial.print(",\"b\":"); Serial.print(digitalRead(ledMavi));
  Serial.print("},\"servo\":"); Serial.print(servoAci);
  Serial.print(",\"alarm\":"); Serial.print(alarmAktif ? 1 : 0);
  Serial.println("}");
}
