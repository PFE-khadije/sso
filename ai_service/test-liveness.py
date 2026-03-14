import cv2
import requests
import time
import numpy as np
import sys

# URL de votre microservice
MICROSERVICE_URL = "http://localhost:5001/liveness"

def capture_frames(num_frames=5, delay=0.2):
    """
    Capture plusieurs frames depuis la webcam.
    Retourne une liste d'images (bytes) encodées en JPEG.
    """
    cap = cv2.VideoCapture(0)  # 0 = première webcam
    frames = []
    print("Préparez-vous à cligner des yeux...")
    for i in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            print("Erreur de capture")
            break
        # Encoder en JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ret:
            frames.append(('frame'+str(i), buffer.tobytes()))
        time.sleep(delay)
    cap.release()
    return frames

def test_liveness():
    frames = capture_frames(num_frames=5, delay=0.2)
    if not frames:
        print("Aucune frame capturée")
        return
    
    # Préparer la requête multipart
    files = {}
    for name, data in frames:
        files[name] = (name + '.jpg', data, 'image/jpeg')
    
    try:
        response = requests.post(MICROSERVICE_URL, files=files)
        if response.status_code == 200:
            result = response.json()
            print("Résultat :", result)
            if result.get('liveness'):
                print("✅ Liveness détectée (vous êtes vivant !)")
            else:
                print("❌ Échec de la détection de vivacité (clignement non détecté)")
        else:
            print(f"Erreur HTTP {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Erreur de connexion : {e}")

if __name__ == "__main__":
    test_liveness()