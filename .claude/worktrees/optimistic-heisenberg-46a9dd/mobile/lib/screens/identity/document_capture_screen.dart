import 'dart:io';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import '../../theme/app_theme.dart';

class DocumentCaptureScreen extends StatefulWidget {
  final String documentType;
  final String side; // 'front' | 'back'

  const DocumentCaptureScreen({super.key, required this.documentType, required this.side});

  @override
  State<DocumentCaptureScreen> createState() => _DocumentCaptureScreenState();
}

class _DocumentCaptureScreenState extends State<DocumentCaptureScreen> {
  File? _image;
  final _picker = ImagePicker();

  bool get _isFront => widget.side == 'front';
  bool get _isIdCard => widget.documentType == 'id_card';

  String get _title {
    if (!_isIdCard) return 'Passport Photo Page';
    return _isFront ? 'ID Card – Front' : 'ID Card – Back';
  }

  String get _instruction {
    return 'Place your document inside the frame.\nMake sure all text is clearly visible and avoid glare.';
  }

  Future<void> _pickImage(ImageSource source) async {
    final picked = await _picker.pickImage(source: source, imageQuality: 90);
    if (picked != null) setState(() => _image = File(picked.path));
  }

  void _continue() {
    if (_image == null) return;

    final extra = {'documentType': widget.documentType, 'frontImage': _image!.path};

    if (_isIdCard && _isFront) {
      // Go capture back
      context.push('/identity/capture-document', extra: {
        'documentType': widget.documentType,
        'side': 'back',
        'frontImagePath': _image!.path,
      });
    } else if (_isIdCard && !_isFront) {
      // Go to selfie with both images
      final frontPath = (ModalRoute.of(context)?.settings.arguments as Map?)?['frontImagePath'];
      context.push('/identity/capture-selfie', extra: {
        'documentType': widget.documentType,
        'frontImagePath': GoRouterState.of(context).extra != null
            ? (GoRouterState.of(context).extra as Map)['frontImagePath']
            : null,
        'backImagePath': _image!.path,
      });
    } else {
      // Passport – go to selfie with front only
      context.push('/identity/capture-selfie', extra: {
        'documentType': widget.documentType,
        'frontImagePath': _image!.path,
        'backImagePath': null,
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final extra = GoRouterState.of(context).extra as Map<String, dynamic>?;

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
                    Expanded(child: Text(_title, textAlign: TextAlign.center, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Colors.white))),
                    const SizedBox(width: 48),
                  ],
                ),
              ),
              // Step bar
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 28),
                child: Row(
                  children: List.generate(3, (i) => Expanded(
                    child: Padding(
                      padding: EdgeInsets.only(right: i < 2 ? 6 : 0),
                      child: Container(
                        height: 4,
                        decoration: BoxDecoration(
                          color: i <= 1 ? AppColors.primary : AppColors.cardBorder,
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                    ),
                  )),
                ),
              ),
              const SizedBox(height: 8),
              Text('Step 2 of 3 – ${_isFront ? "Document Front" : "Document Back"}',
                  style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
              const SizedBox(height: 28),
              // Document frame
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 28),
                  child: Column(
                    children: [
                      _DocumentFrame(image: _image, isPassport: !_isIdCard),
                      const SizedBox(height: 24),
                      Text(_instruction,
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: AppColors.textSecondary, fontSize: 14, height: 1.5)),
                      const SizedBox(height: 32),
                      Row(
                        children: [
                          Expanded(
                            child: _SourceButton(
                              icon: Icons.camera_alt_rounded,
                              label: 'Camera',
                              onTap: () => _pickImage(ImageSource.camera),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _SourceButton(
                              icon: Icons.photo_library_rounded,
                              label: 'Gallery',
                              onTap: () => _pickImage(ImageSource.gallery),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      GradientButton(
                        label: _image == null ? 'Capture Document' : (_isIdCard && _isFront ? 'Continue to Back' : 'Continue'),
                        onPressed: _image == null ? null : _continue,
                        icon: const Icon(Icons.arrow_forward_rounded, color: Colors.white, size: 20),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }
}

class _DocumentFrame extends StatelessWidget {
  final File? image;
  final bool isPassport;
  const _DocumentFrame({required this.image, required this.isPassport});

  @override
  Widget build(BuildContext context) {
    final aspectRatio = isPassport ? 0.71 : 1.58; // passport vs ID card ratio
    return AspectRatio(
      aspectRatio: aspectRatio,
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surfaceElevated,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: image != null ? AppColors.primary : AppColors.cardBorder,
            width: image != null ? 2 : 1.5,
          ),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(15),
          child: image != null
              ? Image.file(image!, fit: BoxFit.cover)
              : Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      isPassport ? Icons.menu_book_rounded : Icons.credit_card_rounded,
                      size: 48,
                      color: AppColors.textHint,
                    ),
                    const SizedBox(height: 12),
                    const Text('Document appears here', style: TextStyle(color: AppColors.textHint, fontSize: 14)),
                  ],
                ),
        ),
      ),
    );
  }
}

class _SourceButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _SourceButton({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          color: AppColors.surfaceElevated,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.cardBorder),
        ),
        child: Column(
          children: [
            Icon(icon, color: AppColors.primary, size: 28),
            const SizedBox(height: 6),
            Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 13, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}
