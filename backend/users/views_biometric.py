import json
import logging
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken  
from django.shortcuts import get_object_or_404
from .models import User, BiometricProfile
from .utils import (
    encrypt_value, decrypt_value, log_user_activity,
    extract_embedding, verify_face,
    cosine_sim, auto_register_device,
)

logger = logging.getLogger(__name__)


class BiometricEnrollView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        image_file = request.FILES.get('image')
        if not image_file:
            return Response(
                {'error': 'Image requise'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            image_bytes = image_file.read()

            result = extract_embedding(image_bytes)

            if 'error' in result:
                error_msg = result['error']
                # AI service unavailable / timeout → 503, not 400
                if any(k in error_msg.lower() for k in ('timeout', 'réseau', 'joindre', 'indisponible', 'network')):
                    return Response({'error': error_msg}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

            embedding = result.get('embedding')
            if not embedding:
                return Response(
                    {'error': "Aucun visage détecté. Assurez-vous d'être bien éclairé et regardez la caméra."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Chiffrer et stocker
            encrypted_embedding = encrypt_value(json.dumps(embedding))

            profile, created = BiometricProfile.objects.update_or_create(
                user=request.user,
                defaults={'encrypted_embedding': encrypted_embedding}
            )

            request.user.biometric_enabled = True
            request.user.save(update_fields=['biometric_enabled'])

            log_user_activity(
                request.user,
                'biometric_enroll_success',
                "Enrôlement biométrique réussi",
                request
            )

            return Response({
                'message': 'Profil biométrique enregistré avec succès',
                'created': created
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Erreur lors de l'enrôlement biométrique: {str(e)}")
            return Response(
                {'error': f"Erreur interne: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BiometricLoginView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        identifier = request.data.get('identifier')
        image_file = request.FILES.get('image')

        if not identifier or not image_file:
            return Response(
                {'error': 'Identifiant et image requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find user
        try:
            if '@' in identifier:
                user = User.objects.get(email=identifier)
            else:
                user = User.objects.get(phone=identifier)
        except User.DoesNotExist:
            return Response(
                {'error': 'Authentification échouée'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        image_bytes = image_file.read()

        # Check biometric profile
        try:
            profile = user.biometric_profile
        except BiometricProfile.DoesNotExist:
            return Response(
                {'error': 'Authentification échouée'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Decrypt stored embedding
        try:
            stored_embedding = json.loads(decrypt_value(profile.encrypted_embedding))
        except Exception as e:
            logger.error(f"Erreur de déchiffrement: {str(e)}")
            return Response(
                {'error': 'Erreur d\'authentification'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Verify face
        result = verify_face(image_bytes, stored_embedding)
        if 'error' in result:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )

        similarity = result.get('similarity', 0.0)
        verified = result.get('verified', False)

        if verified:
            refresh = RefreshToken.for_user(user)
            auto_register_device(user, request)
            log_user_activity(user, 'biometric_login_success', f"Connexion biométrique réussie (similarité: {similarity:.2f})", request)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'phone': str(user.phone) if user.phone else None,   
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
                'similarity': similarity
            })
        else:
            log_user_activity(user, 'biometric_login_failed', f"Échec connexion biométrique (similarité: {similarity:.2f})", request)
            return Response(
                {'error': 'Visage non reconnu', 'similarity': similarity},
                status=status.HTTP_401_UNAUTHORIZED
            )


class BiometricStatusView(APIView):
    """
    Vérifie si l'utilisateur a un profil biométrique
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = request.user.biometric_profile
            return Response({
                'enrolled': True,
                'created_at': profile.created_at,
                'updated_at': profile.updated_at
            })
        except BiometricProfile.DoesNotExist:
            return Response({'enrolled': False})


class BiometricDeleteView(APIView):
    """
    Supprime le profil biométrique de l'utilisateur
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        try:
            profile = request.user.biometric_profile
            profile.delete()
            request.user.biometric_enabled = False
            request.user.save(update_fields=['biometric_enabled'])

            log_user_activity(
                request.user,
                'biometric_delete',
                "Suppression du profil biométrique",
                request
            )

            return Response({'message': 'Profil biométrique supprimé'})
        except BiometricProfile.DoesNotExist:
            return Response({'error': 'Aucun profil trouvé'}, status=status.HTTP_404_NOT_FOUND)


@method_decorator(ratelimit(key='ip', rate='20/m', method='POST', block=True), name='post')
class BiometricIdentifyView(APIView):
    """1-to-N face identification — no identifier required.
    Searches all enrolled users by cosine similarity."""
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    THRESHOLD = 0.65

    def post(self, request):
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'error': 'Image requise'}, status=status.HTTP_400_BAD_REQUEST)

        image_bytes = image_file.read()

        # Extract embedding from the query image
        emb_result = extract_embedding(image_bytes)
        if 'error' in emb_result:
            return Response({'error': emb_result['error']}, status=status.HTTP_400_BAD_REQUEST)
        query_emb = emb_result.get('embedding')
        if not query_emb:
            return Response({'error': "Impossible d'extraire l'embedding"}, status=status.HTTP_400_BAD_REQUEST)

        # Search all enrolled users
        best_user = None
        best_sim = 0.0
        for profile in BiometricProfile.objects.select_related('user').all():
            try:
                stored_emb = json.loads(decrypt_value(profile.encrypted_embedding))
                sim = cosine_sim(query_emb, stored_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_user = profile.user
            except Exception:
                continue

        if best_user and best_sim >= self.THRESHOLD:
            refresh = RefreshToken.for_user(best_user)
            auto_register_device(best_user, request)
            log_user_activity(
                best_user,
                'identify_login_success',
                f"Identification faciale 1-to-N réussie (sim: {best_sim:.2f})",
                request,
            )
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': best_user.id,
                    'email': best_user.email,
                    'phone': str(best_user.phone) if best_user.phone else None,
                    'first_name': best_user.first_name,
                    'last_name': best_user.last_name,
                },
                'similarity': best_sim,
            })

        return Response(
            {'error': 'Visage non reconnu. Assurez-vous d\'être bien enrôlé.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )
