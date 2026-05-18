"""
FingersUP — Gesture State Machine (FSM)

Mevcut gesture_processor.py'nin yerini alan,
daha sağlam bir jest algılama ve menü kontrol sistemi.

Durum Geçişleri:
  IDLE → HAND_READY → GESTURE_LOCKED → MENU_MAIN → MENU_SUB → COOLDOWN → IDLE
                    ↘ DIRECT_CMD → COOLDOWN ↗
"""

import time
from enum import Enum, auto
from collections import Counter
from . import config


class GState(Enum):
    """FSM durumları."""
    IDLE = auto()           # El yok veya yüz onaylanmadı
    HAND_READY = auto()     # El algılandı, sabit bekleniyor
    GESTURE_LOCKED = auto() # Jest sabit onaylandı, komut gönderilecek
    MENU_MAIN = auto()      # Ana menü açık, parmakla seçim bekleniyor
    MENU_SUB = auto()       # Alt menü seçimi bekleniyor
    COOLDOWN = auto()       # Komut gönderildi, bekleme süresi


class GestureStateMachine:
    """
    Sonlu durum makinesi (FSM) tabanlı jest algılama sistemi.

    Özellikler:
        - Zaman-bazlı debounce (frame-bazlı değil)
        - Çoğunluk oyu (majority voting) ile titreşim engelleme
        - Hysteresis: state geçişi farklı eşiklerden geçer
        - Timeout koruması: her state'te zaman aşımı var
        - Debug bilgileri: OSD'ye state bilgisi çizilir
    """

    MENU_ITEMS = {
        1: {"name": "Isiklar",   "sub": {1: "Kirmizi LED", 2: "Yesil LED", 3: "Mavi LED", 4: "Oda Isigi"}},
        2: {"name": "Sicaklik",  "sub": {1: "Olcum Al", 2: "Alarm Siniri"}},
        3: {"name": "Guvenlik",  "sub": {1: "Kapi Durumu", 2: "Alarm", 3: "Buzzer"}},
        4: {"name": "Perde",     "sub": {1: "Ac (0)", 2: "Kapat (180)", 3: "45", 4: "90", 5: "135"}, "analog": True},
        5: {"name": "Sistem",    "sub": {1: "Tum Durum", 2: "Segment Test", 3: "Reset"}},
    }

    def __init__(self):
        self.state = GState.IDLE
        self.current_menu = 0
        self.current_sub = 0
        self.pending_selection = 0
        self.last_command = ""

        # Zamanlayıcılar
        self._state_enter_time = time.time()
        self._stable_start = 0.0
        self._confirm_start = 0.0
        self._hand_lost_start_time = 0.0

        # Çoğunluk oyu penceresi
        self._vote_window = []   # Son N frame'in parmak dizisi

        # Sabit parmak dizisi (oy sonucu)
        self._voted_fingers = [0, 0, 0, 0, 0]
        self._voted_count = 0    # Sabit parmak sayısı

        # Menü modunu (in_menu) dışarıya açık tut — display_info uyumu
        self.in_menu = False

        # Debug
        self._debug_info = ""
        self._display_changed = True

    # ── Public API ──────────────────────────────────────

    def process(self, hands_data):
        """
        Her frame çağrılır. Komut varsa string döner, yoksa None.
        """
        now = time.time()
        
        # ── İki elin de THUMB (Onay) olması durumu: Menüden Çıkış (İptal) ──
        if self.in_menu and hands_data and len(hands_data) >= 2:
            # Ghost (hayalet) elleri engellemek için biri sol diğeri sağ el olmalı
            types = {h["type"] for h in hands_data if "type" in h}
            if len(types) >= 2:
                if all(self._is_confirm(h["fingers"]) for h in hands_data):
                    self.in_menu = False
                    self.current_menu = 0
                    self.current_sub = 0
                    self.pending_selection = 0
                    self._transition(GState.COOLDOWN, now)
                    return "CONF_EXIT"

        # ── Primary Hand (Menü) ve Analog Hand Seçimi ──
        primary_hand = None
        analog_hand = None

        if hands_data:
            for h in hands_data:
                if self._is_analog(h["fingers"]):
                    analog_hand = h
                else:
                    if primary_hand is None:
                        primary_hand = h
            
            # Eğer hiçbir şey bulamadıysak ama eller varsa (örneğin iki el de analog)
            if not primary_hand and hands_data:
                primary_hand = hands_data[0]

        fingers = primary_hand["fingers"] if primary_hand else None

        # ── Çoğunluk oyu güncelle ──
        if fingers is not None:
            self._push_vote(fingers)
        else:
            self._vote_window.clear()
            self._voted_fingers = [0, 0, 0, 0, 0]
            self._voted_count = 0

        # ── State machine ──
        result = None

        if self.state == GState.IDLE:
            result = self._handle_idle(now, fingers)

        elif self.state == GState.HAND_READY:
            result = self._handle_hand_ready(now, fingers)

        elif self.state == GState.GESTURE_LOCKED:
            result = self._handle_gesture_locked(now, fingers, analog_hand)

        elif self.state == GState.MENU_MAIN:
            result = self._handle_menu_main(now, fingers)

        elif self.state == GState.MENU_SUB:
            result = self._handle_menu_sub(now, fingers, analog_hand)

        elif self.state == GState.COOLDOWN:
            result = self._handle_cooldown(now, fingers)

        # ── Normal modda (menu dışında) parmak sayısını göster ──
        if not self.in_menu and self._voted_count >= config.VOTE_MIN_AGREEMENT:
            finger_count = sum(self._voted_fingers)
            if finger_count > 0 and not self._is_confirm(self._voted_fingers):
                # Parmak sayısını her frame göster (display updatei için)
                # Fakat MQTT'ye göndermiyoruz, sadece display info güncelleniyor
                self._display_changed = True

        if result:
            self.last_command = result
            self._display_changed = True

        return result

    # ── State Handlers ──────────────────────────────────

    def _handle_idle(self, now, fingers):
        """El algılanırsa HAND_READY'ye geç."""
        if fingers is not None and any(f != 0 for f in (self._voted_fingers if self._voted_count >= 3 else [0])):
            # El var ve en az birkaç frame oy var
            pass
        if fingers is not None:
            self._transition(GState.HAND_READY, now)
        return None

    def _handle_hand_ready(self, now, fingers):
        """El sabit mi? Sabit ise GESTURE_LOCKED'a geç."""
        if fingers is None:
            self._transition(GState.IDLE, now)
            return None

        # Timeout: 5 saniye el görüp sabit jest alamazsa IDLE'a dön
        if now - self._state_enter_time > 5.0:
            self._transition(GState.IDLE, now)
            return None

        # Oylama ile sabit parmak dizisi belirlendi mi?
        if self._voted_count >= config.VOTE_MIN_AGREEMENT:
            
            # SADECE ONAY (Menüye giriş) kabul edilir. (Analog sadece menü içinde)
            if self._is_confirm(self._voted_fingers):
                elapsed_ms = (now - self._stable_start) * 1000
                if self._stable_start == 0:
                    self._stable_start = now
                    return None

                if elapsed_ms >= config.GESTURE_STABLE_MS:
                    self._transition(GState.GESTURE_LOCKED, now)
                    return None
            else:
                self._stable_start = 0.0
        else:
            self._stable_start = 0.0

        return None

    def _handle_gesture_locked(self, now, fingers, analog_hand):
        """Sabit jest belirlendi. Menüye gir."""
        voted = self._voted_fingers[:]

        # Menüye Giriş (Onay Jesti - Sadece Başparmak)
        if self._is_confirm(voted):
            if not self.in_menu:
                self.in_menu = True
                self.current_menu = 0
                self.current_sub = 0
                self.pending_selection = 0
                self._transition(GState.MENU_MAIN, now)
                return "CONF"
            else:
                self._transition(GState.HAND_READY, now)
                return None

        # Doğrudan komutlar iptal
        self._transition(GState.HAND_READY, now)
        return None

    def _handle_menu_main(self, now, fingers):
        """Ana menü açık. Parmak ile seçim bekleniyor."""
        # Timeout
        if now - self._state_enter_time > config.MENU_TIMEOUT_S:
            self.in_menu = False
            self.current_menu = 0
            self._transition(GState.COOLDOWN, now)
            return "MENU_TIMEOUT"

        if fingers is None:
            if self._hand_lost_start_time == 0.0:
                self._hand_lost_start_time = now
            if now - self._hand_lost_start_time > 3.0:
                self.in_menu = False
                self.current_menu = 0
                self.pending_selection = 0
                self._transition(GState.IDLE, now)
            return None
        else:
            self._hand_lost_start_time = 0.0

        # Sadece parmak sayısı ile seçim (Önizleme ve Onaylama)
        if self._voted_count >= config.VOTE_MIN_AGREEMENT:
            count = sum(self._voted_fingers)
            
            # Seçimi onayla (Onay Jesti - Başparmak)
            if self._is_confirm(self._voted_fingers):
                self._stable_start = 0.0
                if self.pending_selection > 0:
                    sel = self.pending_selection
                    self.pending_selection = 0
                    self.current_menu = sel
                    self.in_menu = True  # <-- Kesin True tut!
                    self._transition(GState.MENU_SUB, now)
                    return f"MENU_{self.MENU_ITEMS[sel]['name']}"
                return None

            # Parmak sayısıyla önizleme seçimi (Onay jesti değilse)
            if 1 <= count <= 5 and not self._is_analog(self._voted_fingers):
                elapsed_ms = (now - self._stable_start) * 1000 if self._stable_start > 0 else 0
                if self._stable_start == 0:
                    self._stable_start = now
                    return None
                
                required_ms = config.GESTURE_STABLE_MS
                if self.pending_selection > 0 and count != self.pending_selection:
                    required_ms = config.GESTURE_STABLE_MS * 2.5
                
                if elapsed_ms >= required_ms:
                    if self.pending_selection != count:
                        self.pending_selection = count
                        self._display_changed = True
                    return None
        else:
            self._stable_start = 0.0

        return None

    def _handle_menu_sub(self, now, fingers, analog_hand):
        """Alt menü seçimi bekleniyor."""
        # Timeout
        if now - self._state_enter_time > config.MENU_TIMEOUT_S:
            self.current_menu = 0
            self.in_menu = False
            self._transition(GState.COOLDOWN, now)
            return "MENU_TIMEOUT"

        if fingers is None:
            if self._hand_lost_start_time == 0.0:
                self._hand_lost_start_time = now
            if now - self._hand_lost_start_time > 3.0:
                self.current_menu = 0
                self.pending_selection = 0
                self.in_menu = False
                self._transition(GState.IDLE, now)
            return None
        else:
            self._hand_lost_start_time = 0.0

        # Alt menü seçimi ve Analog kontrolü
        if self._voted_count >= config.VOTE_MIN_AGREEMENT:
            voted = self._voted_fingers[:]
            count = sum(voted)
            
            # Analog Mod Kontrolü
            menu_info = self.MENU_ITEMS.get(self.current_menu, {})
            if menu_info.get("analog", False) and self._is_analog(voted):
                if analog_hand and "spread" in analog_hand:
                    analog_val = int(analog_hand["spread"] * 180 / 100)
                    menu_name = menu_info["name"]
                    # Analog modda state'i koru, sürekli data akmasına izin ver
                    return f"ANALOG_{menu_name}_{analog_val}"
                return None

            # Onay Jesti (Başparmak)
            if self._is_confirm(voted):
                self._stable_start = 0.0
                if self.pending_selection > 0:
                    sel = self.pending_selection
                    sub_items = menu_info.get("sub", {})
                    if sel in sub_items:
                        cmd = f"EXEC_{self.current_menu}_{sel}"
                        self.current_menu = 0
                        self.current_sub = 0
                        self.pending_selection = 0
                        self.in_menu = False
                        self._transition(GState.COOLDOWN, now)
                        return cmd
                    else:
                        self.pending_selection = 0
                return None

            # Önizleme seçimi (Onay ve Analog değilse)
            if 1 <= count <= 5:
                elapsed_ms = (now - self._stable_start) * 1000 if self._stable_start > 0 else 0
                if self._stable_start == 0:
                    self._stable_start = now
                    return None
                
                required_ms = config.GESTURE_STABLE_MS
                if self.pending_selection > 0 and count != self.pending_selection:
                    required_ms = config.GESTURE_STABLE_MS * 2.5
                
                if elapsed_ms >= required_ms:
                    sub_items = self.MENU_ITEMS.get(self.current_menu, {}).get("sub", {})
                    if count in sub_items:
                        if self.pending_selection != count:
                            self.pending_selection = count
                            self._display_changed = True
                    return None
        else:
            self._stable_start = 0.0

        return None

    def _handle_cooldown(self, now, fingers):
        """Komut gönderildi, bekleme süresi."""
        elapsed_ms = (now - self._state_enter_time) * 1000
        if elapsed_ms >= config.GESTURE_COOLDOWN_MS:
            # Cooldown bitti
            if fingers is None or sum(self._voted_fingers) == 0:
                # El yok veya yumruk → IDLE
                if self.in_menu:
                    self._transition(GState.MENU_MAIN, now)
                else:
                    self._transition(GState.IDLE, now)
            else:
                # El hala aktif → HAND_READY'ye geri dön (yumruk beklemeden!)
                if self.in_menu:
                    self._transition(GState.MENU_MAIN, now)
                else:
                    self._transition(GState.HAND_READY, now)
            return None

        # Cooldown sırasında ekstra timeout koruması
        if elapsed_ms > 3000:
            # 3 saniyeyi aştıysa zorla çık (deadlock koruması)
            if self.in_menu:
                self._transition(GState.MENU_MAIN, now)
            else:
                self._transition(GState.IDLE, now)

        return None

    # ── Internal Utilities ──────────────────────────────

    def _transition(self, new_state, now):
        """State geçişi yap. Vote window korunur (sabit parmak bilgisi kaybolmasın)."""
        old = self.state
        self.state = new_state
        self._state_enter_time = now
        self._stable_start = 0.0
        self.pending_selection = 0  # Geçişlerde seçimi sıfırla
        self._hand_lost_start_time = 0.0
        # NOT: _vote_window temizlenMEZ — mevcut oy verisi korunur
        # Sadece cooldown çıkışında veya el kaybolduğunda temizlenir
        self._debug_info = f"{old.name} -> {new_state.name}"
        self._display_changed = True

    def _push_vote(self, fingers):
        """Çoğunluk oyu penceresine yeni frame ekle."""
        key = tuple(fingers)
        self._vote_window.append(key)
        if len(self._vote_window) > config.VOTE_WINDOW_SIZE:
            self._vote_window.pop(0)

        # En sık görülen parmak dizisini bul
        if len(self._vote_window) >= 2:
            counter = Counter(self._vote_window)
            most_common, count = counter.most_common(1)[0]
            self._voted_fingers = list(most_common)
            self._voted_count = count
        else:
            self._voted_fingers = list(key)
            self._voted_count = len(self._vote_window)

    @staticmethod
    def _is_confirm(fingers):
        """Onay jesti: Tüm parmaklar kapalı (Yumruk - Fist)."""
        return sum(fingers) == 0

    @staticmethod
    def _is_analog(fingers):
        """Analog jesti: Sadece Başparmak + İşaret parmağı açık (Thumb + Index)."""
        return (fingers[0] == 1 and fingers[1] == 1
                and fingers[2] == 0 and fingers[3] == 0 and fingers[4] == 0)

    # ── Display Info (OSD uyumu) ────────────────────────

    def get_display_info(self):
        """Ekran üstü durum bilgisi (camera_manager._draw_status ile uyumlu)."""
        lines = []

        state_label = self.state.name
        voted_str = ''.join(map(str, self._voted_fingers))
        vote_ratio = f"{self._voted_count}/{config.VOTE_WINDOW_SIZE}"

        if self.state == GState.IDLE:
            lines.append("Normal Mod - Thumb+Index = Menu")
            lines.append("Parmaklar = LED kontrol")

        elif self.state == GState.HAND_READY:
            lines.append(f"El algilandi [{voted_str}] {vote_ratio}")
            lines.append("Sabit tutun...")

        elif self.state == GState.COOLDOWN:
            lines.append("Komut gonderildi!")
            remaining = max(0, config.GESTURE_COOLDOWN_MS - (time.time() - self._state_enter_time) * 1000)
            lines.append(f"Bekleniyor... {remaining:.0f}ms")

        elif self.state in (GState.GESTURE_LOCKED, GState.MENU_MAIN):
            if self.current_menu == 0:
                lines.append("MENU - Parmakla sec, YUMRUK onay")
                for k, v in self.MENU_ITEMS.items():
                    prefix = ">>" if self.pending_selection == k else "  "
                    lines.append(f"{prefix} {k}: {v['name']}")
                lines.append("Iki el YUMRUK = Cikis")
            else:
                name = self.MENU_ITEMS[self.current_menu]["name"]
                lines.append(f"[{name}] Alt komut sec, YUMRUK onay")
                sub = self.MENU_ITEMS[self.current_menu]["sub"]
                for k, v in sub.items():
                    prefix = ">>" if self.pending_selection == k else "  "
                    lines.append(f"{prefix} {k}: {v}")
                lines.append("Iki el YUMRUK = Cikis")

        elif self.state == GState.MENU_SUB:
            if self.current_menu in self.MENU_ITEMS:
                name = self.MENU_ITEMS[self.current_menu]["name"]
                lines.append(f"[{name}] Alt komut sec, YUMRUK onay")
                sub = self.MENU_ITEMS[self.current_menu]["sub"]
                for k, v in sub.items():
                    prefix = ">>" if self.pending_selection == k else "  "
                    lines.append(f"{prefix} {k}: {v}")
                if self.MENU_ITEMS[self.current_menu].get("analog"):
                    lines.append("ANALOG (Thumb+Index) AKTIF")
                lines.append(f"[{voted_str}] {vote_ratio}")

        # Debug satırı
        if self._debug_info:
            lines.append(f"DBG: {self._debug_info}")

        return lines

    def menu_just_changed(self):
        """Menü durumu değişti mi? (display güncelleme için)."""
        if self._display_changed:
            self._display_changed = False
            return True
        return False

    @property
    def debug_state_name(self):
        """Debug için mevcut state adı."""
        return self.state.name
