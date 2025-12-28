import cv2
from .camera import Camera
from .detector import Detector
from .mqtt_client import MQTTClient


def run(broker='broker.emqx.io', topic='Sentry', src=0):
    cam = Camera(src)
    det = Detector()
    mqttc = MQTTClient(broker, 1883, topic)
    lastData = "00000"

    while cam.is_opened():
        success, img = cam.read()
        if not success:
            break

        hands, img = det.find(img)
        fingerVal, lmList = det.calc_finger_values(hands)

        if lmList:
            img = det.draw_marks(img, lmList, fingerVal)

            strVal = ''.join(map(str, fingerVal))
            if lastData != strVal:
                mqttc.publish(strVal)
                print(f'Publish Message: {strVal}')
                lastData = strVal

        cam.show("Image", img)
        key = cam.wait_key(1)
        if key == ord('q'):
            break

    cam.release()
    cam.destroy()
    mqttc.stop()


if __name__ == '__main__':
    run()
