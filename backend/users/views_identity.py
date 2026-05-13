from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from .models import IdentityDocument
from .serializers import IdentityDocumentSerializer
from difflib import SequenceMatcher
from .utils import verify_id_card, extract_card_text, extract_document_info, compare_names


def _field_match(a, b, threshold=0.65):
    """Direct fuzzy match between two short name strings — no length minimum."""
    if not a or not b:
        return False
    a, b = a.lower().strip(), b.lower().strip()
    return a in b or b in a or SequenceMatcher(None, a, b).ratio() >= threshold


class IdentityStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            doc = request.user.identity_document
            return Response({
                'has_document': True,
                'status': doc.status,
                'document_type': doc.document_type,
                'rejection_reason': doc.rejection_reason or None,
            })
        except IdentityDocument.DoesNotExist:
            return Response({'has_document': False, 'status': None, 'document_type': None, 'rejection_reason': None})


class IdentityUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user

        try:
            existing = user.identity_document
            if existing.status == 'approved':
                return Response(
                    {'detail': 'Identity already verified.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
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
        save_kwargs = {
            'user': user,
            'status': doc_status,
            'rejection_reason': rejection_reason,
        }

        if front_file and selfie_file:
            front_bytes = front_file.read()
            selfie_bytes = selfie_file.read()
            # Reset so the serializer can still save the files
            front_file.seek(0)
            selfie_file.seek(0)

            # Step 1: AI document info extraction + name comparison
            doc_info = extract_document_info(front_bytes)
            raw_text = doc_info.get('raw_text', '')

            # Names from OCR extraction (may be None if the OCR service returns raw text only)
            ai_first = doc_info.get('first_name')
            ai_last = doc_info.get('last_name')

            name_mismatch = False
            if ai_first and ai_last:
                # AI returned structured names — use direct field comparison.
                # compare_names() requires ≥20 chars so it always returns None for
                # short individual names; _field_match() has no length restriction.
                # Accept either Western (first→first, last→last) or Eastern order.
                forward = _field_match(user.first_name, ai_first) and _field_match(user.last_name, ai_last)
                reversed_ = _field_match(user.first_name, ai_last) and _field_match(user.last_name, ai_first)
                if not (forward or reversed_):
                    name_mismatch = True
            elif len(raw_text.strip()) >= 20:
                # Fall back to fuzzy OCR text search
                last_ok = compare_names(user.last_name, raw_text)
                first_ok = compare_names(user.first_name, raw_text)
                if last_ok is False and first_ok is False:
                    name_mismatch = True

            if name_mismatch:
                doc_status = 'rejected'
                rejection_reason = "Le nom sur la pièce d'identité ne correspond pas aux informations de votre compte."
                reviewed_at = timezone.now()

            # Step 2: AI face verification — selfie vs document photo (skip if already rejected)
            if doc_status != 'rejected':
                ai_result = verify_id_card(front_bytes, selfie_bytes)
                if 'error' not in ai_result:
                    reviewed_at = timezone.now()
                    if ai_result.get('verified'):
                        doc_status = 'approved'
                    else:
                        doc_status = 'rejected'
                        rejection_reason = "Le visage sur le selfie ne correspond pas à la photo du document d'identité."
            # If all checks are inconclusive, keep status='pending' for manual admin review

            save_kwargs['status'] = doc_status
            save_kwargs['rejection_reason'] = rejection_reason
            if reviewed_at:
                save_kwargs['reviewed_at'] = reviewed_at

        serializer.save(**save_kwargs)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



