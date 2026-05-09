import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../theme/app_theme.dart';

class DocumentTypeScreen extends StatelessWidget {
  const DocumentTypeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 24),
                // Step indicator
                _buildStepHeader(context),
                const SizedBox(height: 36),
                const Text('Verify Your\nIdentity', style: TextStyle(fontSize: 32, fontWeight: FontWeight.w800, color: Colors.white, height: 1.2)),
                const SizedBox(height: 12),
                const Text(
                  'We need to verify who you are. Please choose your ID document type to continue.',
                  style: TextStyle(color: AppColors.textSecondary, fontSize: 15, height: 1.5),
                ),
                const SizedBox(height: 40),
                _DocumentCard(
                  type: 'id_card',
                  icon: Icons.credit_card_rounded,
                  title: 'National ID Card',
                  subtitle: 'Front & back required',
                  onTap: () => context.push('/identity/capture-document', extra: {'documentType': 'id_card', 'side': 'front'}),
                ),
                const SizedBox(height: 16),
                _DocumentCard(
                  type: 'passport',
                  icon: Icons.menu_book_rounded,
                  title: 'Passport',
                  subtitle: 'Photo page only',
                  onTap: () => context.push('/identity/capture-document', extra: {'documentType': 'passport', 'side': 'front'}),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceElevated,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppColors.cardBorder),
                  ),
                  child: Row(
                    children: const [
                      Icon(Icons.lock_rounded, color: AppColors.accent, size: 20),
                      SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Your documents are encrypted and stored securely. We never sell your data.',
                          style: TextStyle(color: AppColors.textSecondary, fontSize: 13, height: 1.4),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStepHeader(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: List.generate(3, (i) => Expanded(
                  child: Padding(
                    padding: EdgeInsets.only(right: i < 2 ? 6 : 0),
                    child: Container(
                      height: 4,
                      decoration: BoxDecoration(
                        color: i == 0 ? AppColors.primary : AppColors.cardBorder,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                )),
              ),
              const SizedBox(height: 8),
              const Text('Step 2 of 3 – Document Type', style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
            ],
          ),
        ),
      ],
    );
  }
}

class _DocumentCard extends StatelessWidget {
  final String type;
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _DocumentCard({
    required this.type,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppColors.cardBorder),
        ),
        child: Row(
          children: [
            Container(
              width: 60,
              height: 60,
              decoration: BoxDecoration(
                gradient: AppColors.primaryGradient,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(icon, color: Colors.white, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: Colors.white)),
                  const SizedBox(height: 4),
                  Text(subtitle, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary)),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios_rounded, color: AppColors.textSecondary, size: 16),
          ],
        ),
      ),
    );
  }
}
