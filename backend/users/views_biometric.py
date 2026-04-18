import json
import logging
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
    extract_embedding, verify_face
)

logger = logging.getLogger(__name__)


class BiometricEnrollView(APIView):
    """
    Enrôlement biométrique (sans détection de vivacité)
    """
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
            # Extraire l'embedding
            result = extract_embedding(image_file.read())

            if 'error' in result:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )

            embedding = result.get('embedding')
            if not embedding:
                return Response(
                    {'error': "Impossible d'extraire l'embedding"},
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
        result = verify_face(image_file.read(), stored_embedding)
        if 'error' in result:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )

        similarity = result.get('similarity', 0.0)
        verified = result.get('verified', False)

        if verified:
            refresh = RefreshToken.for_user(user)
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