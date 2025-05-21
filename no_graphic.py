import cv2
import numpy as np
import os
import time
from datetime import datetime
from typing import List, Dict

from tensorflow.keras.models import load_model

class CameraFacialEmotionDetector:
    MODEL_PATH = "emotion_model.hdf5"  # <-- your .h5 Keras model here
    FACE_SIZE = (64, 64)

    def __init__(self):
        print("[DEBUG] Loading emotion Keras model from:", self.MODEL_PATH)
        self.model = load_model(self.MODEL_PATH, compile=False)
        print("[DEBUG] Loading Haar cascade for face detection...")
        haar_path = (
            "/home/pi/haarcascade_frontalface_default.xml"
            if os.path.exists("/home/pi/haarcascade_frontalface_default.xml")
            else cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.face_cascade = cv2.CascadeClassifier(haar_path)
        print("[DEBUG] Initialization complete.")

    def detect_faces(self, frame: np.ndarray) -> List[Dict[str, int]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=3, minSize=(48, 48)
        )
        return [{'x': x, 'y': y, 'w': w, 'h': h} for (x, y, w, h) in faces]

    def process_face(self, face_roi: np.ndarray) -> Dict[str, float]:
        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, self.FACE_SIZE)
        normalized = resized.astype("float32") / 255.0
        reshaped = np.reshape(normalized, (1, 64, 64, 1))

        preds = self.model.predict(reshaped, verbose=0)[0]  # FER2013: [Angry, Disgust, Fear, Happy, Sad, Surprise, Neutral]

        happy = preds[3]
        normal = preds[6]
        sad = preds[2] + preds[4]  # Fear + Sad (adjust if needed)
        total = happy + normal + sad
        if total > 0:
            happy /= total
            normal /= total
            sad /= total
        return {
            'Happy': float(happy),
            'Normal': float(normal),
            'Sad': float(sad),
        }

    def classify_mood(self, happy, normal, sad) -> str:
        # New thresholds based on your provided values
        if happy >= 0.55:
            return "MUY FELIZ"
        elif happy >= 0.12 and sad < 0.4:
            return "FELIZ"
        elif happy < 0.05 and sad > 0.6:
            return "TRISTE"
        elif happy < 0.05 and sad > 0.5:
            return "MUY TRISTE"
        else:
            return "NORMAL"

    def analyze_camera_feed(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("Cannot open camera")
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.resize(frame, (320, 240))
                faces = self.detect_faces(frame)
                timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

                if faces:
                    f = max(faces, key=lambda r: r['w'] * r['h'])
                    x, y, w, h = f['x'], f['y'], f['w'], f['h']
                    face_roi = frame[y:y+h, x:x+w]
                    emo = self.process_face(face_roi)
                    mood = self.classify_mood(emo['Happy'], emo['Normal'], emo['Sad'])
                    print(f"{timestamp} | {mood} | H:{emo['Happy']:.2f} N:{emo['Normal']:.2f} S:{emo['Sad']:.2f}")
                else:
                    print(f"{timestamp} | No face detected")
                time.sleep(1)
        finally:
            cap.release()

if __name__ == "__main__":
    detector = CameraFacialEmotionDetector()
    print("Press 'q' to exit.")
    detector.analyze_camera_feed()