import random
import json
import base64
import redis
import secrets
import math
import datetime
from difflib import SequenceMatcher
from django.urls import reverse

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet
from users.models import UserActivity
from django.utils import timezone
from .models import PasswordResetToken

# ── Redis connection ──────────────────────────────────────────────────────────
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
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


def generate_password_reset_token(user):
    token = secrets.token_urlsafe(32)
    PasswordResetToken.objects.create(user=user, token=token)
    return token

def send_password_reset_email(user, request):
    token = generate_password_reset_token(user)
    reset_url = request.build_absolute_uri(f'/api/password-reset/confirm/?token={token}')
    subject = "Password Reset Request"
    message = f"Click the link to reset your password: {reset_url}\nThis link expires in 1 hour."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

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

AI_SERVICE_KEY = getattr(settings, 'AI_SERVICE_KEY', None)

def _ai_headers():
    """Returns auth headers for the AI microservice."""
    return {'X-API-Key': AI_SERVICE_KEY} if AI_SERVICE_KEY else {}

def _ai_error(response):
    """Extracts a human-readable error from an AI service error response."""
    try:
        body = response.json()
        return body.get('error') or body.get('detail') or body.get('message') or f"Service IA: HTTP {response.status_code}"
    except Exception:
        return f"Service IA indisponible (HTTP {response.status_code})"

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
        response = requests.post(f"{AI_SERVICE_URL}/detect", files=files, headers=_ai_headers(), timeout=10)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.exceptions.Timeout:
        return {'error': 'Service IA: timeout'}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}

def extract_embedding(image_bytes):
    """Extrait l'embedding du visage (512 dimensions)."""
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    try:
        response = requests.post(f"{AI_SERVICE_URL}/embed", files=files, headers=_ai_headers(), timeout=30)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.exceptions.Timeout:
        return {'error': 'Le service de reconnaissance faciale est temporairement indisponible. Réessayez dans quelques secondes.'}
    except requests.exceptions.ConnectionError:
        return {'error': 'Impossible de joindre le service de reconnaissance faciale.'}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}

def verify_face(image_bytes, reference_embedding):
    """Compare une image avec un embedding stocké."""
    payload = {'image': base64.b64encode(image_bytes).decode('utf-8'), 'embedding': reference_embedding}
    try:
        response = requests.post(f"{AI_SERVICE_URL}/verify", json=payload, headers=_ai_headers(), timeout=15)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}

def compare_two_faces(image_bytes1, image_bytes2):
    """Compare deux images et retourne la similarité."""
    payload = {
        'image1': base64.b64encode(image_bytes1).decode('utf-8'),
        'image2': base64.b64encode(image_bytes2).decode('utf-8'),
    }
    try:
        response = requests.post(f"{AI_SERVICE_URL}/verify", json=payload, headers=_ai_headers(), timeout=15)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}

def verify_id_card(id_card_bytes, selfie_bytes):
    """Vérifie que le selfie correspond à la photo de la pièce d'identité."""
    files = {
        'id_card': ('id_card.jpg', id_card_bytes, 'image/jpeg'),
        'selfie': ('selfie.jpg', selfie_bytes, 'image/jpeg'),
    }
    try:
        response = requests.post(f"{AI_SERVICE_URL}/verify-id", files=files, headers=_ai_headers(), timeout=30)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}


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


# ── Face identification helpers ───────────────────────────────────────────────
def cosine_sim(a, b):
    """Pure-Python cosine similarity between two embedding lists."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def check_liveness(image_bytes):
    """Calls /liveness AI endpoint. Returns {'live': bool, 'score': float} or {'error': str}.
    If the service is unreachable, returns {'error': ...} so callers can degrade gracefully."""
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    try:
        response = requests.post(f"{AI_SERVICE_URL}/liveness", files=files, headers=_ai_headers(), timeout=15)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.exceptions.Timeout:
        return {'error': 'Service IA: timeout'}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}


# ── OCR helpers ───────────────────────────────────────────────────────────────
def extract_card_text(image_bytes):
    """Extracts raw text from an ID card image using pytesseract."""
    try:
        import pytesseract
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img, lang='fra+ara+eng')
    except Exception:
        return ''


def extract_document_info(image_bytes):
    """Extracts structured info from an ID document.
    Tries the AI microservice /extract-document endpoint first,
    then falls back to pytesseract OCR parsing.
    Returns dict: {first_name, last_name, birth_date, expiry_date, doc_number, raw_text}"""
    import re

    # Try AI microservice first
    files = {'image': ('document.jpg', image_bytes, 'image/jpeg')}
    try:
        response = requests.post(
            f"{AI_SERVICE_URL}/extract-document",
            files=files,
            headers=_ai_headers(),
            timeout=30,
        )
        if response.ok:
            data = response.json()
            # Normalise keys so callers get consistent field names
            return {
                'first_name': data.get('first_name') or data.get('prenom'),
                'last_name': data.get('last_name') or data.get('nom'),
                'birth_date': data.get('birth_date') or data.get('date_naissance'),
                'expiry_date': data.get('expiry_date') or data.get('date_expiration'),
                'doc_number': data.get('doc_number') or data.get('numero'),
                'raw_text': data.get('raw_text', ''),
                'source': 'ai',
            }
    except requests.RequestException:
        pass

    # Fallback: pytesseract
    raw_text = extract_card_text(image_bytes)

    date_pattern = r'\b(\d{2}[./]\d{2}[./]\d{4})\b'
    dates = re.findall(date_pattern, raw_text)
    birth_date = dates[0] if len(dates) >= 1 else None
    expiry_date = dates[-1] if len(dates) >= 2 else None

    doc_number = None
    num_match = re.search(r'\b([A-Z0-9]{8,12})\b', raw_text)
    if num_match:
        doc_number = num_match.group(1)

    return {
        'first_name': None,
        'last_name': None,
        'birth_date': birth_date,
        'expiry_date': expiry_date,
        'doc_number': doc_number,
        'raw_text': raw_text,
        'source': 'ocr',
    }


def compare_names(registered_name, ocr_text, threshold=0.65):
    """Checks whether registered_name appears (fuzzy) in OCR text.
    Returns True if found, False if clearly absent, None if text is too short to judge."""
    if not registered_name or not ocr_text:
        return None
    if len(ocr_text.strip()) < 20:
        return None
    name = registered_name.lower().strip()
    text = ocr_text.lower()
    if name in text:
        return True
    n = len(name)
    for i in range(len(text) - n + 1):
        if SequenceMatcher(None, name, text[i:i + n]).ratio() >= threshold:
            return True
    return False


# ── Device auto-registration ──────────────────────────────────────────────────
def auto_register_device(user, request):
    """Creates or updates a TrustedDevice after any successful authentication."""
    from .models import TrustedDevice
    fingerprint = request.META.get('HTTP_X_DEVICE_FINGERPRINT')
    if not fingerprint:
        return
    device_name = request.META.get('HTTP_X_DEVICE_NAME', 'Mobile Device')
    expires_at = timezone.now() + datetime.timedelta(days=30)
    TrustedDevice.objects.update_or_create(
        device_fingerprint=fingerprint,
        defaults={
            'user': user,
            'device_name': device_name,
            'expires_at': expires_at,
        },
    )