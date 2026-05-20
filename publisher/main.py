import signal
import sys
from .mqtt_client import MQTTClient
from .camera_manager import CameraManager
from .config import CAMERA_IDS


def run(camera_ids=None):
    mqtt = MQTTClient()
    cam_ids = camera_ids if camera_ids is not None else CAMERA_IDS

    # Filter out non-existent cameras
    import cv2
    available = []
    for cid in cam_ids:
        cap = cv2.VideoCapture(cid)
        if cap.isOpened():
            cap.release()
            available.append(cid)
        else:
            cap.release()
            print(f"Kamera {cid} mevcut degil, atlaniyor")

    if not available:
        print("Hicbir kamera bulunamadi!")
        mqtt.stop()
        return

    print(f"FingersUP Akilli Ev Sistemi Baslatiliyor...")
    print(f"Aktif Kameralar: {available}")

    manager = CameraManager(mqtt, available)

    def signal_handler(sig, frame):
        print("\nKapatiliyor...")
        manager.stop()
        mqtt.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    manager.start()


if __name__ == '__main__':
    run()
