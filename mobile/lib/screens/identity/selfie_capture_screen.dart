import 'dart:io';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import '../../theme/app_theme.dart';

class SelfieCaptureScreen extends StatefulWidget {
  final Map<String, dynamic> extra;
  const SelfieCaptureScreen({super.key, required this.extra});

  @override
  State<SelfieCaptureScreen> createState() => _SelfieCaptureScreenState();
}

class _SelfieCaptureScreenState extends State<SelfieCaptureScreen> {
  File? _selfie;
  final _picker = ImagePicker();

  Future<void> _takeSelfie(ImageSource source) async {
    final picked = await _picker.pickImage(
      source: source,
      preferredCameraDevice: CameraDevice.front,
      imageQuality: 90,
    );
    if (picked != null) setState(() => _selfie = File(picked.path));
  }

  void _continue() {
    if (_selfie == null) return;
    context.push('/identity/review', extra: {
      ...widget.extra,
      'selfiePath': _selfie!.path,
    });
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
                      child: Text('Take a Selfie', textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Colors.white)),
                    ),
                    const SizedBox(width: 48),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 28),
                child: Row(
                  children: List.generate(3, (i) => Expanded(
                    child: Padding(
                      padding: EdgeInsets.only(right: i < 2 ? 6 : 0),
                      child: Container(
                        height: 4,
                        decoration: BoxDecoration(
                          color: i <= 2 ? AppColors.primary : AppColors.cardBorder,
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                    ),
                  )),
                ),
              ),
              const SizedBox(height: 8),
              const Text('Step 3 of 3 – Face Verification', style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
              const SizedBox(height: 32),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 28),
                  child: Column(
                    children: [
                      _SelfieFrame(image: _selfie),
                      const SizedBox(height: 28),
                      const Text(
                        'Look directly at the camera with your face centered in the oval. Make sure your face is well-lit.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: AppColors.textSecondary, fontSize: 14, height: 1.5),
                      ),
                      const SizedBox(height: 12),
                      _TipsRow(),
                      const SizedBox(height: 28),
                      Row(
                        children: [
                          Expanded(
                            child: _SourceButton(
                              icon: Icons.camera_front_rounded,
                              label: 'Camera',
                              onTap: () => _takeSelfie(ImageSource.camera),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _SourceButton(
                              icon: Icons.photo_library_rounded,
                              label: 'Gallery',
                              onTap: () => _takeSelfie(ImageSource.gallery),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      GradientButton(
                        label: 'Review & Submit',
                        onPressed: _selfie == null ? null : _continue,
                        icon: const Icon(Icons.check_rounded, color: Colors.white, size: 20),
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

class _SelfieFrame extends StatelessWidget {
  final File? image;
  const _SelfieFrame({required this.image});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SizedBox(
        width: 220,
        height: 260,
        child: Stack(
          alignment: Alignment.center,
          children: [
            // Oval frame
            Container(
              width: 200,
              height: 240,
              decoration: BoxDecoration(
                shape: BoxShape.rectangle,
                borderRadius: BorderRadius.circular(100),
                border: Border.all(
                  color: image != null ? AppColors.primary : AppColors.cardBorder,
                  width: 2.5,
                ),
                color: AppColors.surfaceElevated,
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(100),
                child: image != null
                    ? Image.file(image!, fit: BoxFit.cover)
                    : const Icon(Icons.face_rounded, size: 80, color: AppColors.textHint),
              ),
            ),
            // Corner dots
            if (image == null) ...[
              Positioned(top: 0, child: _CornerDot()),
              Positioned(bottom: 0, child: _CornerDot()),
              Positioned(left: 0, child: _CornerDot()),
              Positioned(right: 0, child: _CornerDot()),
            ],
          ],
        ),
      ),
    );
  }
}

class _CornerDot extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 10,
      height: 10,
      decoration: const BoxDecoration(color: AppColors.primary, shape: BoxShape.circle),
    );
  }
}

class _TipsRow extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const tips = [
      (Icons.wb_sunny_outlined, 'Good lighting'),
      (Icons.do_not_disturb_on_outlined, 'No glasses'),
      (Icons.face_unlock_outlined, 'Face centered'),
    ];
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: tips
          .map((t) => Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Column(
                  children: [
                    Icon(t.$1, color: AppColors.accent, size: 20),
                    const SizedBox(height: 4),
                    Text(t.$2, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
                  ],
                ),
              ))
          .toList(),
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
