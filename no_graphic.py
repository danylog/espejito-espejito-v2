import os
os.environ["KERAS_BACKEND"] = "jax"

import keras
import cv2
import numpy as np
import time
from datetime import datetime

# Load the Keras model from Hugging Face Hub
model = keras.saving.load_model("hf://FelaKuti/Emotion-detection")

# Index mapping for the model's output
# 0: Happy, 1: Angry, 2: Disgust, 3: Sad, 4: Neutral, 5: Fear, 6: Surprise
EMOTION_LABELS = ["Happy", "Angry", "Disgust", "Sad", "Neutral", "Fear", "Surprise"]
TARGET_INDICES = [0, 3, 4]  # Happy, Sad, Neutral

class CameraFacialEmotionDetector:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

    def detect_faces(self, frame):
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=3, minSize=(48, 48)
        )
        return [{'x': x, 'y': y, 'w': w, 'h': h} for (x, y, w, h) in faces]

    def process_face(self, face_roi):
        face_resized = cv2.resize(face_roi, (48, 48))
        face_gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
        face_norm = face_gray.astype("float32") / 255.0
        face_input = np.expand_dims(face_norm, axis=(0, -1))  # shape: (1, 48, 48, 1)
        preds = model(face_input)
        preds = preds.numpy().flatten()
        # Only keep Happy, Sad, Neutral
        filtered = preds[TARGET_INDICES]
        filtered = filtered / filtered.sum()
        return {
            'Happy': filtered[0],
            'Sad': filtered[1],
            'Neutral': filtered[2]
        }

    def classify_mood(self, happy, neutral, sad):
        diff = happy - sad
        if diff >= 0.4:
            return "MUY FELIZ"
        elif diff >= 0.15:
            return "FELIZ"
        elif diff > -0.15:
            return "NORMAL"
        elif diff > -0.4:
            return "TRISTE"
        else:
            return "MUY TRISTE"

    def analyze_camera_feed(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("Could not open the camera (try sudo or check camera connection)")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("Failed to capture frame. Exiting...")
                    break

                frame = cv2.resize(frame, (320, 240))
                faces = self.detect_faces(frame)
                if faces:
                    biggest = max(faces, key=lambda f: f['w'] * f['h'])
                    x, y, w, h = biggest['x'], biggest['y'], biggest['w'], biggest['h']
                    face_roi = frame[y:y+h, x:x+w]
                    emotions = self.process_face(face_roi)
                    mood = self.classify_mood(emotions['Happy'], emotions['Neutral'], emotions['Sad'])
                    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"Timestamp: {timestamp}")
                    print(f"Face at (x: {x}, y: {y}, w: {w}, h: {h})")
                    print(f"  Mood: {mood}")
                    print(f"  Happy: {emotions['Happy']*100:.2f}%")
                    print(f"  Neutral: {emotions['Neutral']*100:.2f}%")
                    print(f"  Sad: {emotions['Sad']*100:.2f}%")
                time.sleep(5)
        finally:
            cap.release()

if __name__ == "__main__":
    detector = CameraFacialEmotionDetector()
    try:
        print("Starting emotion detection from the camera...")
        print("Press Ctrl+C to stop.")
        detector.analyze_camera_feed()
    except Exception as e:
        print(f"Error: {e}")