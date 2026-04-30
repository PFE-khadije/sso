import 'dart:convert';
import 'api_service.dart';

class AuthResult {
  final bool success;
  final String? error;
  final Map<String, dynamic>? user;
  final bool mfaRequired;
  final String? mfaToken;
  final List<String> mfaMethods;

  const AuthResult({
    required this.success,
    this.error,
    this.user,
    this.mfaRequired = false,
    this.mfaToken,
    this.mfaMethods = const [],
  });
}

class AuthService {
  static Future<AuthResult> register({
    required String email,
    required String phone,
    required String firstName,
    required String lastName,
    required String password,
    required String password2,
  }) async {
    try {
      final response = await ApiService.post('/signup/', {
        'email': email,
        'phone': phone,
        'first_name': firstName,
        'last_name': lastName,
        'password': password,
        'password2': password2,
      });
      final data = jsonDecode(response.body);
      if (response.statusCode == 201) {
        await ApiService.saveTokens(data['access'], data['refresh']);
        return AuthResult(success: true, user: data['user']);
      }
      final errors = data is Map ? data.values.expand((v) => v is List ? v : [v]).join('\n') : 'Registration failed';
      return AuthResult(success: false, error: errors.toString());
    } catch (e) {
      return AuthResult(success: false, error: 'Network error. Please try again.');
    }
  }

  static Future<AuthResult> login({
    required String identifier,
    required String password,
  }) async {
    try {
      final response = await ApiService.post('/login/', {
        'identifier': identifier,
        'password': password,
      });
      final data = jsonDecode(response.body);
      if (response.statusCode == 200) {
        if (data['mfa_required'] == true) {
          return AuthResult(
            success: true,
            mfaRequired: true,
            mfaToken: data['mfa_token'],
            mfaMethods: List<String>.from(data['mfa_methods'] ?? []),
          );
        }
        await ApiService.saveTokens(data['access'], data['refresh']);
        return AuthResult(success: true, user: data['user']);
      }
      final msg = data['detail'] ?? data['non_field_errors']?.first ?? 'Login failed';
      return AuthResult(success: false, error: msg.toString());
    } catch (e) {
      return AuthResult(success: false, error: 'Network error. Please try again.');
    }
  }

  static Future<void> logout() async {
    await ApiService.clearTokens();
  }

  static Future<Map<String, dynamic>?> getCurrentUser() async {
    try {
      final response = await ApiService.get('/user/me/');
      if (response.statusCode == 200) return jsonDecode(response.body);
      return null;
    } catch (_) {
      return null;
    }
  }
}
