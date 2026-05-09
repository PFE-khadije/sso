import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../theme/app_theme.dart';

class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: Column(
              children: [
                const Spacer(flex: 2),
                // Illustration area
                _HeroIllustration(),
                const SizedBox(height: 48),
                const Text(
                  'Your Identity,\nSecured.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 36, fontWeight: FontWeight.w800, color: Colors.white, height: 1.15, letterSpacing: -0.5),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Verify once, access everywhere.\nNovaGard keeps your digital identity safe and private.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 16, color: AppColors.textSecondary, height: 1.6),
                ),
                const Spacer(flex: 2),
                // Feature pills
                _FeaturePills(),
                const SizedBox(height: 40),
                GradientButton(
                  label: 'Create Account',
                  onPressed: () => context.push('/register'),
                ),
                const SizedBox(height: 16),
                OutlinedButton(
                  onPressed: () => context.push('/login'),
                  child: const Text('Sign In'),
                ),
                const SizedBox(height: 32),
                const Text(
                  'By continuing you agree to our Terms & Privacy Policy',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, color: AppColors.textHint),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _HeroIllustration extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 220,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Glow rings
          Container(
            width: 200,
            height: 200,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: AppColors.primary.withOpacity(0.15), width: 1),
            ),
          ),
          Container(
            width: 160,
            height: 160,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: AppColors.primary.withOpacity(0.25), width: 1),
            ),
          ),
          // Shield icon
          Container(
            width: 110,
            height: 110,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              shape: BoxShape.circle,
              boxShadow: [BoxShadow(color: AppColors.primary.withOpacity(0.4), blurRadius: 40, spreadRadius: 5)],
            ),
            child: const Icon(Icons.shield_rounded, size: 58, color: Colors.white),
          ),
          // Floating badges
          Positioned(top: 20, right: 30, child: _FloatingBadge(icon: Icons.fingerprint, color: AppColors.accent)),
          Positioned(bottom: 20, left: 30, child: _FloatingBadge(icon: Icons.verified_user, color: AppColors.primary)),
          Positioned(top: 40, left: 40, child: _FloatingBadge(icon: Icons.lock_rounded, color: const Color(0xFFAB47BC))),
        ],
      ),
    );
  }
}

class _FloatingBadge extends StatelessWidget {
  final IconData icon;
  final Color color;
  const _FloatingBadge({required this.icon, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.cardBorder),
        boxShadow: [BoxShadow(color: color.withOpacity(0.3), blurRadius: 12)],
      ),
      child: Icon(icon, size: 22, color: color),
    );
  }
}

class _FeaturePills extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const features = [
      (Icons.credit_card_rounded, 'ID Verified'),
      (Icons.face_retouching_natural, 'Face Match'),
      (Icons.lock_outline_rounded, 'Encrypted'),
    ];
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: features
          .map((f) => Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceElevated,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: AppColors.cardBorder),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(f.$1, size: 14, color: AppColors.primary),
                      const SizedBox(width: 6),
                      Text(f.$2, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary, fontWeight: FontWeight.w500)),
                    ],
                  ),
                ),
              ))
          .toList(),
    );
  }
}
