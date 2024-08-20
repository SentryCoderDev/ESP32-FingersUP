import cv2
from cvzone.HandTrackingModule import HandDetector
import paho.mqtt.client as mqtt

cap = cv2.VideoCapture(0)

detector = HandDetector(detectionCon=0.8, maxHands=1)

fingerTip = [4, 8, 12, 16, 20]
fingerVal = [0, 0, 0, 0, 0]
lastData = "00000"

red = (0, 0, 255)
yellow = (0, 255, 255)
blue = (255, 0, 0)
green = (0, 255, 0)
purple = (255, 0, 255)

color = [red, yellow, blue, green, purple]

broker = "broker.emqx.io"
topic = "Sentry"
client = mqtt.Client()
client.connect(broker, 1883, 60)
client.loop_start()

while cap.isOpened():
    success, img = cap.read()
    hands, img = detector.findHands(img)
    
    if hands:
        lmList = hands[0]['lmList']
        
        # Thumb
        handType = hands[0]['type']
        if handType == "Right":
            if lmList[fingerTip[0]][0] > lmList[fingerTip[0] - 1][0]:
                fingerVal[0] = 1
            else:
                fingerVal[0] = 0
        else:
            if lmList[fingerTip[0]][0] < lmList[fingerTip[0] - 1][0]:
                fingerVal[0] = 1
            else:
                fingerVal[0] = 0

        # 4 fingers
        for i in range(1, 5):
            if lmList[fingerTip[i]][1] < lmList[fingerTip[i] - 2][1]:
                fingerVal[i] = 1
            else:
                fingerVal[i] = 0

        # Draw mark
        for i in range(5):
            if fingerVal[i] == 1:
                cv2.circle(img, (lmList[fingerTip[i]][0], lmList[fingerTip[i]][1]), 15,
                           color[i], cv2.FILLED)

        strVal = ''.join(map(str, fingerVal))

        if lastData != strVal:
            client.publish(topic, strVal)
            print(f'Publish Message: {strVal}')
            lastData = strVal

    cv2.imshow("Image", img)
    key = cv2.waitKey(1)
    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
client.loop_stop()
client.disconnect()
