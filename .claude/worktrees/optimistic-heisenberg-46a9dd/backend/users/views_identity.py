from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from .models import IdentityDocument
from .serializers import IdentityDocumentSerializer


class IdentityDocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            existing = request.user.identity_document
            if existing.status == 'approved':
                return Response({'detail': 'Identity already verified.'}, status=status.HTTP_400_BAD_REQUEST)
            # Allow re-submission if rejected
            serializer = IdentityDocumentSerializer(existing, data=request.data, partial=False)
        except IdentityDocument.DoesNotExist:
            serializer = IdentityDocumentSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(user=request.user, status='pending')
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IdentityDocumentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            doc = request.user.identity_document
            return Response({
                'has_document': True,
                'status': doc.status,
                'document_type': doc.document_type,
                'rejection_reason': doc.rejection_reason,
                'submitted_at': doc.created_at,
            })
        except IdentityDocument.DoesNotExist:
            return Response({'has_document': False, 'status': None})
