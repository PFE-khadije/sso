from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import IdentityDocument


@receiver(pre_save, sender=IdentityDocument)
def on_identity_status_change(sender, instance, **kwargs):
    if not instance.pk:
        return  # new document, not a status update
    try:
        old = IdentityDocument.objects.get(pk=instance.pk)
    except IdentityDocument.DoesNotExist:
        return

    if old.status == instance.status:
        return

    from .fcm import send_push_notification

    if instance.status == 'approved':
        send_push_notification(
            instance.user,
            title='Identité vérifiée ✓',
            body='Votre document d\'identité a été approuvé. Votre compte est maintenant entièrement vérifié.',
            data={'type': 'identity_approved'},
        )
    elif instance.status == 'rejected':
        reason = instance.rejection_reason or 'Veuillez soumettre à nouveau vos documents.'
        send_push_notification(
            instance.user,
            title='Vérification refusée',
            body=reason,
            data={'type': 'identity_rejected'},
        )
