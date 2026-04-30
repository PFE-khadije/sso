import 'dart:io';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../theme/app_theme.dart';
import '../../services/identity_service.dart';

class ReviewScreen extends StatefulWidget {
  final Map<String, dynamic> data;
  const ReviewScreen({super.key, required this.data});

  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> {
  bool _loading = false;
  String? _error;

  String get _documentType => widget.data['documentType'] as String;
  String? get _frontPath => widget.data['frontImagePath'] as String?;
  String? get _backPath => widget.data['backImagePath'] as String?;
  String? get _selfiePath => widget.data['selfiePath'] as String?;

  Future<void> _submit() async {
    if (_frontPath == null || _selfiePath == null) return;
    setState(() { _loading = true; _error = null; });

    final result = await IdentityService.uploadDocuments(
      documentType: _documentType,
      frontImage: File(_frontPath!),
      backImage: _backPath != null ? File(_backPath!) : null,
      selfieImage: File(_selfiePath!),
    );

    if (!mounted) return;
    setState(() => _loading = false);

    if (result.success) {
      context.go('/identity/pending');
    } else {
      setState(() => _error = result.error);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                child: Row(
                  children: [
                    IconButton(
                      onPressed: () => context.pop(),
                      icon: const Icon(Icons.arrow_back_ios_new_rounded, color: AppColors.textSecondary),
                    ),
                    const Expanded(
                      child: Text('Review & Submit', textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Colors.white)),
                    ),
                    const SizedBox(width: 48),
                  ],
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 28),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Almost there! Review your documents before submitting.',
                        style: TextStyle(color: AppColors.textSecondary, fontSize: 15, height: 1.5),
                      ),
                      const SizedBox(height: 28),
                      if (_error != null) ...[
                        _ErrorBanner(message: _error!),
                        const SizedBox(height: 20),
                      ],
                      // Document type badge
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AppColors.primary.withOpacity(0.3)),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.verified_rounded, color: AppColors.primary, size: 16),
                            const SizedBox(width: 6),
                            Text(
                              _documentType == 'id_card' ? 'National ID Card' : 'Passport',
                              style: const TextStyle(color: AppColors.primary, fontSize: 13, fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 24),
                      const Text('Documents', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white)),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(child: _ImagePreview(path: _frontPath, label: _documentType == 'passport' ? 'Photo Page' : 'Front')),
                          if (_backPath != null) ...[
                            const SizedBox(width: 12),
                            Expanded(child: _ImagePreview(path: _backPath, label: 'Back')),
                          ],
                        ],
                      ),
                      const SizedBox(height: 24),
                      const Text('Selfie', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white)),
                      const SizedBox(height: 12),
                      _SelfiePreview(path: _selfiePath),
                      const SizedBox(height: 28),
                      // Info box
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppColors.surfaceElevated,
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(color: AppColors.cardBorder),
                        ),
                        child: Column(
                          children: const [
                            _CheckItem(text: 'All text is clearly visible'),
                            SizedBox(height: 8),
                            _CheckItem(text: 'No blurry or cropped images'),
                            SizedBox(height: 8),
                            _CheckItem(text: 'Selfie matches document photo'),
                          ],
                        ),
                      ),
                      const SizedBox(height: 32),
                      GradientButton(
                        label: 'Submit for Verification',
                        onPressed: _submit,
                        isLoading: _loading,
                        icon: const Icon(Icons.send_rounded, color: Colors.white, size: 18),
                      ),
                      const SizedBox(height: 32),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ImagePreview extends StatelessWidget {
  final String? path;
  final String label;
  const _ImagePreview({required this.path, required this.label});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary)),
        const SizedBox(height: 8),
        AspectRatio(
          aspectRatio: 1.58,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.cardBorder),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(11),
              child: path != null
                  ? Image.file(File(path!), fit: BoxFit.cover)
                  : const Center(child: Icon(Icons.broken_image_outlined, color: AppColors.textHint)),
            ),
          ),
        ),
      ],
    );
  }
}

class _SelfiePreview extends StatelessWidget {
  final String? path;
  const _SelfiePreview({required this.path});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SizedBox(
        width: 140,
        height: 170,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(70),
            border: Border.all(color: AppColors.primary, width: 2),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(70),
            child: path != null
                ? Image.file(File(path!), fit: BoxFit.cover)
                : const Center(child: Icon(Icons.face_rounded, size: 60, color: AppColors.textHint)),
          ),
        ),
      ),
    );
  }
}

class _CheckItem extends StatelessWidget {
  final String text;
  const _CheckItem({required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(Icons.check_circle_rounded, color: AppColors.accent, size: 18),
        const SizedBox(width: 10),
        Text(text, style: const TextStyle(color: AppColors.textSecondary, fontSize: 14)),
      ],
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  final String message;
  const _ErrorBanner({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.error.withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.error.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline_rounded, color: AppColors.error, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(message, style: const TextStyle(color: AppColors.error, fontSize: 14))),
        ],
      ),
    );
  }
}
