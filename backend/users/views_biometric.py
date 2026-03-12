import json
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.files.uploadedfile import InMemoryUploadedFile
from .models import User, BiometricProfile
from .utils import (
    encrypt_value, decrypt_value, log_user_activity,
    extract_embedding, verify_face, check_liveness, check_liveness_video
)

logger = logging.getLogger(__name__)

class BiometricEnrollView(APIView):
    """
    Enrôlement biométrique avec détection de vivacité
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        # Vérifier les fichiers
        image_file = request.FILES.get('image')
        if not image_file:
            return Response(
                {'error': 'Image requise'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Optionnel: séquence vidéo pour liveness avancé
        video_file = request.FILES.get('video')  # séquence d'images ou vidéo courte

        try:
            # Étape 1: Vérifier la vivacité si vidéo fournie
            liveness_passed = False
            liveness_score = 0.0
            
            if video_file:
                # Analyse de vivacité par vidéo (clignement, mouvement)
                liveness_result = check_liveness_video(video_file.read())
                if 'error' in liveness_result:
                    return Response(
                        {'error': f"Erreur de détection de vivacité: {liveness_result['error']}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                liveness_passed = liveness_result.get('liveness_passed', False)
                liveness_score = liveness_result.get('score', 0.0)
            else:
                # Analyse de vivacité simple sur une image
                liveness_result = check_liveness(image_file.read())
                if 'error' in liveness_result:
                    return Response(
                        {'error': f"Erreur de détection de vivacité: {liveness_result['error']}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                liveness_passed = liveness_result.get('liveness_passed', False)
                liveness_score = liveness_result.get('score', 0.0)

            if not liveness_passed:
                logger.warning(f"Tentative d'enrôlement avec vivacité échouée: score={liveness_score}")
                return Response(
                    {'error': 'Détection de vivacité échouée. Veuillez réessayer avec un vrai visage.',
                     'liveness_score': liveness_score},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Étape 2: Extraire l'embedding
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

            # Étape 3: Chiffrer et stocker
            encrypted_embedding = encrypt_value(json.dumps(embedding))

            # Mettre à jour ou créer le profil
            profile, created = BiometricProfile.objects.update_or_create(
                user=request.user,
                defaults={
                    'encrypted_embedding': encrypted_embedding,
                    'liveness_score_enrollment': liveness_score  # optionnel: ajouter ce champ
                }
            )

            # Marquer l'utilisateur comme ayant la biométrie activée
            request.user.biometric_enabled = True
            request.user.save(update_fields=['biometric_enabled'])

            # Log l'activité
            log_user_activity(
                request.user,
                'biometric_enroll_success',
                f"Enrôlement biométrique réussi (liveness score: {liveness_score:.2f})",
                request
            )

            return Response({
                'message': 'Profil biométrique enregistré avec succès',
                'created': created,
                'liveness_score': liveness_score
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Erreur lors de l'enrôlement biométrique: {str(e)}")
            return Response(
                {'error': f"Erreur interne: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BiometricLoginView(APIView):
    """
    Connexion biométrique avec détection de vivacité
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        identifier = request.data.get('identifier')
        image_file = request.FILES.get('image')
        
        # Optionnel: vidéo pour liveness
        video_file = request.FILES.get('video')

        if not identifier or not image_file:
            return Response(
                {'error': 'Identifiant et image requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Étape 1: Vérifier la vivacité
            liveness_passed = False
            liveness_score = 0.0
            
            if video_file:
                liveness_result = check_liveness_video(video_file.read())
                if 'error' in liveness_result:
                    return Response(
                        {'error': f"Erreur de détection de vivacité: {liveness_result['error']}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                liveness_passed = liveness_result.get('liveness_passed', False)
                liveness_score = liveness_result.get('score', 0.0)
            else:
                liveness_result = check_liveness(image_file.read())
                if 'error' in liveness_result:
                    return Response(
                        {'error': f"Erreur de détection de vivacité: {liveness_result['error']}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                liveness_passed = liveness_result.get('liveness_passed', False)
                liveness_score = liveness_result.get('score', 0.0)

            if not liveness_passed:
                logger.warning(f"Tentative de connexion avec vivacité échouée: score={liveness_score}")
                return Response(
                    {'error': 'Détection de vivacité échouée. Veuillez réessayer avec un vrai visage.',
                     'liveness_score': liveness_score},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Étape 2: Trouver l'utilisateur
            try:
                if '@' in identifier:
                    user = User.objects.get(email=identifier)
                else:
                    user = User.objects.get(phone=identifier)
            except User.DoesNotExist:
                # Ne pas révéler si l'utilisateur existe
                return Response(
                    {'error': 'Authentification échouée'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Vérifier que l'utilisateur a un profil biométrique
            try:
                profile = user.biometric_profile
            except BiometricProfile.DoesNotExist:
                return Response(
                    {'error': 'Authentification échouée'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Étape 3: Déchiffrer l'embedding stocké
            try:
                stored_embedding = json.loads(decrypt_value(profile.encrypted_embedding))
            except Exception as e:
                logger.error(f"Erreur de déchiffrement pour l'utilisateur {user.id}: {str(e)}")
                return Response(
                    {'error': 'Erreur d\'authentification'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Étape 4: Vérifier la photo avec le microservice
            result = verify_face(image_file.read(), stored_embedding)

            if 'error' in result:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )

            similarity = result.get('similarity', 0.0)
            verified = result.get('verified', False)

            if verified:
                # Générer les tokens JWT
                from rest_framework_simplejwt.tokens import RefreshToken
                refresh = RefreshToken.for_user(user)

                # Logger l'activité
                log_user_activity(
                    user, 'biometric_login_success',
                    f"Connexion biométrique réussie (similitude: {similarity:.2f}, liveness: {liveness_score:.2f})",
                    request
                )

                return Response({
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'phone': user.phone,
                    },
                    'similarity': similarity,
                    'liveness_score': liveness_score
                })
            else:
                # Échec de la vérification
                log_user_activity(
                    user, 'biometric_login_failed',
                    f"Échec de connexion biométrique (similitude: {similarity:.2f})",
                    request
                )
                
                return Response(
                    {'error': 'Visage non reconnu', 'similarity': similarity},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        except Exception as e:
            logger.error(f"Erreur lors de la connexion biométrique: {str(e)}")
            return Response(
                {'error': f"Erreur interne: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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