import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'theme/app_theme.dart';
import 'screens/splash_screen.dart';
import 'screens/welcome_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/auth/register_screen.dart';
import 'screens/identity/document_type_screen.dart';
import 'screens/identity/document_capture_screen.dart';
import 'screens/identity/selfie_capture_screen.dart';
import 'screens/identity/review_screen.dart';
import 'screens/identity/verification_pending_screen.dart';
import 'screens/home/home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  runApp(const NovaGardApp());
}

final _router = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(path: '/', builder: (_, __) => const SplashScreen()),
    GoRoute(path: '/welcome', builder: (_, __) => const WelcomeScreen()),
    GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
    GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
    GoRoute(path: '/identity/document-type', builder: (_, __) => const DocumentTypeScreen()),
    GoRoute(
      path: '/identity/capture-document',
      builder: (_, state) {
        final extra = state.extra as Map<String, dynamic>;
        return DocumentCaptureScreen(
          documentType: extra['documentType'] as String,
          side: extra['side'] as String,
        );
      },
    ),
    GoRoute(
      path: '/identity/capture-selfie',
      builder: (_, state) => SelfieCaptureScreen(extra: state.extra as Map<String, dynamic>),
    ),
    GoRoute(
      path: '/identity/review',
      builder: (_, state) => ReviewScreen(data: state.extra as Map<String, dynamic>),
    ),
    GoRoute(path: '/identity/pending', builder: (_, __) => const VerificationPendingScreen()),
    GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
  ],
);

class NovaGardApp extends StatelessWidget {
  const NovaGardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'NovaGard',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      routerConfig: _router,
    );
  }
}
