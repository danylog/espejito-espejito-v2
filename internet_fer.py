import cv2
import numpy as np
from tensorflow.keras.models import load_model

# Load model
model = load_model("emotion_model.hdf5")  # Replace with actual path

# FER2013 standard emotion order
EMOTIONS = ["Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral"]

# Mapped emotions: reduce to Happy, Neutral, Sad
def map_emotions(predictions):
    mapped = {
        "Happy": predictions[3],
        "Neutral": predictions[6],
        "Sad": predictions[0] + predictions[2] + predictions[4],  # Angry + Fear + Sad
    }
    return mapped

# Face detection
face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

def preprocess_face(face_image):
    gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (64, 64))
    normalized = resized.astype("float32") / 255.0
    reshaped = np.reshape(normalized, (1, 64, 64, 1))
    return reshaped

# Start webcam
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_detector.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    for (x, y, w, h) in faces:
        face = frame[y:y+h, x:x+w]
        input_face = preprocess_face(face)

        predictions = model.predict(input_face)[0]
        mapped = map_emotions(predictions)

        # Normalize to percentages
        total = sum(mapped.values())
        percentages = {k: round((v / total) * 100, 2) for k, v in mapped.items()}
        
        # Show result in terminal
        print(f"[Percentages] Happy: {percentages['Happy']}% | Neutral: {percentages['Neutral']}% | Sad: {percentages['Sad']}%")

        # Display main emotion on video
        main_emotion = max(percentages, key=percentages.get)
        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
        cv2.putText(frame, main_emotion, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    cv2.imshow("Emotion Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
