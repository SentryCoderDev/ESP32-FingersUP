"""
FingersUP — Gesture State Machine Unit Tests (v3, Menu Only & Analog)
"""

import sys
import time
sys.path.insert(0, ".")

from publisher.gesture_state_machine import GestureStateMachine, GState
from publisher import config

# Test için hızlı zamanlama
config.GESTURE_STABLE_MS = 50
config.GESTURE_COOLDOWN_MS = 50
config.CONFIRM_HOLD_MS = 30
config.VOTE_WINDOW_SIZE = 3
config.VOTE_MIN_AGREEMENT = 2

PASS = 0
FAIL = 0

def assert_state(fsm, expected, test_name):
    global PASS, FAIL
    if fsm.state == expected:
        PASS += 1
        print(f"  [PASS] {test_name}: {fsm.state.name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {test_name}: beklenen={expected.name}, gercek={fsm.state.name}")

def make_hand(fingers, spread=50, type="Right"):
    return {"fingers": fingers, "spread": spread, "lmList": [[0,0]]*21, "landmarks": None, "confidence": 95, "type": type}

def feed_frames(fsm, hands_list, n=5, delay=0.02, debug=False):
    """N frame boyunca aynı veriyi gönder."""
    cmd = None
    for i in range(n):
        result = fsm.process(hands_list)
        if debug:
            print(f"    frame {i}: state={fsm.state.name}, voted={fsm._voted_fingers}, "
                  f"vote_count={fsm._voted_count}, stable_start={fsm._stable_start:.3f}, result={result}")
        if result:
            cmd = result
        time.sleep(delay)
    return cmd

# ─── Test 1: Başlangıç durumu ───────────────────────────
print("\n=== Test 1: Baslangic durumu ===")
fsm = GestureStateMachine()
assert_state(fsm, GState.IDLE, "Baslangic IDLE")

# ─── Test 2: El algılama → HAND_READY ──────────────────
print("\n=== Test 2: El algilama ===")
fsm = GestureStateMachine()
hand = make_hand([0, 1, 0, 0, 0])
fsm.process([hand])
assert_state(fsm, GState.HAND_READY, "El goruldu -> HAND_READY")

# ─── Test 3: El kaybolma → IDLE ────────────────────────
print("\n=== Test 3: El kaybolma ===")
fsm.process([])
assert_state(fsm, GState.IDLE, "El kayboldu -> IDLE")

# ─── Test 4: Direct Komutların Yasaklanması ────────────
print("\n=== Test 4: Direct Komut Yasagi (Sadece 3 parmak) ===")
fsm = GestureStateMachine()
hand = make_hand([0, 1, 1, 1, 0])  # 3 Parmak
cmd = feed_frames(fsm, [hand], n=10, delay=0.02)
if cmd is None and fsm.state == GState.HAND_READY:
    PASS += 1
    print(f"  [PASS] Direct komut engellendi, state: {fsm.state.name}")
else:
    FAIL += 1
    print(f"  [FAIL] Komut gitti veya state degisti: cmd={cmd}, state={fsm.state.name}")

# ─── Test 5: Yumruk ile Menü Açma ──────────────────────
print("\n=== Test 5: Menu acma (Yumruk jesti) ===")
fsm = GestureStateMachine()
fist = make_hand([0, 0, 0, 0, 0])
cmd = feed_frames(fsm, [fist], n=10, delay=0.02)
if cmd == "CONF":
    PASS += 1
    print(f"  [PASS] Menu acildi: {cmd}")
    assert_state(fsm, GState.MENU_MAIN, "MENU_MAIN state")
else:
    FAIL += 1
    print(f"  [FAIL] Menu acma beklendi, gelen: {cmd}, state: {fsm.state.name}")

# ─── Test 6: Menüde parmak ile seçim (Fist-to-Confirm) ────────
print("\n=== Test 6: Menu secimi (2 parmak, sonra Yumruk = Sicaklik) ===")
if fsm.state == GState.MENU_MAIN:
    time.sleep(0.05)
    two_fingers = make_hand([0, 1, 1, 0, 0])  # 2 parmak (İşaret + Orta)
    # 2 parmak gönder (önizleme seçimi olacak)
    feed_frames(fsm, [two_fingers], n=10, delay=0.03)
    
    # Seçim pending iken Yumruk gönderip onayla
    fist = make_hand([0, 0, 0, 0, 0])
    cmd = feed_frames(fsm, [fist], n=8, delay=0.03)

    if cmd == "MENU_Sicaklik":
        PASS += 1
        print(f"  [PASS] Menu secildi (Yumruk ile onay): {cmd}")
    else:
        FAIL += 1
        print(f"  [FAIL] Menu secim beklendi, gelen: {cmd}, state: {fsm.state.name}")
else:
    FAIL += 1
    print(f"  [SKIP/FAIL] Menu acik degil, state: {fsm.state.name}")

# ─── Test 7: Analog Gönderimi (Sadece Perde Menüsünde) ──────────
print("\n=== Test 7: Analog Gonderimi (Sadece Perde) ===")
fsm = GestureStateMachine()
# Önce menüyü aç
feed_frames(fsm, [make_hand([0, 0, 0, 0, 0])], n=10, delay=0.02)
# Menü 4'ü (Perde) seçmek için 4 parmak göster
feed_frames(fsm, [make_hand([0, 1, 1, 1, 1])], n=10, delay=0.02)
# Onayla (Yumruk)
feed_frames(fsm, [make_hand([0, 0, 0, 0, 0])], n=8, delay=0.02)

if fsm.state == GState.MENU_SUB and fsm.current_menu == 4:
    # Şimdi Analog (Thumb+Index) jesti yap
    analog_hand = make_hand([1, 1, 0, 0, 0], spread=50) # 50% spread -> 90 derece
    cmd = feed_frames(fsm, [analog_hand], n=10, delay=0.02)
    if cmd == "ANALOG_Perde_90":
        PASS += 1
        print(f"  [PASS] Perde menüsünde Analog gonderildi: {cmd}")
    else:
        FAIL += 1
        print(f"  [FAIL] Analog beklendi, gelen: {cmd}, state: {fsm.state.name}")
else:
    FAIL += 1
    print(f"  [SKIP/FAIL] Perde menusune girilemedi, state: {fsm.state.name}")

# ─── Test 8: İki El Yumruk ile Menüden Çıkış ───────────
print("\n=== Test 8: Iki El Yumruk ile Menuden Cikis ===")
fsm = GestureStateMachine()
fist = make_hand([0, 0, 0, 0, 0]) # Menüyü aç
feed_frames(fsm, [fist], n=10, delay=0.02) 
if fsm.state != GState.MENU_MAIN:
    FAIL += 1
    print("  [FAIL] Menuye girilemedi")
else:
    time.sleep(0.05)
    fist2 = make_hand([0, 0, 0, 0, 0], type="Left")
    cmd2 = feed_frames(fsm, [fist, fist2], n=5, delay=0.02) # İki el yumruk
    if cmd2 == "CONF_EXIT":
        PASS += 1
        print(f"  [PASS] Iki el Yumruk ile cikis yapildi: {cmd2}")
    else:
        FAIL += 1
        print(f"  [FAIL] Cikis beklendi, gelen: {cmd2}, state: {fsm.state.name}")

# ─── Test 9: _is_analog ────────────────────────────────
print("\n=== Test 9: Is_analog kontrolu ===")
assert GestureStateMachine._is_analog([1, 1, 0, 0, 0]) == True
assert GestureStateMachine._is_analog([1, 0, 0, 0, 0]) == False
assert GestureStateMachine._is_analog([0, 1, 1, 0, 0]) == False
assert GestureStateMachine._is_analog([1, 1, 1, 0, 0]) == False
PASS += 1
print(f"  [PASS] _is_analog tum durumlar dogru")

# ─── Sonuc ──────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"SONUC: {PASS} BASARILI / {FAIL} BASARISIZ")
print(f"{'='*50}")

if FAIL > 0:
    sys.exit(1)
