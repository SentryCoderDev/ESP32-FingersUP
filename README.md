# FingersUP - Akilli Ev Sistemi

Kamera ile yuz tanima + iki el hareket algilama ile kontrol edilen, MQTT tabanli akilli ev sistemi.

## Mimari

```
                    ┌─────────────────────────┐
                    │   Multi Kamera (PC)     │
                    │  Yuz Tanima + El Takibi │
                    └─────────┬───────────────┘
                              │ MQTT
                    ┌────────▼───────────────┐
                    │    ESP8266             │
                    │  - MQTT subscriber     │
                    │  - 7-Segment Display   │
                    │  - UART -> Arduino     │
                    └────────┬───────────────┘
                              │ UART
                    ┌────────▼───────────────┐
                    │    Arduino             │
                    │  - LCD 16x2            │
                    │  - LED'ler (K,Y,M)     │
                    │  - Servo Motor         │
                    │  - HC-SR04 (Mesafe)    │
                    │  - Sicaklik Sensoru    │
                    │  - IR Modul            │
                    │  - LDR (Isik)          │
                    │  - Buzzer              │
                    └────────────────────────┘

    Web Uygulamasi (Tarayici)
         │ MQTT WebSocket
         └─────────────┘
```

## Ozellikler

- **Yuz Tanima**: Sadece taninan kullanicinin el komutlari calisir
- **Cift El**: Sag el menulerde gezinme, sol el analog deger kontrolu
- **Menu Sistemi**: Yumruk ile menu ac/kapa, parmaklarla 5 ana menu + alt komutlar
- **Multi Kamera**: Ayni anda birden fazla kamera destegi
- **Web Dashboard**: Tarayicidan izleme ve kontrol
- **IR Alternatif**: Uzaktan kumanda ile yedek kontrol

## Menu Yapisi

```
Yumruk -> Menuyu Ac/Kapat

1. ISIKLAR
   1. Kirmizi LED Ac/Kapa
   2. Yesil LED Ac/Kapa
   3. Mavi LED Ac/Kapa
   4. Oda Isigi Durumu (LDR)

2. SICAKLIK
   1. Olcum Al
   2. Alarm Siniri Belirle

3. GUVENLiK
   1. Kapi Durumu (HC-SR04)
   2. Alarm Ac/Kapa
   3. Buzzer Test

4. PERDE/SERVO
   1. Ac (0°)
   2. Kapat (180°)
   3-5. Belirli Acilar

5. SiSTEM
   1. Tum Durum
   2. Segment Test
   3. Yeniden Baslat
```

## Gereksinimler

- Python 3.8+
- Web kamera(lar)
- ESP8266 veya ESP32 (WiFi + MQTT)
- Arduino (Uno/Nano/Mega)
- MQTT Broker (varsayilan: `broker.emqx.io`)

## Python Bagimliliklari

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Yuz Tanima Kayit

1. `assets/known_faces/` klasorune .jpg dosyasi koyun (dosya adi = kisi adi)
2. Veya calisma aninda `r` tusuna basarak kayit yapin

## Hizli Baslangic

```bash
python Publisher.py
```

## Proje Yapisi

```
├── Publisher.py              # Giris noktasi
├── publisher/                # Python paketi
│   ├── main.py              # Ana dongu
│   ├── config.py            # Yapilandirma
│   ├── camera_manager.py    # Multi-kamera yoneticisi
│   ├── face_recognizer.py   # Yuz tanima
│   ├── hand_detector.py     # El hareket algilama
│   ├── gesture_processor.py # Menu sistemi
│   └── mqtt_client.py       # MQTT iletisim
├── ESP_Subscriber/           # ESP8266 kodu
├── Arduino_Controller/       # Arduino kodu
├── web_app/                  # Web dashboard
│   ├── index.html
│   ├── style.css
│   └── app.js
├── assets/
│   ├── known_faces/         # Kayitli yuzler
│   └── wiring.md            # Kablaj semasi
└── requirements.txt
```

## Lisans

Bu proje bir `LICENSE` dosyasi icerir.
