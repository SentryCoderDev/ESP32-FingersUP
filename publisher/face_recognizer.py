import os
import cv2
import numpy as np
import mediapipe as mp
from .config import KNOWN_FACES_DIR, FACE_SAMPLES_PER_PERSON, FACE_RECOGNITION_THRESHOLD


class FaceRecognizer:
    def __init__(self):
        self.mp_face = mp.solutions.face_detection
        self.detector = self.mp_face.FaceDetection(model_selection=1, min_detection_confidence=0.6)
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.face_locations = []
        self.face_names = []
        self.labels = {}
        self.label_counter = 0
        self._trained = False
        self._load_faces()

    def _load_faces(self):
        if not os.path.exists(KNOWN_FACES_DIR):
            os.makedirs(KNOWN_FACES_DIR)
            return

        images = []
        labels_list = []
        self.labels = {}
        self.label_counter = 0

        for fname in sorted(os.listdir(KNOWN_FACES_DIR)):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png')) and not fname.endswith('_full.jpg'):
                name = os.path.splitext(fname)[0]
                if '_' in name:
                    name = name.rsplit('_', 1)[0]
                path = os.path.join(KNOWN_FACES_DIR, fname)
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    img = cv2.resize(img, (100, 100))
                    if name not in self.labels:
                        self.labels[name] = self.label_counter
                        self.label_counter += 1
                    images.append(img)
                    labels_list.append(self.labels[name])

        if images:
            self.recognizer.train(images, np.array(labels_list))
            self._trained = True
            print(f"Yuz modeli: {len(self.labels)} kisi, {len(images)} ornek")
        else:
            print("Yuz modeli: kayitli kisi yok")

    def recognize(self, img):
        self.face_locations = []
        self.face_names = []

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.detector.process(rgb)

        if not results or not results.detections:
            return False

        h, w, _ = img.shape
        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            x = max(0, int(bbox.xmin * w))
            y = max(0, int(bbox.ymin * h))
            bw = min(int(bbox.width * w), w - x)
            bh = min(int(bbox.height * h), h - y)

            self.face_locations.append((y, x + bw, y + bh, x))

            if self._trained:
                face_roi = img[y:y + bh, x:x + bw]
                if face_roi.size == 0:
                    self.face_names.append("unknown")
                    continue
                gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (100, 100))
                try:
                    label_id, distance = self.recognizer.predict(gray)
                    name = "unknown"
                    name_guess = "unknown"
                    for n, lid in self.labels.items():
                        if lid == label_id:
                            name_guess = n
                            break
                    if distance < FACE_RECOGNITION_THRESHOLD:
                        name = name_guess
                    
                    self.face_names.append(name)
                    print(f"  Yuz tahmini: {name_guess} (mesafe: {distance:.1f}) -> Sonuc: {name}")
                except Exception as e:
                    print(f"  Tahmin hatasi: {e}")
                    self.face_names.append("unknown")
            else:
                self.face_names.append("unknown")

        return len(self.face_locations) > 0

    def register_face_samples(self, img, name):
        if not os.path.exists(KNOWN_FACES_DIR):
            os.makedirs(KNOWN_FACES_DIR)

        existing_count = sum(1 for f in os.listdir(KNOWN_FACES_DIR)
                            if f.startswith(name + '_') and f.endswith('.jpg')
                            and not f.endswith('_full.jpg'))
        sample_idx = existing_count
        path = os.path.join(KNOWN_FACES_DIR, f"{name}_{sample_idx}.jpg")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (100, 100))
        cv2.imwrite(path, gray)
        self._load_faces()
        return True

    def draw_faces(self, img):
        for (top, right, bottom, left), name in zip(self.face_locations, self.face_names):
            is_known = (name != "unknown")
            color = (0, 255, 136) if is_known else (0, 0, 255) # Green / Red (BGR)
            
            # Draw corner brackets (tech look)
            length = 15
            thickness = 2
            # Top-Left
            cv2.line(img, (left, top), (left + length, top), color, thickness)
            cv2.line(img, (left, top), (left, top + length), color, thickness)
            # Top-Right
            cv2.line(img, (right, top), (right - length, top), color, thickness)
            cv2.line(img, (right, top), (right, top + length), color, thickness)
            # Bottom-Left
            cv2.line(img, (left, bottom), (left + length, bottom), color, thickness)
            cv2.line(img, (left, bottom), (left, bottom - length), color, thickness)
            # Bottom-Right
            cv2.line(img, (right, bottom), (right - length, bottom), color, thickness)
            cv2.line(img, (right, bottom), (right, bottom - length), color, thickness)
            
            # Label
            label = name.upper()
            (w_l, h_l), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            
            # Draw label tag background (filled rect)
            cv2.rectangle(img, (left, top - h_l - 8), (left + w_l + 10, top), color, -1)
            # Draw label text (black text over bright background)
            cv2.putText(img, label, (left + 5, top - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        return img
