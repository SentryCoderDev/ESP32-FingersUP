import cv2
from cvzone.HandTrackingModule import HandDetector


class Detector:
    def __init__(self, detectionCon=0.8, maxHands=1):
        self.detector = HandDetector(detectionCon=detectionCon, maxHands=maxHands)
        self.fingerTip = [4, 8, 12, 16, 20]

    def find(self, img):
        hands, img = self.detector.findHands(img)
        return hands, img

    def calc_finger_values(self, hands):
        fingerVal = [0, 0, 0, 0, 0]
        if not hands:
            return fingerVal, None

        lmList = hands[0]["lmList"]
        handType = hands[0]["type"]

        # Thumb
        if handType == "Right":
            if lmList[self.fingerTip[0]][0] > lmList[self.fingerTip[0] - 1][0]:
                fingerVal[0] = 1
        else:
            if lmList[self.fingerTip[0]][0] < lmList[self.fingerTip[0] - 1][0]:
                fingerVal[0] = 1

        # 4 fingers
        for i in range(1, 5):
            if lmList[self.fingerTip[i]][1] < lmList[self.fingerTip[i] - 2][1]:
                fingerVal[i] = 1

        return fingerVal, lmList

    def draw_marks(self, img, lmList, fingerVal):
        color = [(0, 0, 255), (0, 255, 255), (255, 0, 0), (0, 255, 0), (255, 0, 255)]
        if lmList:
            for i in range(5):
                if fingerVal[i] == 1:
                    cv2.circle(img, (lmList[self.fingerTip[i]][0], lmList[self.fingerTip[i]][1]), 15,
                               color[i], cv2.FILLED)
        return img
