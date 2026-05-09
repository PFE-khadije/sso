# 📘 Guide d'intégration pour clients – Plateforme d'Identité (version Flutter)

*(Ce guide complète la documentation principale – section spécifique aux applications mobiles Flutter)*

---

## Intégration avec une application Flutter

Vous pouvez intégrer notre SSO dans votre application mobile Flutter en utilisant le **flux Authorization Code avec PKCE** (recommandé pour les clients publics).  
Aucun `client_secret` n'est nécessaire, mais vous devez utiliser PKCE.

### 1. Installer les dépendances nécessaires

Dans votre projet Flutter, ajoutez les packages suivants dans `pubspec.yaml` :

```yaml
dependencies:
  flutter_appauth: ^6.0.0        # pour OAuth2 / OpenID Connect
  http: ^1.1.0                    # pour les appels API
  secure_storage: ^2.0.0          # pour stocker les jetons en toute sécurité
```

Puis exécutez `flutter pub get`.

### 2. Configurer l’application OAuth2

- Créez une application OAuth2 via notre API (voir section 6 du guide principal) avec :
  - `client_type` = `public`
  - `grant_type` = `authorization-code`
  - `redirect_uris` = un schéma personnalisé, par exemple `monapp://callback`

> ⚠️ Pour Flutter, le `redirect_uri` doit être un schéma personnalisé que votre application sait intercepter. Exemple : `com.monentreprise.monapp:/callback`

### 3. Implémenter le flux d’authentification

Voici un exemple complet utilisant `flutter_appauth` (qui gère PKCE automatiquement).

```dart
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

final FlutterAppAuth appAuth = FlutterAppAuth();

// Configuration
const String clientId = 'VOTRE_CLIENT_ID_PUBLIC';
const String redirectUrl = 'com.monentreprise.monapp:/callback';
const String discoveryUrl = 'https://sso-backend-6b1e.onrender.com/.well-known/openid-configuration';

Future<void> login() async {
  // Récupérer la configuration OIDC
  final discovery = await appAuth.fetchDiscovery(discoveryUrl);
  if (discovery == null) throw Exception('Discovery non trouvé');

  // Lancer le flow Authorization Code + PKCE
  final authResult = await appAuth.authorize(
    AuthorizationTokenRequest(
      clientId,
      redirectUrl,
      discoveryUrl: discoveryUrl,
      scopes: ['openid', 'profile', 'email'],
      // PKCE est activé par défaut
    ),
  );

  if (authResult != null && authResult.accessToken != null) {
    // Échanger le code contre les jetons (fait automatiquement par flutter_appauth)
    // Vous avez maintenant accessToken et idToken
    final accessToken = authResult.accessToken!;
    final idToken = authResult.idToken;

    // Stocker les jetons de façon sécurisée
    await storeTokens(accessToken, idToken);

    // Appeler le endpoint /userinfo pour récupérer le profil
    final userInfo = await fetchUserInfo(accessToken);
    print(userInfo);
  }
}
```

### 4. Récupérer les informations utilisateur

```dart
Future<Map<String, dynamic>> fetchUserInfo(String accessToken) async {
  final response = await http.get(
    Uri.parse('https://sso-backend-6b1e.onrender.com/o/userinfo/'),
    headers: {'Authorization': 'Bearer $accessToken'},
  );
  if (response.statusCode == 200) {
    return json.decode(response.body);
  } else {
    throw Exception('Failed to get user info');
  }
}
```

### 5. Stockage sécurisé des jetons

```dart
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
final storage = FlutterSecureStorage();

Future<void> storeTokens(String accessToken, String? idToken) async {
  await storage.write(key: 'access_token', value: accessToken);
  if (idToken != null) {
    await storage.write(key: 'id_token', value: idToken);
  }
}

Future<void> clearTokens() async {
  await storage.delete(key: 'access_token');
  await storage.delete(key: 'id_token');
}
```

### 6. Intercepter le callback (redirection)

Dans votre fichier `android/app/src/main/AndroidManifest.xml`, ajoutez un `<intent-filter>` pour capturer le schéma personnalisé :

```xml
<activity android:name="com.linusu.flutter_appauth.CallbackActivity" >
  <intent-filter>
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="com.monentreprise.monapp" android:host="callback" />
  </intent-filter>
</activity>
```

Pour iOS, dans `Info.plist` :

```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>com.monentreprise.monapp</string>
    </array>
  </dict>
</array>
```

### 7. Rafraîchir le token

```dart
Future<String?> refreshToken(String refreshToken) async {
  final discovery = await appAuth.fetchDiscovery(discoveryUrl);
  final tokenResponse = await appAuth.token(
    TokenRequest(
      clientId,
      redirectUrl,
      refreshToken: refreshToken,
      discoveryUrl: discoveryUrl,
    ),
  );
  if (tokenResponse != null && tokenResponse.accessToken != null) {
    await storeTokens(tokenResponse.accessToken!, tokenResponse.idToken);
    return tokenResponse.accessToken;
  }
  return null;
}
```

### 8. Appeler les API protégées

```dart
Future<void> callProtectedApi() async {
  final accessToken = await storage.read(key: 'access_token');
  if (accessToken == null) throw Exception('Non authentifié');
  final response = await http.get(
    Uri.parse('https://sso-backend-6b1e.onrender.com/api/user/me/'),
    headers: {'Authorization': 'Bearer $accessToken'},
  );
  if (response.statusCode == 200) {
    print('Profil: ${response.body}');
  }
}
```

---

## Bonnes pratiques pour Flutter

- **N’utilisez jamais `client_secret`** dans une application mobile. Restez sur PKCE.
- **Stockez les jetons dans `flutter_secure_storage`** (chiffrement natif).
- **Vérifiez la validité du `access_token`** avant chaque appel API ; s’il expire, utilisez le `refresh_token` silencieusement.
- **Gérez la déconnexion** en appelant notre endpoint `/logout` (ou simplement en supprimant les jetons localement).

---

## Exemple de cycle complet

```dart
// Page de connexion
ElevatedButton(
  onPressed: () async {
    await login();
    Navigator.pushReplacementNamed(context, '/dashboard');
  },
  child: Text('Se connecter avec SSO'),
);
```

Une fois connecté, l’utilisateur peut utiliser l’application sans ressaisir ses identifiants.

---

## Dépannage Flutter spécifique

| Problème | Solution |
|----------|----------|
| `redirect_uri` non reconnu | Vérifiez la déclaration dans `AndroidManifest.xml` et `Info.plist`. Assurez-vous que le schéma correspond exactement à celui enregistré dans notre plateforme. |
| `invalid_grant` (PKCE) | Vérifiez que vous utilisez bien PKCE ; `flutter_appauth` le gère automatiquement. |
| `unsupported_response_type` | Assurez-vous que le `response_type` est `code`. |
| connexion échouée sur émulateur | Les émulateurs peuvent avoir des problèmes réseau ; utilisez un appareil réel ou `adb reverse` pour les tests locaux. |

---
