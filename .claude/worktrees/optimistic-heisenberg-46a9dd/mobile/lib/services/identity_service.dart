import 'dart:convert';
import 'dart:io';
import 'api_service.dart';

class IdentityStatus {
  final bool hasDocument;
  final String? status;
  final String? documentType;
  final String? rejectionReason;

  const IdentityStatus({
    required this.hasDocument,
    this.status,
    this.documentType,
    this.rejectionReason,
  });

  bool get isPending => status == 'pending' || status == 'under_review';
  bool get isApproved => status == 'approved';
  bool get isRejected => status == 'rejected';

  factory IdentityStatus.fromJson(Map<String, dynamic> json) {
    return IdentityStatus(
      hasDocument: json['has_document'] ?? false,
      status: json['status'],
      documentType: json['document_type'],
      rejectionReason: json['rejection_reason'],
    );
  }
}

class IdentityService {
  static Future<IdentityStatus> getStatus() async {
    try {
      final response = await ApiService.get('/identity/status/');
      if (response.statusCode == 200) {
        return IdentityStatus.fromJson(jsonDecode(response.body));
      }
    } catch (_) {}
    return const IdentityStatus(hasDocument: false);
  }

  static Future<({bool success, String? error})> uploadDocuments({
    required String documentType,
    required File frontImage,
    File? backImage,
    required File selfieImage,
  }) async {
    try {
      final files = <String, File>{
        'front_image': frontImage,
        'selfie_image': selfieImage,
        if (backImage != null) 'back_image': backImage,
      };
      final response = await ApiService.multipartPost(
        '/identity/upload/',
        fields: {'document_type': documentType},
        files: files,
      );
      if (response.statusCode == 201) return (success: true, error: null);
      final data = jsonDecode(response.body);
      final msg = data['detail'] ?? data.values.first?.toString() ?? 'Upload failed';
      return (success: false, error: msg.toString());
    } catch (e) {
      return (success: false, error: 'Network error. Please try again.');
    }
  }
}
