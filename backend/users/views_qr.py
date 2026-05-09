import io
import base64
import qrcode
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .models import QRLoginToken


class QRLoginGenerateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        QRLoginToken.objects.filter(expires_at__lt=timezone.now()).delete()
        token_obj = QRLoginToken.objects.create(
            expires_at=timezone.now() + timedelta(minutes=3),
        )
        qr = qrcode.make(str(token_obj.token))
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode()
        return Response({
            'token': str(token_obj.token),
            'qr_code': f'data:image/png;base64,{qr_b64}',
            'expires_at': token_obj.expires_at.isoformat(),
        })


class QRLoginConfirmView(APIView):
    """Called by the authenticated mobile app to approve a pending QR session."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token_str = request.data.get('token')
        if not token_str:
            return Response({'error': 'token requis'}, status=400)
        try:
            token_obj = QRLoginToken.objects.get(
                token=token_str,
                status='pending',
                expires_at__gt=timezone.now(),
            )
        except QRLoginToken.DoesNotExist:
            return Response({'error': 'QR invalide ou expiré'}, status=400)
        token_obj.user = request.user
        token_obj.status = 'confirmed'
        token_obj.save()
        return Response({'message': 'Connexion approuvée'})


class QRLoginStatusView(APIView):
    """Polled by the desktop browser to check if the QR was scanned."""
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            token_obj = QRLoginToken.objects.select_related('user').get(token=token)
        except QRLoginToken.DoesNotExist:
            return Response({'status': 'invalid'}, status=404)

        if token_obj.status == 'pending' and token_obj.expires_at < timezone.now():
            token_obj.status = 'expired'
            token_obj.save()
            return Response({'status': 'expired'})

        if token_obj.status == 'confirmed' and token_obj.user:
            refresh = RefreshToken.for_user(token_obj.user)
            token_obj.status = 'expired'
            token_obj.save()
            return Response({
                'status': 'confirmed',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {'id': token_obj.user.id, 'email': token_obj.user.email},
            })

        return Response({'status': token_obj.status})
