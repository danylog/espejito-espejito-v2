from transformers import AutoImageProcessor, AutoModelForImageClassification
import torch
import cv2
from datetime import datetime
from typing import List, Dict

class CameraFacialEmotionDetector:
    def __init__(self):
        # ...existing model loading code...
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
        # Only convert if frame has 3 channels (color)
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame  # Already grayscale
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
        happy = filtered_probs[0].item()
        normal = filtered_probs[1].item()
        sad = filtered_probs[2].item()
        return {'Happy': happy, 'Normal': normal, 'Sad': sad}

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
        # Use V4L2 backend for Pi Camera (if needed)
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        if not cap.isOpened():
            raise RuntimeError("Could not open the camera (try sudo or check camera connection)")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("Failed to capture frame. Exiting...")
                    break
                faces = self.detect_faces(frame)
                if faces:
                    biggest = max(faces, key=lambda f: f['w'] * f['h'])
                    x, y, w, h = biggest['x'], biggest['y'], biggest['w'], biggest['h']
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
                # Remove all cv2.imshow and waitKey calls
        finally:
            cap.release()
# Example usage
if __name__ == "__main__":
    detector = CameraFacialEmotionDetector()
    
    try:
        print("Starting emotion detection from the camera...")
        print("Press 'q' to stop.")
        detector.analyze_camera_feed()
    except Exception as e:
        print(f"Error: {e}")