import random
import json
import base64
import redis
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet
from users.models import UserActivity

# ── Redis connection ──────────────────────────────────────────────────────────
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True
)

# ── OTP functions ────────────────────────────────────────────────────────────
def generate_otp(length=6):
    """Génère un code OTP numérique."""
    return ''.join(str(random.randint(0, 9)) for _ in range(length))

def store_otp(key, otp, ttl=300):
    """Stocke un OTP dans Redis (durée de vie en secondes)."""
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
    En développement : affiche dans la console.
    En production : remplacer par un vrai service SMS (Twilio, etc.)
    """
    print(f"*** SMS OTP for {phone}: {otp} ***")

# ── Activity logging ─────────────────────────────────────────────────────────
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

# ── AI Service client ────────────────────────────────────────────────────────
AI_SERVICE_URL = getattr(settings, 'AI_SERVICE_URL', None)
if not AI_SERVICE_URL:
    raise ImproperlyConfigured("AI_SERVICE_URL must be defined in settings (e.g., 'http://localhost:5001')")

class AIServiceError(Exception):
    pass

def health_check():
    """Vérifie si le service IA est disponible."""
    try:
        response = requests.get(f"{AI_SERVICE_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def detect_face(image_bytes):
    """Détecte le plus grand visage dans une image."""
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    try:
        response = requests.post(f"{AI_SERVICE_URL}/detect", files=files, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}

def extract_embedding(image_bytes):
    """Extrait l'embedding du visage (512 dimensions)."""
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    try:
        response = requests.post(f"{AI_SERVICE_URL}/embed", files=files, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}

def verify_face(image_bytes, reference_embedding):
    """Compare une image avec un embedding stocké."""
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
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}

def compare_two_faces(image_bytes1, image_bytes2):
    """Compare deux images et retourne la similarité."""
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
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}

def verify_id_card(id_card_bytes, selfie_bytes):
    """Vérifie que le selfie correspond à la photo de la pièce d'identité."""
    files = {
        'id_card': ('id_card.jpg', id_card_bytes, 'image/jpeg'),
        'selfie': ('selfie.jpg', selfie_bytes, 'image/jpeg')
    }
    try:
        response = requests.post(f"{AI_SERVICE_URL}/verify-id", files=files, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {'error': f"Erreur de connexion: {str(e)}"}


# ── Encryption utilities (Fernet) ────────────────────────────────────────────
def get_encryption_key():
    """Récupère la clé de chiffrement depuis les settings. Lève une erreur si absente."""
    key = getattr(settings, 'ENCRYPTION_KEY', None)
    if not key:
        raise ImproperlyConfigured(
            "ENCRYPTION_KEY must be set in environment (e.g., .env file). "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return key

_cipher = None

def get_cipher():
    """Singleton Fernet instance."""
    global _cipher
    if _cipher is None:
        key = get_encryption_key()
        _cipher = Fernet(key.encode() if isinstance(key, str) else key)
    return _cipher

def encrypt_value(value):
    """Chiffre une chaîne et retourne en base64."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.encode('utf-8')
    cipher = get_cipher()
    encrypted = cipher.encrypt(value)
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_value(encrypted_value):
    """Déchiffre une valeur base64."""
    if encrypted_value is None:
        return None
    cipher = get_cipher()
    encrypted_bytes = base64.b64decode(encrypted_value.encode('utf-8'))
    decrypted = cipher.decrypt(encrypted_bytes)
    return decrypted.decode('utf-8')

def encrypt_json(data):
    """Chiffre un objet JSON."""
    json_str = json.dumps(data)
    return encrypt_value(json_str)

def decrypt_json(encrypted_value):
    """Déchiffre et retourne un objet JSON."""
    decrypted_str = decrypt_value(encrypted_value)
    return json.loads(decrypted_str)