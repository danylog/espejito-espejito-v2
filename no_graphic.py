from transformers import AutoImageProcessor, AutoModelForImageClassification
import torch
import cv2
import subprocess
import os
import time
from datetime import datetime
from typing import List, Dict
import uuid

class CameraFacialEmotionDetector:
    def __init__(self):
        self.processor = AutoImageProcessor.from_pretrained(
            "prithivMLmods/Facial-Emotion-Detection-SigLIP2", use_fast=False
        )
        self.model = AutoModelForImageClassification.from_pretrained(
            "prithivMLmods/Facial-Emotion-Detection-SigLIP2"
        )
        self.model.eval()
        self.emotion_mapping = {2: 'Happy', 3: 'Normal', 4: 'Sad'}
        self.target_indices = [2, 3, 4]
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    def detect_faces(self, frame: cv2.Mat) -> List[Dict[str, int]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(48, 48))
        return [{'x': x, 'y': y, 'w': w, 'h': h} for (x, y, w, h) in faces]

    def process_face(self, face_roi: cv2.Mat) -> Dict:
        face_resized = cv2.resize(face_roi, (224, 224))
        face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
        inputs = self.processor(images=[face_rgb], return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        filtered_probs = probs[0][self.target_indices]
        filtered_probs = filtered_probs / filtered_probs.sum()
        return {
            'Happy': filtered_probs[0].item(),
            'Normal': filtered_probs[1].item(),
            'Sad': filtered_probs[2].item()
        }

    def classify_mood(self, happy, normal, sad):
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
        tmp_img_path = f"/tmp/cam_frame_{uuid.uuid4().hex}.jpg"
        print("Using libcamera-still to capture frames... Press 'q' to quit.")

        try:
            while True:
                # Capture a frame using libcamera-still
                cmd = [
                    "libcamera-still", "-n", "-t", "1", "-o", tmp_img_path,
                    "--width", "640", "--height", "480", "--quality", "90"
                ]
                result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if result.returncode != 0 or not os.path.exists(tmp_img_path):
                    print("Failed to capture frame.")
                    continue

                frame = cv2.imread(tmp_img_path)
                if frame is None:
                    print("Failed to read captured frame.")
                    continue

                faces = self.detect_faces(frame)
                if faces:
                    biggest = max(faces, key=lambda f: f['w'] * f['h'])
                    x, y, w, h = biggest['x'], biggest['y'], biggest['w'], biggest['h']
                    face_roi = frame[y:y+h, x:x+w]
                    emotions = self.process_face(face_roi)
                    mood = self.classify_mood(emotions['Happy'], emotions['Normal'], emotions['Sad'])

                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    label = f"{mood}  Happy: {emotions['Happy']*100:.1f}%  Normal: {emotions['Normal']*100:.1f}%  Sad: {emotions['Sad']*100:.1f}%"
                    cv2.putText(frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 200, 0), 2, cv2.LINE_AA)

                    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"Timestamp: {timestamp}")
                    print(f"Face at (x: {x}, y: {y}, w: {w}, h: {h})")
                    print(f"  Mood: {mood}")
                    print(f"  Happy: {emotions['Happy']*100:.2f}%")
                    print(f"  Normal: {emotions['Normal']*100:.2f}%")
                    print(f"  Sad: {emotions['Sad']*100:.2f}%")

                cv2.imshow("Facial Emotion Detection", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

                time.sleep(0.1)  # Delay to avoid overwhelming system
        finally:
            if os.path.exists(tmp_img_path):
                os.remove(tmp_img_path)
            cv2.destroyAllWindows()

if __name__ == "__main__":
    detector = CameraFacialEmotionDetector()
    
    try:
        print("Starting emotion detection from the camera...")
        print("Press 'q' to stop.")
        detector.analyze_camera_feed()
    except Exception as e:
        print(f"Error: {e}")