import datetime
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from .models import IdentityDocument
from .serializers import IdentityDocumentSerializer
from .utils import verify_id_card, extract_card_text, compare_names


class IdentityStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            doc = request.user.identity_document
            expiry_date = doc.expiry_date
            days_until_expiry = None
            if expiry_date:
                days_until_expiry = (expiry_date - datetime.date.today()).days
            return Response({
                'has_document': True,
                'status': doc.status,
                'document_type': doc.document_type,
                'rejection_reason': doc.rejection_reason or None,
                'expiry_date': expiry_date.isoformat() if expiry_date else None,
                'days_until_expiry': days_until_expiry,
            })
        except IdentityDocument.DoesNotExist:
            return Response({'has_document': False, 'status': None, 'document_type': None, 'rejection_reason': None, 'expiry_date': None, 'days_until_expiry': None})


class IdentityUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user

        try:
            existing = user.identity_document
            if existing.status == 'approved':
                # Allow re-upload only if the document has already expired
                if existing.expiry_date and existing.expiry_date < datetime.date.today():
                    existing.delete()
                else:
                    return Response(
                        {'detail': 'Identity already verified.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                existing.delete()
        except IdentityDocument.DoesNotExist:
            pass

        serializer = IdentityDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Read bytes before saving so we can send them to the AI microservice
        front_file = request.FILES.get('front_image')
        selfie_file = request.FILES.get('selfie_image')

        doc_status = 'pending'
        rejection_reason = ''
        reviewed_at = None

        if front_file and selfie_file:
            front_bytes = front_file.read()
            selfie_bytes = selfie_file.read()
            # Reset so the serializer can still save the files
            front_file.seek(0)
            selfie_file.seek(0)

            # OCR: extract text from front image and compare with registered name
            ocr_text = extract_card_text(front_bytes)
            if len(ocr_text.strip()) >= 20:
                last_found = compare_names(user.last_name, ocr_text)
                first_found = compare_names(user.first_name, ocr_text)
                # Only reject when BOTH names are explicitly absent (not just undetermined)
                if last_found is False and first_found is False:
                    doc_status = 'rejected'
                    rejection_reason = "Le nom sur la pièce d'identité ne correspond pas aux informations de votre compte."
                    reviewed_at = timezone.now()

            # AI face verification (skip if already rejected by OCR)
            if doc_status != 'rejected':
                ai_result = verify_id_card(front_bytes, selfie_bytes)
                if 'error' not in ai_result:
                    reviewed_at = timezone.now()
                    if ai_result.get('match'):
                        doc_status = 'approved'
                    else:
                        doc_status = 'rejected'
                        rejection_reason = "Le visage ne correspond pas au document d'identité."
            # If both checks are inconclusive, keep status='pending' for manual admin review

        save_kwargs = {
            'user': user,
            'status': doc_status,
            'rejection_reason': rejection_reason,
        }
        if reviewed_at:
            save_kwargs['reviewed_at'] = reviewed_at

        serializer.save(**save_kwargs)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
