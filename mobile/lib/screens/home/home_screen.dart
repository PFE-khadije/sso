import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../theme/app_theme.dart';
import '../../services/auth_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Map<String, dynamic>? _user;

  @override
  void initState() {
    super.initState();
    _loadUser();
  }

  Future<void> _loadUser() async {
    final user = await AuthService.getCurrentUser();
    if (mounted) setState(() => _user = user);
  }

  @override
  Widget build(BuildContext context) {
    final name = _user != null
        ? '${_user!['first_name'] ?? ''} ${_user!['last_name'] ?? ''}'.trim()
        : '';

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Column(
            children: [
              // Header
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
                child: Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        gradient: AppColors.primaryGradient,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: const Icon(Icons.shield_rounded, color: Colors.white, size: 24),
                    ),
                    const SizedBox(width: 12),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(name.isNotEmpty ? 'Hello, $name 👋' : 'Welcome back!',
                            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white)),
                        const Text('Identity Verified', style: TextStyle(fontSize: 12, color: AppColors.accent)),
                      ],
                    ),
                    const Spacer(),
                    IconButton(
                      onPressed: () async {
                        await AuthService.logout();
                        if (context.mounted) context.go('/welcome');
                      },
                      icon: const Icon(Icons.logout_rounded, color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
              // Verified badge card
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: AppColors.primaryGradient,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: [BoxShadow(color: AppColors.primary.withOpacity(0.3), blurRadius: 20, offset: const Offset(0, 8))],
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 52,
                        height: 52,
                        decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(14)),
                        child: const Icon(Icons.verified_user_rounded, color: Colors.white, size: 28),
                      ),
                      const SizedBox(width: 16),
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Identity Verified', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white)),
                            SizedBox(height: 4),
                            Text('Your account is fully verified and secure', style: TextStyle(fontSize: 13, color: Colors.white70)),
                          ],
                        ),
                      ),
                      const Icon(Icons.check_circle_rounded, color: Colors.white, size: 28),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 28),
              // Section: Quick Actions
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Row(
                  children: const [
                    Text('Your Services', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white)),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: GridView.count(
                    crossAxisCount: 2,
                    crossAxisSpacing: 14,
                    mainAxisSpacing: 14,
                    childAspectRatio: 1.1,
                    children: const [
                      _ServiceCard(icon: Icons.credit_card_rounded, label: 'My ID Card', color: Color(0xFF4F6AF5)),
                      _ServiceCard(icon: Icons.fingerprint, label: 'Biometrics', color: Color(0xFF00D4AA)),
                      _ServiceCard(icon: Icons.devices_rounded, label: 'My Devices', color: Color(0xFFAB47BC)),
                      _ServiceCard(icon: Icons.shield_outlined, label: 'Security', color: Color(0xFFFFB300)),
                      _ServiceCard(icon: Icons.history_rounded, label: 'Activity', color: Color(0xFFEF5350)),
                      _ServiceCard(icon: Icons.settings_rounded, label: 'Settings', color: Color(0xFF42A5F5)),
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

class _ServiceCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _ServiceCard({required this.icon, required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: color.withOpacity(0.15),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: color, size: 26),
          ),
          const SizedBox(height: 12),
          Text(label, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.white)),
        ],
      ),
    );
  }
}
