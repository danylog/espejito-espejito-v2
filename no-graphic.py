from transformers import AutoImageProcessor, AutoModelForImageClassification
import torch
import cv2
from datetime import datetime
from typing import List, Dict

class CameraFacialEmotionDetector:
    def __init__(self):
        # Load the processor and model with `use_fast=False`
        self.processor = AutoImageProcessor.from_pretrained(
            "prithivMLmods/Facial-Emotion-Detection-SigLIP2", use_fast=False
        )
        self.model = AutoModelForImageClassification.from_pretrained(
            "prithivMLmods/Facial-Emotion-Detection-SigLIP2"
        )
        self.model.eval()  # Set model to evaluation mode
        
        # Define emotion mapping for the model
        self.emotion_mapping = {
            0: 'Surprise',
            1: 'Angry',
            2: 'Happy',
            3: 'Neutral',
            4: 'Sad',
            5: 'Surprise'
        }
        
        # Load the Haar cascade for face detection
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    def detect_faces(self, frame: cv2.Mat) -> List[Dict[str, int]]:
        """
        Detect faces in a video frame using Haar cascades.
        Args:
            frame (cv2.Mat): A single frame from the video
        
        Returns:
            List[Dict[str, int]]: List of bounding boxes for detected faces
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(48, 48))
        return [{'x': x, 'y': y, 'w': w, 'h': h} for (x, y, w, h) in faces]

    def process_face(self, face_roi: cv2.Mat) -> Dict:
        """
        Predict emotions for a cropped face.
        Args:
            face_roi (cv2.Mat): Cropped image of a face
        
        Returns:
            Dict: Predicted top emotion and scores for all emotions
        """
        # Resize face to match model's input size
        face_resized = cv2.resize(face_roi, (224, 224))
        face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
        
        # Convert to tensor
        inputs = self.processor(images=[face_rgb], return_tensors="pt")
        
        # Perform inference
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        # Get the top prediction
        predicted_class = probs.argmax().item()
        confidence = probs[0][predicted_class].item()
        
        # Map predictions to emotions
        predictions = [
            {'emotion': self.emotion_mapping[i], 'confidence': prob.item()}
            for i, prob in enumerate(probs[0])
        ]
        predictions.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            'top_emotion': self.emotion_mapping[predicted_class],
            'confidence': confidence,
            'all_emotions': predictions
        }

    def analyze_camera_feed(self):
        """
        Analyze video frames from the camera and output detected emotions.
        """
        cap = cv2.VideoCapture(0)  # Open the default camera (camera index 0)
        if not cap.isOpened():
            raise RuntimeError("Could not open the camera")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("Failed to capture frame. Exiting...")
                    break
                
                # Detect faces in the frame
                faces = self.detect_faces(frame)
                
                for face in faces:
                    x, y, w, h = face['x'], face['y'], face['w'], face['h']
                    face_roi = frame[y:y+h, x:x+w]
                    
                    # Process face to detect emotion
                    emotions = self.process_face(face_roi)
                    
                    # Output the detected emotions
                    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"Timestamp: {timestamp}")
                    print(f"Face at (x: {x}, y: {y}, w: {w}, h: {h})")
                    print(f"  Top Emotion: {emotions['top_emotion']} ({emotions['confidence']:.2f})")
                    print("  All Emotions:")
                    for emotion in emotions['all_emotions']:
                        print(f"    - {emotion['emotion']}: {emotion['confidence']:.2f}")
                
                # Exit on key press (e.g., 'q')
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("Exiting...")
                    break

        finally:
            cap.release()  # Release the camera

# Example usage
if __name__ == "__main__":
    detector = CameraFacialEmotionDetector()
    
    try:
        print("Starting emotion detection from the camera...")
        print("Press 'q' to stop.")
        detector.analyze_camera_feed()
    except Exception as e:
        print(f"Error: {e}")