import cv2
import math
import time
import mediapipe as mp
from . import config
from .face_recognizer import FaceRecognizer
from .gesture_state_machine import GestureStateMachine
from .config import (
    FACE_RECOGNIZE_EVERY_N_FRAMES, FACE_SAMPLES_PER_PERSON,
    DETECTION_CONF, TRACKING_CONF, HAND_CONFIDENCE_THRESHOLD,
    FINGER_OPEN_ANGLE, FINGER_CLOSE_ANGLE,
    THUMB_OPEN_ANGLE, THUMB_CLOSE_ANGLE,
    CAMERA_FLIP, PUBLISH_COOLDOWN,
)

TIP_COLORS = [(0,0,255),(0,165,255),(0,255,255),(0,255,0),(255,0,0)]
TIP_LABELS = ["B","I","O","Y","S"]

# Mediapipe landmark indeksleri
# Her parmak için: [MCP, PIP, DIP, TIP]
FINGER_JOINTS = {
    0: [1, 2, 3, 4],      # Başparmak: CMC→MCP→IP→TIP
    1: [5, 6, 7, 8],      # İşaret
    2: [9, 10, 11, 12],    # Orta
    3: [13, 14, 15, 16],   # Yüzük
    4: [17, 18, 19, 20],   # Serçe
}


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _angle_at_joint(a, b, c):
    """
    a-b-c noktaları arasındaki açıyı derece olarak hesapla.
    b = eklem noktası (köşe).
    Açık parmak ≈ 180°, kapalı parmak ≈ 30-90°.
    """
    ba = [a[0] - b[0], a[1] - b[1]]
    bc = [c[0] - b[0], c[1] - b[1]]
    dot = ba[0] * bc[0] + ba[1] * bc[1]
    mag_ba = math.sqrt(ba[0]**2 + ba[1]**2) + 1e-6
    mag_bc = math.sqrt(bc[0]**2 + bc[1]**2) + 1e-6
    cos_angle = _clamp(dot / (mag_ba * mag_bc), -1.0, 1.0)
    return math.degrees(math.acos(cos_angle))


class CameraManager:
    def __init__(self, mqtt_client, camera_ids=None):
        self.mqtt = mqtt_client
        self.camera_ids = camera_ids or [0]
        self.face_recognizer = FaceRecognizer()
        self.caps = []
        self.running = True

        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.hands_detector = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=DETECTION_CONF,
            min_tracking_confidence=TRACKING_CONF,
        )
        self.finger_tips = [4, 8, 12, 16, 20]
        self.thumb_mcp = 2

        # Her kamera için ayrı FSM ve state
        self.menu_systems = {}
        self.last_face_name = {}
        self.last_gesture_cmd = {}
        self.last_publish_time = {}
        self.face_frame_counters = {}
        self.cached_face_data = {}
        self.is_registering = False
        
        # Sensor verileri kalıcı cache (bağlantı kopsa bile gösterilsin)
        self.cached_sensor_data = {
            "sicaklik": "--",
            "isik": "--",
            "mesafe": "--",
            "ir": "--",
            "ledler": {"r": "--", "g": "--", "b": "--"},
            "servo": "--",
            "alarm": "--"
        }
        self.last_sensor_update_time = 0

        # Hysteresis state: her kamera için parmak önceki durumu
        self._prev_fingers = {}

        for cam_id in self.camera_ids:
            cap = cv2.VideoCapture(cam_id)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            if cap.isOpened():
                self.caps.append(cap)
                self.menu_systems[cam_id] = GestureStateMachine()
                self.last_face_name[cam_id] = "none"
                self.last_gesture_cmd[cam_id] = ""
                self.last_publish_time[cam_id] = 0
                self.face_frame_counters[cam_id] = 0
                self.cached_face_data[cam_id] = (False, [], [])
                self._prev_fingers[cam_id] = {"Right": [0]*5, "Left": [0]*5}
                print(f"Kamera {cam_id} acildi")
            else:
                cap.release()
                print(f"Kamera {cam_id} bulunamadi, atlaniyor")

        if not self.caps:
            print("Hicbir kamera bulunamadi!")
            self.running = False

    def start(self):
        if not self.running:
            return

        print(f"{len(self.caps)} kamera ile calisiliyor...")
        print("Kontroller: [q] cikis, [r] yuz kaydet, [d] debug toggle")

        frame_count = 0
        show_debug = False

        while self.running:
            all_closed = True
            for i, cap in enumerate(self.caps):
                if not cap.isOpened():
                    continue
                all_closed = False

                success, img = cap.read()
                if not success:
                    continue

                # Ayna efekti
                if CAMERA_FLIP:
                    img = cv2.flip(img, 1)

                cam_id = self.camera_ids[i]
                frame_count += 1
                self.face_frame_counters[cam_id] += 1

                if self.face_frame_counters[cam_id] % FACE_RECOGNIZE_EVERY_N_FRAMES == 0:
                    face_present = self.face_recognizer.recognize(img)
                    self.cached_face_data[cam_id] = (
                        face_present,
                        self.face_recognizer.face_locations[:],
                        self.face_recognizer.face_names[:],
                    )
                else:
                    self.face_recognizer.face_locations = self.cached_face_data[cam_id][1][:]
                    self.face_recognizer.face_names = self.cached_face_data[cam_id][2][:]

                self.face_recognizer.draw_faces(img)

                face_present = self.cached_face_data[cam_id][0]
                face_names = self.cached_face_data[cam_id][2]

                if not self.is_registering:
                    if not face_present or "unknown" in face_names:
                        cv2.putText(img, "Yuz Taninmadi!", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    else:
                        face_name = face_names[0] if face_names else "unknown"
                        if face_name != self.last_face_name.get(cam_id):
                            self.mqtt.publish_face(face_name)
                            self.last_face_name[cam_id] = face_name

                        hands_data = self._detect_hands(img, cam_id)
                        
                        # Custom styled neon skeleton drawing
                        self._draw_tips(img, hands_data)
                        for hd in hands_data:
                            lm = hd["lmList"]
                            if lm:
                                for conn in self.mp_hands.HAND_CONNECTIONS:
                                    p1 = lm[conn[0]]
                                    p2 = lm[conn[1]]
                                    # Right hand (Menu) in Cyan, Left hand (Analog) in Orange/Gold
                                    color = (255, 230, 0) if hd["type"] == "Right" else (0, 136, 255)
                                    cv2.line(img, tuple(p1), tuple(p2), color, 2, cv2.LINE_AA)

                        menu = self.menu_systems[cam_id]
                        self._draw_hand_labels(img, hands_data, menu)

                        cmd = menu.process(hands_data)

                        # Eger menu degilse ve parmaklar aciksa sayi goster (Hizli tepki ve sifirlama ile)
                        if not menu.in_menu:
                            if hands_data:
                                if menu._voted_count >= config.VOTE_MIN_AGREEMENT:
                                    finger_count = sum(menu._voted_fingers)
                                    if finger_count > 0 and not menu._is_confirm(menu._voted_fingers):
                                        display_cmd = f"FINGERS_{finger_count}"
                                        if display_cmd != self.last_gesture_cmd.get(cam_id):
                                            now = time.time()
                                            if now - self.last_publish_time.get(cam_id, 0) >= PUBLISH_COOLDOWN:
                                                self.mqtt.publish_gesture(display_cmd)
                                                print(f"[Kamera {cam_id}] {face_name}: {display_cmd} (oy:{menu._voted_count})")
                                                self.last_gesture_cmd[cam_id] = display_cmd
                                                self.last_publish_time[cam_id] = now
                                    elif finger_count == 0:
                                        if self.last_gesture_cmd.get(cam_id) != "FINGERS_0":
                                            self.mqtt.publish_gesture("FINGERS_0")
                                            self.last_gesture_cmd[cam_id] = "FINGERS_0"
                            else:
                                # El tamamen kaybolduysa segmenti anında sıfırla ve önbelleği temizle
                                if self.last_gesture_cmd.get(cam_id) != "FINGERS_0" and self.last_gesture_cmd.get(cam_id, "").startswith("FINGERS_"):
                                    self.mqtt.publish_gesture("FINGERS_0")
                                    self.last_gesture_cmd[cam_id] = "FINGERS_0"
                                elif not hands_data:
                                    self.last_gesture_cmd[cam_id] = ""

                        if cmd and cmd != self.last_gesture_cmd.get(cam_id):
                            now = time.time()
                            if now - self.last_publish_time.get(cam_id, 0) >= PUBLISH_COOLDOWN:
                                self.mqtt.publish_gesture(cmd)
                                print(f"[Kamera {cam_id}] {face_name}: {cmd}")
                                self.last_gesture_cmd[cam_id] = cmd
                                self.last_publish_time[cam_id] = now

                        self._draw_status(img, menu, cam_id)

                        # Debug overlay
                        if show_debug:
                            self._draw_debug(img, hands_data, menu, cam_id)



                cv2.imshow(f"FingersUP - Kamera {cam_id}", img)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r') and not self.is_registering:
                if self.caps:
                    self._register_face_from_camera(self.caps[0], self.camera_ids[0])
            elif key == ord('d'):
                show_debug = not show_debug
                print(f"Debug overlay: {'ACIK' if show_debug else 'KAPALI'}")

            if all_closed:
                break

        self.stop()

    def _draw_status(self, img, menu, cam_id):
        is_menu = menu.in_menu
        
        # 1. Status Card (Top Right) - Telemetry & Active User
        face_name = "MISAFIR"
        if hasattr(self, "cached_face_data") and cam_id in self.cached_face_data:
            face_names = self.cached_face_data[cam_id][2]
            if face_names:
                face_name = face_names[0]
                
        card_w, card_h = 240, 100
        card_x = img.shape[1] - card_w - 10
        card_y = 10
        
        # Draw status card background (semi-transparent dark)
        overlay = img.copy()
        cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h), (25, 20, 15), -1)
        cv2.addWeighted(overlay, 0.5, img, 0.5, 0, dst=img)
        
        # Border for Status Card
        color_card = (0, 255, 136) if face_name != "unknown" and face_name != "MISAFIR" else (0, 0, 255)
        cv2.rectangle(img, (card_x, card_y), (card_x + card_w, card_y + card_h), color_card, 1)
        
        # Display face name
        cv2.putText(img, f"KULLANICI: {face_name.upper()}", (card_x + 10, card_y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color_card, 1, cv2.LINE_AA)
        
        # Sensor verileri (MQTT'den oku ve cache'e kaydet)
        import time
        status_txt = f"MQTT: BAGLANTI YOK | CAM: {cam_id}"
        temp_txt = f"Sicaklik: {self.cached_sensor_data['sicaklik']} C"
        ldr_txt = f"Isik (LDR): {self.cached_sensor_data['isik']}"
        dist_txt = f"Mesafe: {self.cached_sensor_data['mesafe']} cm"
        ir_txt = f"IR: {self.cached_sensor_data['ir']}"
        led_txt = f"LED: K:{self.cached_sensor_data['ledler'].get('r', '--')} | Y:{self.cached_sensor_data['ledler'].get('g', '--')} | M:{self.cached_sensor_data['ledler'].get('b', '--')}"
        
        # MQTT bağlı ve sensor verisi varsa güncelle
        if hasattr(self, "mqtt"):
            if self.mqtt.client and self.mqtt.client.is_connected():
                status_txt = f"MQTT: ONLINE | CAM: {cam_id}"
                
            if self.mqtt.esp32_status:
                st = self.mqtt.esp32_status
                if isinstance(st, dict):
                    # Sensor verilerini cache'e kaydet (kalıcı tutmak için)
                    if "sicaklik" in st:
                        self.cached_sensor_data["sicaklik"] = f"{st['sicaklik']:.1f}"
                        self.last_sensor_update_time = time.time()
                    if "isik" in st:
                        self.cached_sensor_data["isik"] = str(st['isik'])
                    if "mesafe" in st:
                        self.cached_sensor_data["mesafe"] = str(st['mesafe'])
                    if "ir" in st:
                        self.cached_sensor_data["ir"] = "SINYAL" if st['ir'] else "BEKLE"
                    if "ledler" in st:
                        leds = st["ledler"]
                        if isinstance(leds, dict):
                            self.cached_sensor_data["ledler"]["r"] = "ACIK" if int(leds.get("r", 0)) == 1 else "KAPA"
                            self.cached_sensor_data["ledler"]["g"] = "ACIK" if int(leds.get("g", 0)) == 1 else "KAPA"
                            self.cached_sensor_data["ledler"]["b"] = "ACIK" if int(leds.get("b", 0)) == 1 else "KAPA"
                    
                    # Cache'lenmiş verileri kullan
                    temp_txt = f"Temp: {self.cached_sensor_data['sicaklik']} C"
                    ldr_txt = f"LDR: {self.cached_sensor_data['isik']}"
                    dist_txt = f"Dist: {self.cached_sensor_data['mesafe']} cm"
                    ir_txt = f"IR: {self.cached_sensor_data['ir']}"
                    r_st = self.cached_sensor_data['ledler'].get("r", "KAPA")
                    g_st = self.cached_sensor_data['ledler'].get("g", "KAPA")
                    b_st = self.cached_sensor_data['ledler'].get("b", "KAPA")
                    led_txt = f"LED: K:{r_st} | Y:{g_st} | M:{b_st}"
 
        cv2.putText(img, status_txt, (card_x + 10, card_y + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(img, f"{temp_txt} | {ldr_txt}", (card_x + 10, card_y + 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 255, 180), 1, cv2.LINE_AA)
        cv2.putText(img, f"{dist_txt} | {ir_txt}", (card_x + 10, card_y + 73),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(img, led_txt, (card_x + 10, card_y + 88),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 200, 150), 1, cv2.LINE_AA)

        # 2. Side Menu Panel (If menu active)
        if is_menu:
            panel_w = 210
            panel_h = img.shape[0] - 20
            
            overlay_m = img.copy()
            cv2.rectangle(overlay_m, (10, 10), (10 + panel_w, 10 + panel_h), (25, 20, 15), -1)
            cv2.addWeighted(overlay_m, 0.5, img, 0.5, 0, dst=img)
            
            # Glowing border for panel
            border_c = (255, 212, 0) # Cyan
            cv2.rectangle(img, (10, 10), (10 + panel_w, 10 + panel_h), border_c, 1)
            
            # Title
            cv2.putText(img, "FingersUP MENU", (20, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
            cv2.line(img, (15, 42), (10 + panel_w - 5, 42), (80, 80, 80), 1)
            
            y = 70
            if menu.current_menu == 0:
                # Main Menu
                cv2.putText(img, "ANA MENU", (20, 58),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 136), 1, cv2.LINE_AA)
                            
                for k in sorted(menu.MENU_ITEMS.keys()):
                    name = menu.MENU_ITEMS[k]["name"]
                    is_hovered = (menu.pending_selection == k)
                    
                    if is_hovered:
                        cv2.rectangle(img, (15, y - 14), (10 + panel_w - 5, y + 6), border_c, -1)
                        cv2.putText(img, f"{k}: {name}", (22, y),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
                    else:
                        cv2.putText(img, f"{k}: {name}", (22, y),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 230, 230), 1, cv2.LINE_AA)
                    y += 30
            else:
                # Sub Menu
                menu_info = menu.MENU_ITEMS.get(menu.current_menu, {})
                menu_name = menu_info.get("name", "Alt Menu")
                cv2.putText(img, f"ALT: {menu_name.upper()}", (20, 58),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 136), 1, cv2.LINE_AA)
                
                sub_items = menu_info.get("sub", {})
                for k in sorted(sub_items.keys()):
                    sub_name = sub_items[k]
                    is_hovered = (menu.pending_selection == k)
                    
                    if is_hovered:
                        cv2.rectangle(img, (15, y - 14), (10 + panel_w - 5, y + 6), border_c, -1)
                        cv2.putText(img, f"{k}: {sub_name}", (22, y),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
                    else:
                        cv2.putText(img, f"{k}: {sub_name}", (22, y),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 230, 230), 1, cv2.LINE_AA)
                    y += 30
                    
            # Help text
            cv2.line(img, (15, panel_h - 40), (10 + panel_w - 5, panel_h - 40), (80, 80, 80), 1)
            cv2.putText(img, "Yumruk: ONAY", (20, panel_h - 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
            cv2.putText(img, "2 Yumruk: CIKIS", (20, panel_h - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
                        
        else:
            # Simple bottom status bar when menu is NOT open
            cv2.rectangle(img, (0, img.shape[0] - 28), (img.shape[1], img.shape[0]), (25, 20, 15), -1)
            cv2.putText(img, "FingersUP - Sistem Hazir. Menuye girmek icin BASPARMAK jesti yapin.", (10, img.shape[0] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
                        
        # 3. Draw Analog Slider (Bottom Center)
        analog_val = None
        if menu.last_command and menu.last_command.startswith("ANALOG_"):
            parts = menu.last_command.split("_")
            if len(parts) >= 3:
                try:
                    analog_val = int(parts[2])
                except ValueError:
                    pass
                    
        if analog_val is not None:
            bar_x1, bar_y = 230, img.shape[0] - 45
            bar_x2 = img.shape[1] - 10
            bar_w = bar_x2 - bar_x1
            
            # Background bar
            cv2.rectangle(img, (bar_x1, bar_y), (bar_x2, bar_y + 14), (50, 50, 50), -1)
            
            # Fill width
            filled_w = int(bar_w * (analog_val / 180.0))
            cv2.rectangle(img, (bar_x1, bar_y), (bar_x1 + filled_w, bar_y + 14), (0, 136, 255), -1)
            cv2.rectangle(img, (bar_x1, bar_y), (bar_x2, bar_y + 14), (255, 255, 255), 1)
            
            cv2.putText(img, f"PERDE ACISI: {analog_val} deg", (bar_x1, bar_y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 136, 255), 1, cv2.LINE_AA)

    def _draw_debug(self, img, hands_data, menu, cam_id):
        """Debug overlay — parmak açıları, FSM state, oy durumu."""
        h, w = img.shape[:2]
        base_y = h - 100

        # FSM state
        state_name = menu.debug_state_name
        cv2.putText(img, f"FSM: {state_name}", (w - 200, base_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

        # Voted fingers
        voted = ''.join(map(str, menu._voted_fingers))
        cv2.putText(img, f"Vote: {voted} ({menu._voted_count}/{7})", (w - 200, base_y + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 255, 180), 1)

        # Parmak açıları
        for hand in hands_data:
            if hand["type"] != "Right":
                continue
            angles = hand.get("_angles", [])
            for idx, angle in enumerate(angles):
                label = TIP_LABELS[idx] if idx < len(TIP_LABELS) else "?"
                color = (0, 255, 0) if hand["fingers"][idx] else (0, 0, 255)
                cv2.putText(img, f"{label}:{angle:.0f}", (w - 200, base_y + 36 + idx * 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

    def _draw_hand_labels(self, img, hands_data, menu):
        from publisher.gesture_state_machine import GState
        
        for hand in hands_data:
            if hand["lmList"]:
                x, y = hand["lmList"][0][0], hand["lmList"][0][1]
                fs = ''.join(map(str, hand["fingers"]))
                conf = hand.get("confidence", 0)
                cv2.putText(img, f"{hand['type'][0]} {fs} c:{conf:.0f}%",
                            (x - 15, y - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
                
                # Analog Çubuk (Pinch Visualizer)
                # Sadece Başparmak ve İşaret Parmağı açıksa VE Analog mod aktifse göster
                if hand["fingers"] == [1, 1, 0, 0, 0] and "pinch_pts" in hand:
                    is_analog_active = False
                    if menu.state == GState.MENU_SUB:
                        menu_info = menu.MENU_ITEMS.get(menu.current_menu, {})
                        if menu_info.get("analog", False):
                            is_analog_active = True
                    
                    if is_analog_active:
                        p1, p2 = hand["pinch_pts"]
                        # Çizgi çiz
                        cv2.line(img, tuple(p1), tuple(p2), (0, 255, 255), 3)
                        # Analog değerini yaz (0-180 arası)
                        analog_val = int(hand["spread"] * 180 / 100)
                        cx, cy = (p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2
                        cv2.putText(img, f"{analog_val}", (cx + 10, cy),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    def _register_face_from_camera(self, cap, cam_id):
        import tkinter as tk
        from tkinter import simpledialog

        root = tk.Tk()
        root.withdraw()
        name = simpledialog.askstring("Yuz Kayit", "Kisi adini girin:")
        root.destroy()

        if not name or not name.strip():
            return

        name = name.strip()
        self.is_registering = True
        print(f"Yuz kaydi: {name} - {FACE_SAMPLES_PER_PERSON} ornek")
        samples = 0
        countdown = 0

        while samples < FACE_SAMPLES_PER_PERSON and self.running:
            success, img = cap.read()
            if not success:
                continue

            if CAMERA_FLIP:
                img = cv2.flip(img, 1)

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.face_recognizer.detector.process(rgb)
            detected = results and results.detections

            if detected:
                countdown += 1
                if countdown >= 5:
                    self.face_recognizer.register_face_samples(img, name)
                    samples += 1
                    print(f"  {samples}/{FACE_SAMPLES_PER_PERSON}")
                    cv2.putText(img, f"KAYIT: {samples}/{FACE_SAMPLES_PER_PERSON}", (50, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                    countdown = 0
                    cv2.imshow(f"FingersUP - Kamera {cam_id}", img)
                    cv2.waitKey(300)
            else:
                countdown = 0
                cv2.putText(img, "Yuz gorunmuyor!", (50, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            cv2.putText(img, f"Kayit: {samples}/{FACE_SAMPLES_PER_PERSON}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.imshow(f"FingersUP - Kamera {cam_id}", img)
            k = cv2.waitKey(50) & 0xFF
            if k == ord('q'):
                break

        self.face_recognizer._load_faces()
        for cid in self.camera_ids:
            self.face_frame_counters[cid] = 0
            self.cached_face_data[cid] = (False, [], [])
        print(f"Kayit tamam: {name} ({samples} ornek)")
        self.is_registering = False

    def _detect_hands(self, img, cam_id):
        """
        El algılama — Açı-bazlı parmak tespiti + Hysteresis + Confidence filtre.

        Mevcut Y-koordinat karşılaştırması yerine parmak eklem açılarını
        kullanarak eğik/yan tutulmuş ellerde bile doğru okuma yapar.
        """
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands_detector.process(rgb)
        if not results or not results.multi_hand_landmarks:
            return []

        h, w, _ = img.shape
        hands_data = []

        for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
            # ── Confidence filtresi ──
            classification = handedness.classification[0]
            hand_type = classification.label
            hand_conf = classification.score * 100  # 0-100 arası

            if hand_conf < HAND_CONFIDENCE_THRESHOLD * 100:
                continue  # Düşük güven → bu eli atla

            # Ayna efekti nedeniyle Mediapipe etiketler ters olabilir
            # cv2.flip() sonrası "Right" aslında "Right" kalmalı
            # (flip uyguladıktan sonra Mediapipe doğru etiketler)

            lm_list = []
            for lm in hand_landmarks.landmark:
                lm_list.append([int(lm.x * w), int(lm.y * h)])

            # ── Açı-bazlı parmak algılama ──
            prev = self._prev_fingers.get(cam_id, {}).get(hand_type, [0]*5)
            fingers, angles = self._detect_fingers_by_angle(lm_list, hand_type, prev)

            # Önceki durumu güncelle (hysteresis için)
            if cam_id not in self._prev_fingers:
                self._prev_fingers[cam_id] = {}
            self._prev_fingers[cam_id][hand_type] = fingers[:]

            # ── Pinch (Başparmak - İşaret) Hesabı ──
            # Eski "spread" yerine sadece bu iki parmak arasına bakıyoruz.
            thumb_tip = lm_list[4]
            index_tip = lm_list[8]
            pinch_dist = ((thumb_tip[0] - index_tip[0])**2 + (thumb_tip[1] - index_tip[1])**2)**0.5
            
            # Mesafe kabaca 20px (kapalı) ile 150px (açık) arası değişir. 0-100 arasına map edelim.
            spread = max(0, min(100, int((pinch_dist - 20) / 1.3)))

            hands_data.append({
                "type": hand_type,
                "lmList": lm_list,
                "fingers": fingers,
                "spread": spread,
                "landmarks": hand_landmarks,
                "confidence": hand_conf,
                "pinch_pts": (thumb_tip, index_tip),
                "_angles": angles,  # Debug için
            })

        return hands_data

    def _detect_fingers_by_angle(self, lm_list, hand_type, prev_fingers):
        """
        Açı-bazlı parmak açık/kapalı tespiti.

        Her parmak için MCP→PIP→DIP veya PIP→DIP→TIP açısı hesaplanır.
        Açık parmak ≈ 160-180°, kapalı parmak ≈ 30-100°.
        Hysteresis: açma eşiği > kapama eşiği, arada önceki durum korunur.

        Returns:
            fingers: [0 veya 1] * 5
            angles:  [float] * 5  (debug için)
        """
        fingers = [0, 0, 0, 0, 0]
        angles = [0.0, 0.0, 0.0, 0.0, 0.0]

        for finger_idx in range(5):
            joints = FINGER_JOINTS[finger_idx]  # [MCP, PIP, DIP, TIP]

            if finger_idx == 0:
                # Başparmak için açı hesabı yanıltıcı olabiliyor.
                # Daha sağlam yöntem: Başparmak ucu (4) ile Serçe parmak kökü (17) arası mesafe.
                wrist = lm_list[0]
                index_mcp = lm_list[5]
                pinky_mcp = lm_list[17]
                thumb_tip = lm_list[4]

                # Avuç içi boyutu referansı (Bilek - İşaret Kökü)
                palm_size = ((wrist[0] - index_mcp[0])**2 + (wrist[1] - index_mcp[1])**2)**0.5
                
                # Başparmak ucu ile serçe kökü arası mesafe
                thumb_dist = ((thumb_tip[0] - pinky_mcp[0])**2 + (thumb_tip[1] - pinky_mcp[1])**2)**0.5
                
                # Oran hesapla (Elin kameraya uzaklığından bağımsız)
                ratio = thumb_dist / max(palm_size, 1.0)
                
                # Açı dizisine uyumlu olması için 100 ile çarpıp sahte bir açı gibi gösterelim
                angle = ratio * 100
                angles[0] = angle

                # Oran 1.3'ten büyükse başparmak açık, 1.1'den küçükse kapalı (yumruk)
                open_thresh = 130
                close_thresh = 110
            else:
                # Diğer 4 parmak: MCP→PIP→TIP açısı
                a = lm_list[joints[0]]  # MCP
                b = lm_list[joints[1]]  # PIP
                c = lm_list[joints[3]]  # TIP

                angle = _angle_at_joint(a, b, c)
                angles[finger_idx] = angle

                open_thresh = FINGER_OPEN_ANGLE
                close_thresh = FINGER_CLOSE_ANGLE

            # Hysteresis karar mantığı
            if angle >= open_thresh:
                fingers[finger_idx] = 1
            elif angle <= close_thresh:
                fingers[finger_idx] = 0
            else:
                # Belirsiz bölge → önceki durumu koru
                fingers[finger_idx] = prev_fingers[finger_idx] if finger_idx < len(prev_fingers) else 0

        return fingers, angles

    def _draw_tips(self, img, hands_data):
        for hand in hands_data:
            lm = hand["lmList"]
            if not lm:
                continue
            for i, tip in enumerate(self.finger_tips):
                if tip < len(lm):
                    cx, cy = lm[tip]
                    up = hand["fingers"][i]
                    cv2.circle(img, (cx, cy), 10, TIP_COLORS[i], cv2.FILLED if up else 2)
                    if up:
                        cv2.circle(img, (cx, cy), 10, (255, 255, 255), 2)
                        cv2.putText(img, TIP_LABELS[i], (cx - 5, cy + 4),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)

    def stop(self):
        self.running = False
        for cap in self.caps:
            cap.release()
        self.hands_detector.close()
        cv2.destroyAllWindows()
