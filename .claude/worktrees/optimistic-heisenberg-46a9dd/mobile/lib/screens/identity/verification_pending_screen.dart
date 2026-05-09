import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../theme/app_theme.dart';
import '../../services/identity_service.dart';
import '../../services/auth_service.dart';

class VerificationPendingScreen extends StatefulWidget {
  const VerificationPendingScreen({super.key});

  @override
  State<VerificationPendingScreen> createState() => _VerificationPendingScreenState();
}

class _VerificationPendingScreenState extends State<VerificationPendingScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  IdentityStatus? _status;
  bool _checking = false;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _loadStatus();
  }

  Future<void> _loadStatus() async {
    final status = await IdentityService.getStatus();
    if (mounted) setState(() => _status = status);
  }

  Future<void> _checkStatus() async {
    setState(() => _checking = true);
    final status = await IdentityService.getStatus();
    if (!mounted) return;
    setState(() { _status = status; _checking = false; });

    if (status.isApproved) context.go('/home');
    if (status.isRejected) context.go('/identity/document-type');
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Spacer(flex: 2),
                // Animated icon
                AnimatedBuilder(
                  animation: _pulseController,
                  builder: (_, __) => Transform.scale(
                    scale: 0.95 + 0.05 * _pulseController.value,
                    child: Container(
                      width: 120,
                      height: 120,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: LinearGradient(
                          colors: [
                            AppColors.warning.withOpacity(0.8 + 0.2 * _pulseController.value),
                            AppColors.primary.withOpacity(0.8 + 0.2 * _pulseController.value),
                          ],
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.warning.withOpacity(0.3 * _pulseController.value),
                            blurRadius: 30,
                            spreadRadius: 10,
                          )
                        ],
                      ),
                      child: const Icon(Icons.hourglass_top_rounded, size: 56, color: Colors.white),
                    ),
                  ),
                ),
                const SizedBox(height: 36),
                const Text(
                  'Verification\nIn Progress',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 32, fontWeight: FontWeight.w800, color: Colors.white, height: 1.2),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Our team is reviewing your identity documents. This usually takes 5–10 minutes.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.textSecondary, fontSize: 16, height: 1.6),
                ),
                const SizedBox(height: 40),
                // Timeline
                _VerificationTimeline(),
                const Spacer(flex: 2),
                GradientButton(
                  label: _checking ? 'Checking...' : 'Check Status',
                  onPressed: _checking ? null : _checkStatus,
                  isLoading: _checking,
                  icon: const Icon(Icons.refresh_rounded, color: Colors.white, size: 20),
                ),
                const SizedBox(height: 16),
                TextButton(
                  onPressed: () async {
                    await AuthService.logout();
                    if (context.mounted) context.go('/welcome');
                  },
                  child: const Text('Sign Out', style: TextStyle(color: AppColors.textSecondary)),
                ),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _VerificationTimeline extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const steps = [
      (Icons.upload_rounded, 'Documents submitted', true),
      (Icons.search_rounded, 'Identity review', true),
      (Icons.verified_rounded, 'Verification complete', false),
    ];
    return Column(
      children: steps.asMap().entries.map((entry) {
        final i = entry.key;
        final step = entry.value;
        return Row(
          children: [
            Column(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: step.$3 ? AppColors.primary.withOpacity(0.2) : AppColors.surfaceElevated,
                    shape: BoxShape.circle,
                    border: Border.all(color: step.$3 ? AppColors.primary : AppColors.cardBorder),
                  ),
                  child: Icon(step.$1, size: 18, color: step.$3 ? AppColors.primary : AppColors.textHint),
                ),
                if (i < steps.length - 1)
                  Container(width: 2, height: 24, color: i == 0 ? AppColors.primary : AppColors.cardBorder),
              ],
            ),
            const SizedBox(width: 16),
            Text(step.$2, style: TextStyle(color: step.$3 ? Colors.white : AppColors.textHint, fontSize: 15, fontWeight: step.$3 ? FontWeight.w500 : FontWeight.w400)),
          ],
        );
      }).toList(),
    );
  }
}
