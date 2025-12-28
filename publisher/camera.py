import cv2


class Camera:
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)

    def read(self):
        return self.cap.read()

    def is_opened(self):
        return self.cap.isOpened()

    def release(self):
        try:
            self.cap.release()
        except Exception:
            pass

    def show(self, window_name, img):
        cv2.imshow(window_name, img)

    def wait_key(self, delay=1):
        return cv2.waitKey(delay)

    def destroy(self):
        cv2.destroyAllWindows()
