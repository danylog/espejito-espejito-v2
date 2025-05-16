from transformers import AutoImageProcessor, AutoModelForImageClassification
import torch
import cv2
import time
from datetime import datetime
from typing import List, Dict

class CameraFacialEmotionDetector:
    def __init__(self):
        print("[DEBUG] Initializing processor and model...")
        self.processor = AutoImageProcessor.from_pretrained(
            "prithivMLmods/Facial-Emotion-Detection-SigLIP2", use_fast=False
        )
        self.model = AutoModelForImageClassification.from_pretrained(
            "prithivMLmods/Facial-Emotion-Detection-SigLIP2"
        )
        self.model.eval()
        self.emotion_mapping = {2: 'Happy', 3: 'Normal', 4: 'Sad'}
        self.target_indices = [2, 3, 4]
        print("[DEBUG] Loading Haar cascade for face detection...")
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        print("[DEBUG] Initialization complete.")

    def detect_faces(self, frame: cv2.Mat) -> List[Dict[str, int]]:
        print("[DEBUG] Detecting faces in frame...")
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame  # Already grayscale
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=3, minSize=(48, 48)
        )
        print(f"[DEBUG] Found {len(faces)} face(s).")
        return [{'x': x, 'y': y, 'w': w, 'h': h} for (x, y, w, h) in faces]

    def process_face(self, face_roi: cv2.Mat) -> Dict:
        print("[DEBUG] Processing face ROI for emotion prediction...")
        face_resized = cv2.resize(face_roi, (224, 224))
        face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
        inputs = self.processor(images=[face_rgb], return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        filtered_probs = probs[0][self.target_indices]
        filtered_probs = filtered_probs / filtered_probs.sum()
        happy = filtered_probs[0].item()
        normal = filtered_probs[1].item()
        sad = filtered_probs[2].item()
        print(f"[DEBUG] Emotion probabilities - Happy: {happy:.4f}, Normal: {normal:.4f}, Sad: {sad:.4f}")
        return {'Happy': happy, 'Normal': normal, 'Sad': sad}

    def classify_mood(self, happy, normal, sad):
        print(f"[DEBUG] Classifying mood from values: Happy={happy}, Normal={normal}, Sad={sad}")
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
        print("[DEBUG] Opening camera...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("Could not open the camera (try sudo or check camera connection)")

        try:
            while True:
                print("[DEBUG] Flushing camera buffer...")
                # Grab and discard the last 5 frames to get the freshest image
                for _ in range(10):
                    cap.read()
                print("[DEBUG] Capturing frame...")
                ret, frame = cap.read()
                if not ret:
                    print("[DEBUG] Failed to capture frame. Exiting...")
                    break

                frame = cv2.resize(frame, (320, 240))
                faces = self.detect_faces(frame)
                if faces:
                    biggest = max(faces, key=lambda f: f['w'] * f['h'])
                    x, y, w, h = biggest['x'], biggest['y'], biggest['w'], biggest['h']
                    print(f"[DEBUG] Biggest face at (x: {x}, y: {y}, w: {w}, h: {h})")
                    face_roi = frame[y:y+h, x:x+w]
                    emotions = self.process_face(face_roi)
                    mood = self.classify_mood(emotions['Happy'], emotions['Normal'], emotions['Sad'])
                    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"Timestamp: {timestamp}")
                    print(f"Face at (x: {x}, y: {y}, w: {w}, h: {h})")
                    print(f"  Mood: {mood}")
                    print(f"  Happy: {emotions['Happy']*100:.2f}%")
                    print(f"  Normal: {emotions['Normal']*100:.2f}%")
                    print(f"  Sad: {emotions['Sad']*100:.2f}%")
                else:
                    print("[DEBUG] No faces detected in this frame.")
                time.sleep(1)
        finally:
            print("[DEBUG] Releasing camera...")
            cap.release()

# Example usage
if __name__ == "__main__":
    detector = CameraFacialEmotionDetector()
    try:
        print("Starting emotion detection from the camera...")
        print("Press Ctrl+C to stop.")
        detector.analyze_camera_feed()
    except Exception as e:
        print(f"Error: {e}")