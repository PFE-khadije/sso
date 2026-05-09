import logging
from django.conf import settings

logger = logging.getLogger(__name__)

_firebase_initialized = False


def _init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return True
    try:
        import firebase_admin
        from firebase_admin import credentials
        if firebase_admin._apps:
            _firebase_initialized = True
            return True
        cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
        if not cred_path:
            logger.warning("FIREBASE_CREDENTIALS_PATH not set — push notifications disabled")
            return False
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        return True
    except Exception as e:
        logger.error(f"Firebase init error: {e}")
        return False


def send_push_notification(user, *, title: str, body: str, data: dict = None):
    """
    Send an FCM push notification to all registered devices of a user.
    Silently no-ops if Firebase is not configured.
    """
    if not _init_firebase():
        return
    try:
        from firebase_admin import messaging
        from .models import FCMToken

        tokens = list(FCMToken.objects.filter(user=user).values_list('token', flat=True))
        if not tokens:
            return

        notification = messaging.Notification(title=title, body=body)
        messages = [
            messaging.Message(notification=notification, data={k: str(v) for k, v in (data or {}).items()}, token=t)
            for t in tokens
        ]
        response = messaging.send_each(messages)

        # Clean up stale tokens
        invalid = {'registration-token-not-registered', 'invalid-registration-token'}
        stale = [
            tokens[i]
            for i, r in enumerate(response.responses)
            if not r.success and any(tag in str(r.exception) for tag in invalid)
        ]
        if stale:
            FCMToken.objects.filter(token__in=stale).delete()

        logger.info(f"FCM: {response.success_count} sent, {response.failure_count} failed for {user.email}")
    except Exception as e:
        logger.error(f"FCM send error: {e}")
