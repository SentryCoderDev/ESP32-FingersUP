# ─── MQTT ───────────────────────────────────────────────
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883

MQTT_TOPIC_FACE = "fingersup/face"
MQTT_TOPIC_GESTURE = "fingersup/gesture"
MQTT_TOPIC_STATUS = "fingersup/status"
MQTT_TOPIC_WBCMD = "fingersup/webcmd"
MQTT_TOPIC_ALERT = "fingersup/alert"

# ─── Kamera ─────────────────────────────────────────────
CAMERA_IDS = [0, 1]
CAMERA_FLIP = True  # Ayna efekti (selfie kamera için True)

# ─── Yüz Tanıma ────────────────────────────────────────
KNOWN_FACES_DIR = "assets/known_faces"
FACE_RECOGNIZE_EVERY_N_FRAMES = 8
FACE_SAMPLES_PER_PERSON = 10
FACE_RECOGNITION_THRESHOLD = 135.0  # LBPH mesafe eşiği (altı eşleşme, üstü bilinmeyen)


# ─── Mediapipe El Algılama ──────────────────────────────
DETECTION_CONF = 0.7          # Artırıldı (eski: 0.5) — daha az hayalet el
MAX_HANDS = 2
TRACKING_CONF = 0.6           # Artırıldı (eski: 0.5) — takip kayması azaltır
HAND_CONFIDENCE_THRESHOLD = 0.75  # Sağ/sol el sınıflandırma güven eşiği

# ─── Parmak Algılama (Açı-Bazlı + Hysteresis) ──────────
# Parmak açık/kapalı kararı vektör açısı ile verilir (derece)
# Hysteresis: açma eşiği > kapama eşiği → jitter engellenir
FINGER_OPEN_ANGLE = 160       # Bu açıdan büyükse = açık
FINGER_CLOSE_ANGLE = 100      # Bu açıdan küçükse = kapalı
# Arada kalan değerlerde önceki durum korunur (hysteresis bölgesi)

THUMB_OPEN_ANGLE = 140        # Başparmak için ayrı eşikler
THUMB_CLOSE_ANGLE = 90

# ─── Jest Durum Makinesi (FSM) ──────────────────────────
GESTURE_STABLE_MS = 250       # Jestin (önizleme) sabit kalması gereken süre (ms)
GESTURE_COOLDOWN_MS = 700     # Komut sonrası bekleme süresi (ms)
MENU_TIMEOUT_S = 15.0         # Menüde hareketsizlik zaman aşımı (saniye)
CONFIRM_HOLD_MS = 300         # Onay jesti tutma süresi (ms)

# ─── Çoğunluk Oyu (Majority Vote) ──────────────────────
VOTE_WINDOW_SIZE = 5          # Son N frame'in parmak dizisinden mod alınır
VOTE_MIN_AGREEMENT = 3        # En az N frame aynı sonucu vermeli

# ─── Publish ────────────────────────────────────────────
PUBLISH_COOLDOWN = 0.3        # Jitter önleme için bekleme süresi (saniye)

# ─── Eski Uyumluluk (Deprecated) ────────────────────────
MENU_TIMEOUT = 5.0            # Eski — MENU_TIMEOUT_S kullanın
GESTURE_DEBOUNCE_FRAMES = 5   # Eski — GESTURE_STABLE_MS kullanın
