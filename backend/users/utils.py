import random
import redis
import requests
import base64
import json
from django.conf import settings
from django.core.mail import send_mail
from users.models import UserActivity
from cryptography.fernet import Fernet
import os


redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True
)

def generate_otp(length=6):
    """Génère un code OTP numérique de la longueur souhaitée."""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def store_otp(key, otp, ttl=300):  
    """Stocke un OTP dans Redis avec une durée de vie."""
    redis_client.setex(key, ttl, otp)

def verify_otp(key, otp):
    """Vérifie un OTP et le supprime si valide."""
    stored = redis_client.get(key)
    if stored and stored == otp:
        redis_client.delete(key)
        return True
    return False

def send_email_otp(email, otp):
    """Envoie un OTP par email."""
    subject = "Votre code de vérification"
    message = f"Votre code de vérification est : {otp}\nCe code est valable 5 minutes."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])

def send_sms_otp(phone, otp):
    """
    Envoie un OTP par SMS.
    Pour le développement, on affiche simplement dans la console.
    """
    print(f"*** SMS OTP for {phone}: {otp} ***")

def log_user_activity(user, event_type, description, request=None):
   
    ip = None
    user_agent = None
    if request:
        ip = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')

    UserActivity.objects.create(
        user=user,
        event_type=event_type,
        description=description,
        ip_address=ip,
        user_agent=user_agent
    )   


AI_SERVICE_URL = "http://ai_service:5001"  # Nom du service dans docker-compose

class AIServiceError(Exception):
    pass

def health_check():
    """Vérifie si le service IA est disponible"""
    try:
        response = requests.get(f"{AI_SERVICE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def detect_face(image_bytes):
    """
    Détecte un visage dans une image
    Args:
        image_bytes: bytes de l'image
    Returns:
        dict avec 'face_detected' et 'box' ou 'error'
    """
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    try:
        response = requests.post(
            f"{AI_SERVICE_URL}/detect",
            files=files,
            timeout=10
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}

def extract_embedding(image_bytes):
    """
    Extrait l'embedding d'un visage
    Args:
        image_bytes: bytes de l'image
    Returns:
        dict avec 'embedding' ou 'error'
    """
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    try:
        response = requests.post(
            f"{AI_SERVICE_URL}/embed",
            files=files,
            timeout=10
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}

def verify_face(image_bytes, reference_embedding):
    """
    Vérifie une image par rapport à un embedding de référence
    Args:
        image_bytes: bytes de l'image à vérifier
        reference_embedding: liste de floats (embedding de référence)
    Returns:
        dict avec 'similarity', 'verified' ou 'error'
    """
    # Convertir l'image en base64
    img_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    payload = {
        'image': img_base64,
        'embedding': reference_embedding
    }
    
    try:
        response = requests.post(
            f"{AI_SERVICE_URL}/verify",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}

def compare_two_faces(image_bytes1, image_bytes2):
    """
    Compare deux images et retourne la similarité
    Args:
        image_bytes1, image_bytes2: bytes des deux images
    Returns:
        dict avec 'similarity', 'verified' ou 'error'
    """
    img1_base64 = base64.b64encode(image_bytes1).decode('utf-8')
    img2_base64 = base64.b64encode(image_bytes2).decode('utf-8')
    
    payload = {
        'image1': img1_base64,
        'image2': img2_base64
    }
    
    try:
        response = requests.post(
            f"{AI_SERVICE_URL}/verify",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}    
    
def check_liveness(image_bytes):
    """
    Vérifie la vivacité sur une image unique
    Args:
        image_bytes: bytes de l'image
    Returns:
        dict avec 'liveness_passed', 'score', 'details'
    """
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    try:
        response = requests.post(
            f"{AI_SERVICE_URL}/liveness",
            files=files,
            timeout=10
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}

def check_liveness_video(video_bytes):
    """
    Vérifie la vivacité sur une séquence vidéo (plusieurs images)
    Args:
        video_bytes: bytes de la vidéo ou séquence d'images
    Returns:
        dict avec 'liveness_passed', 'score', 'details'
    """
    files = {'video': ('video.mp4', video_bytes, 'video/mp4')}
    try:
        response = requests.post(
            f"{AI_SERVICE_URL}/liveness/video",
            files=files,
            timeout=15
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}


def get_encryption_key():
    """Récupère la clé de chiffrement depuis les settings ou en génère une"""
    key = getattr(settings, 'ENCRYPTION_KEY', None)
    if not key:
        # En développement, on peut générer une clé
        # En production, il faut la définir dans .env
        key = Fernet.generate_key().decode()
        print(f"ATTENTION: ENCRYPTION_KEY non définie. Utilisation d'une clé temporaire: {key}")
    return key

# Initialiser le chiffreur
_cipher = None

def get_cipher():
    """Retourne une instance de Fernet (singleton)"""
    global _cipher
    if _cipher is None:
        key = get_encryption_key()
        _cipher = Fernet(key.encode() if isinstance(key, str) else key)
    return _cipher

def encrypt_value(value):
    """
    Chiffre une valeur (string) et retourne le résultat en base64
    """
    if value is None:
        return None
    cipher = get_cipher()
    # Convertir en bytes si nécessaire
    if isinstance(value, str):
        value = value.encode('utf-8')
    encrypted = cipher.encrypt(value)
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_value(encrypted_value):
    """
    Déchiffre une valeur (string base64) et retourne la valeur originale
    """
    if encrypted_value is None:
        return None
    cipher = get_cipher()
    # Décoder le base64
    encrypted_bytes = base64.b64decode(encrypted_value.encode('utf-8'))
    decrypted = cipher.decrypt(encrypted_bytes)
    return decrypted.decode('utf-8')

def encrypt_json(data):
    """
    Chiffre un objet JSON (le convertit en string puis le chiffre)
    """
    import json
    json_str = json.dumps(data)
    return encrypt_value(json_str)

def decrypt_json(encrypted_value):
    """
    Déchiffre et retourne un objet JSON
    """
    import json
    decrypted_str = decrypt_value(encrypted_value)
    return json.loads(decrypted_str)        