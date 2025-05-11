from transformers import AutoImageProcessor, AutoModelForImageClassification
import torch
from PIL import Image
import numpy as np
import cv2
from datetime import datetime
from typing import Union, Dict, Tuple

class FacialEmotionDetector:
    def __init__(self):
        # Using AutoImageProcessor instead of AutoProcessor
        self.processor = AutoImageProcessor.from_pretrained("prithivMLmods/Facial-Emotion-Detection-SigLIP2")
        self.model = AutoModelForImageClassification.from_pretrained("prithivMLmods/Facial-Emotion-Detection-SigLIP2")
        
        # Define the specific emotion mapping
        self.emotion_mapping = {
            0: 'Ahegao',
            1: 'Angry',
            2: 'Happy',
            3: 'Neutral',
            4: 'Sad',
            5: 'Surprise'
        }
        
        # Colors for each emotion (BGR format)
        self.emotion_colors = {
            'Ahegao': (255, 192, 203),  # Pink
            'Angry': (0, 0, 255),       # Red
            'Happy': (0, 255, 0),       # Green
            'Neutral': (128, 128, 128),  # Gray
            'Sad': (255, 0, 0),         # Blue
            'Surprise': (0, 255, 255)    # Yellow
        }
        
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    def process_image(self, 
                     image: Union[str, np.ndarray, Image.Image],
                     confidence_threshold: float = 0.5) -> Dict:
        """Process a single image and return emotion predictions"""
        
        # Convert input to PIL Image
        if isinstance(image, str):
            img = Image.open(image)
        elif isinstance(image, np.ndarray):
            img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        elif isinstance(image, Image.Image):
            img = image
        else:
            raise ValueError("Unsupported image format")

        # Process image
        inputs = self.processor(images=img, return_tensors="pt")
        
        # Get predictions
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

        # Get predicted class and probability
        predicted_class = outputs.logits.argmax(-1).item()
        confidence = probs[0][predicted_class].item()
        
        # Get all predictions above threshold
        predictions = []
        for idx, prob in enumerate(probs[0]):
            score = prob.item()
            if score >= confidence_threshold:
                predictions.append({
                    'emotion': self.emotion_mapping[idx],
                    'confidence': score
                })
        
        # Sort by confidence
        predictions.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            'top_emotion': self.emotion_mapping[predicted_class],
            'confidence': confidence,
            'all_emotions': predictions,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    def process_video_stream(self, 
                           source: Union[int, str] = 0,
                           display_results: bool = True,
                           confidence_threshold: float = 0.5):
        """Process video stream (webcam or video file)"""
        cap = cv2.VideoCapture(source)
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            
            # Add timestamp and user info to frame
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            cv2.putText(frame, f"Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): {timestamp}", 
                      (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, "Current User's Login: danylog", 
                      (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            for (x, y, w, h) in faces:
                # Extract face ROI
                face_roi = frame[y:y+h, x:x+w]
                
                try:
                    # Process face for emotion detection
                    results = self.process_image(face_roi, confidence_threshold)
                    
                    if display_results:
                        # Get color for detected emotion
                        emotion_color = self.emotion_colors[results['top_emotion']]
                        
                        # Draw rectangle around face
                        cv2.rectangle(frame, (x, y), (x+w, y+h), emotion_color, 2)
                        
                        # Display emotion and confidence
                        text = f"{results['top_emotion']}: {results['confidence']:.2f}"
                        cv2.putText(frame, text, (x, y-10),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                  emotion_color, 2)
                        
                        # Display all detected emotions
                        y_offset = y + h + 20
                        for emotion in results['all_emotions'][:3]:  # Show top 3 emotions
                            emotion_text = f"{emotion['emotion']}: {emotion['confidence']:.2f}"
                            cv2.putText(frame, emotion_text, (x, y_offset),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                      self.emotion_colors[emotion['emotion']], 1)
                            y_offset += 20
                            
                except Exception as e:
                    print(f"Error processing face: {str(e)}")
                    continue
            
            if display_results:
                cv2.imshow('Facial Emotion Detection', frame)
                
            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        cap.release()
        if display_results:
            cv2.destroyAllWindows()

def main():
    detector = FacialEmotionDetector()
    
    try:
        # Process video stream (webcam)
        detector.process_video_stream(
            source=0,  # Use 0 for webcam
            confidence_threshold=0.5
        )
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()