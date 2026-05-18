"""
FingersUP — Eski Gesture Processor (Deprecated)

Bu modül geriye uyumluluk için korunmuştur.
Yeni kod gesture_state_machine.py kullanır.

MenuSystem sınıfı artık GestureStateMachine'e yönlendirilir.
"""

import warnings
from .gesture_state_machine import GestureStateMachine


class MenuSystem(GestureStateMachine):
    """
    Geriye uyumlu sarmalayıcı.
    Eski kodda `MenuSystem()` olarak kullanılıyorsa
    otomatik olarak yeni FSM'e yönlendirir.
    """

    def __init__(self):
        warnings.warn(
            "MenuSystem kullanımdan kaldırıldı. GestureStateMachine kullanın.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__()
