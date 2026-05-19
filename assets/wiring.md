# FingersUP - Kablaj Semasi

## ESP8266 Baglantilari

### 7-Segment Display (1 haneli, Common Cathode)
| Segment | ESP8266 Pini |
|---------|-------------|
| a       | D0 (GPIO16) |
| b       | D1 (GPIO5)  |
| c       | D2 (GPIO4)  |
| d       | D3 (GPIO0)  |
| e       | D4 (GPIO2)  |
| f       | D5 (GPIO14) |
| g       | D6 (GPIO12) |
| GND     | GND         |

### UART (ESP -> Arduino)
| ESP8266 | Arduino     |
|---------|-------------|
| TX (D7) | RX (D0)     | 
| RX (D8) | TX (D1)     |
| GND     | GND         |

### Güç
| ESP8266 | Kaynak      |
|---------|-------------|
| VCC     | 3.3V        |
| GND     | GND         |

---

## Arduino Baglantilari

### 16x2 LCD (non-I2C - 4-bit mode)
| LCD Pini | Arduino Pini |
|----------|-------------|
| RS       | A0          |
| E        | A1          |
| D4       | A2          |
| D5       | A3          |
| D6       | A4          |
| D7       | A5          |
| VCC      | 5V          |
| GND      | GND         |
| Vo (kontrast) | 10K pot -> GND |

### LED'ler
| LED    | Arduino Pini |
|--------|-------------|
| Kirmizi| D2          |
| Yesil  | D3          |
| Mavi   | D4          |

Her LED ile seri 220R direnc.

### Buzzer
| Buzzer | Arduino Pini |
|--------|-------------|
| +      | D5          |
| -      | GND         |

### Servo Motor
| Servo  | Arduino Pini |
|--------|-------------|
| Sinyal | D6          |
| VCC    | 5V          |
| GND    | GND         |

### HC-SR04 (Ultrasonik Mesafe Sensörü)
| HC-SR04 | Arduino Pini |
|---------|-------------|
| Trig    | D7          |
| Echo    | D8          |
| VCC     | 5V          |
| GND     | GND         |

### IR Modülü
| IR Modul | Arduino Pini |
|----------|-------------|
| Sinyal   | D9          |
| VCC      | 5V          |
| GND      | GND         |

### LDR (Isik Sensörü)
| LDR Devresi   | Arduino |
|---------------|---------|
| LDR + 10K pulldown | A6  |

Devre: 5V -> LDR -> A6 -> 10K -> GND

### Metal Uçlu Sıcaklık Sensörü (LM35/TMP36 benzeri)
| Sensor | Arduino |
|--------|---------|
| VCC    | 5V      |
| Out    | A7      |
| GND    | GND     |

---

## Güç Yönetimi
- ESP8266: 3.3V (regülatör ile)
- Arduino: 5V (USB veya harici adaptör)
- Ortak GND hatti kullanilmalidir
