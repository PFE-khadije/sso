import logging
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

logger = logging.getLogger(__name__)


def _field_match(a, b, threshold=0.75, min_substr=4):
    """Direct fuzzy match between two name strings.
    Substring matches are only accepted when the shorter side is at least
    `min_substr` characters long - this prevents short two- or three-letter
    names ("Ali", "Al") from accidentally matching unrelated text via the
    `a in b` shortcut. Falls back to a SequenceMatcher ratio comparison."""
    if not a or not b:
        return False
    a, b = a.lower().strip(), b.lower().strip()
    if len(a) >= min_substr and a in b:
        return True
    if len(b) >= min_substr and b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


class IdentityStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            doc = request.user.identity_document
            resp = {
                'has_document': True,
                'status': doc.status,
                'document_type': doc.document_type,
                'rejection_reason': doc.rejection_reason or None,
            }
            if doc.status == 'approved':
                resp['ocr'] = {
                    'first_name_fl': doc.ocr_first_name_fl,
                    'last_name_fl': doc.ocr_last_name_fl,
                    'first_name_ar': doc.ocr_first_name_ar,
                    'last_name_ar': doc.ocr_last_name_ar,
                    'birth_date': doc.ocr_birth_date,
                    'doc_number': doc.ocr_doc_number,
                    'birth_place_fl': doc.ocr_birth_place_fl,
                    'birth_place_ar': doc.ocr_birth_place_ar,
                    'gender': doc.ocr_gender,
                    'nationality': doc.ocr_nationality,
                }
            return Response(resp)
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
            front_file.seek(0)
            selfie_file.seek(0)

            doc_info = extract_document_info(front_bytes)
            raw_text = doc_info.get('raw_text', '')

            save_kwargs.update({
                'ocr_first_name_fl': doc_info.get('first_name') or '',
                'ocr_last_name_fl': doc_info.get('last_name') or '',
                'ocr_first_name_ar': doc_info.get('first_name_ar') or '',
                'ocr_last_name_ar': doc_info.get('last_name_ar') or '',
                'ocr_birth_date': str(doc_info.get('birth_date') or ''),
                'ocr_doc_number': str(doc_info.get('doc_number') or ''),
                'ocr_birth_place_fl': doc_info.get('birth_place_fl') or '',
                'ocr_birth_place_ar': doc_info.get('birth_place_ar') or '',
                'ocr_gender': doc_info.get('gender') or '',
                'ocr_nationality': doc_info.get('nationality') or '',
            })

            ai_first_candidates = [
                n for n in (doc_info.get('first_name'), doc_info.get('first_name_ar')) if n
            ]
            ai_last_candidates = [
                n for n in (doc_info.get('last_name'), doc_info.get('last_name_ar')) if n
            ]

            logger.warning(
                "[IDENTITY] user=%s registered=(%r,%r) ocr_first=%s ocr_last=%s raw_text_len=%d",
                getattr(user, 'email', user.pk),
                user.first_name, user.last_name,
                ai_first_candidates, ai_last_candidates,
                len(raw_text),
            )

            name_mismatch = False
            decided_by = 'inconclusive'
            if ai_first_candidates and ai_last_candidates:
                forward = (
                    any(_field_match(user.first_name, f) for f in ai_first_candidates)
                    and any(_field_match(user.last_name, l) for l in ai_last_candidates)
                )
                reversed_ = (
                    any(_field_match(user.first_name, l) for l in ai_last_candidates)
                    and any(_field_match(user.last_name, f) for f in ai_first_candidates)
                )
                decided_by = 'structured-names'
                if not (forward or reversed_):
                    name_mismatch = True
                logger.warning(
                    "[IDENTITY] name-check forward=%s reversed=%s -> mismatch=%s",
                    forward, reversed_, name_mismatch,
                )
            elif len(raw_text.strip()) >= 20:
                last_ok = compare_names(user.last_name, raw_text)
                first_ok = compare_names(user.first_name, raw_text)
                decided_by = 'raw-text-fallback'
                if last_ok is False and first_ok is False:
                    name_mismatch = True
                logger.warning(
                    "[IDENTITY] raw-text-fallback last_ok=%s first_ok=%s -> mismatch=%s",
                    last_ok, first_ok, name_mismatch,
                )
            else:
                logger.warning("[IDENTITY] name-check SKIPPED: no usable OCR output")

            if name_mismatch:
                doc_status = 'rejected'
                rejection_reason = "Le nom sur la piece d'identite ne correspond pas aux informations de votre compte."
                reviewed_at = timezone.now()

            if doc_status != 'rejected':
                ai_result = verify_id_card(front_bytes, selfie_bytes)
                logger.warning(
                    "[IDENTITY] face-check result=%s",
                    {k: v for k, v in ai_result.items() if k != 'message'},
                )
                if 'error' not in ai_result:
                    reviewed_at = timezone.now()
                    if ai_result.get('verified'):
                        doc_status = 'approved'
                    else:
                        doc_status = 'rejected'
                        rejection_reason = "Le visage sur le selfie ne correspond pas a la photo du document d'identite."

            logger.warning(
                "[IDENTITY] FINAL decision=%s decided_by=%s reason=%r",
                doc_status, decided_by, rejection_reason,
            )

            save_kwargs['status'] = doc_status
            save_kwargs['rejection_reason'] = rejection_reason
            if reviewed_at:
                save_kwargs['reviewed_at'] = reviewed_at

        serializer.save(**save_kwargs)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
