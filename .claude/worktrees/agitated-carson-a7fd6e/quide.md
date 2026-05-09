# 📘 Guide d'intégration pour clients – Plateforme d'Identité

Bienvenue sur la **Plateforme d'Identité** – un fournisseur SSO, OAuth2 et OpenID Connect. Ce guide vous explique pas à pas comment créer un compte, créer une organisation (client), ajouter des applications OAuth2, et intégrer notre service dans vos propres applications.

---

## 1. Prérequis

- Un navigateur web moderne
- `curl` ou un outil pour tester les API (Postman, Insomnia)
- Vous devez connaître les bases d'OAuth2 (autorisation, jetons, portées)

> **Base URL de l'API :** `https://sso-backend-6b1e.onrender.com/api`  
> **Base URL OAuth2 :** `https://sso-backend-6b1e.onrender.com/o`

---

## 2. Créer un compte utilisateur (inscription)

Avant de créer une organisation, vous devez avoir un compte utilisateur.

```bash
curl -X POST https://sso-backend-6b1e.onrender.com/api/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "votre-email@exemple.com",
    "phone": "+33123456789",
    "first_name": "Jean",
    "last_name": "Dupont",
    "password": "MotDePasseFort123!",
    "password2": "MotDePasseFort123!"
  }'
```

**Réponse (201) :**
```json
{
  "user": { "id": 1, "email": "votre-email@exemple.com", ... },
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

>  Si la vérification d'email est active, vous recevrez un lien de confirmation. Connectez-vous ensuite.

---

## 3. Se connecter et obtenir un jeton JWT

```bash
curl -X POST https://sso-backend-6b1e.onrender.com/api/login/ \
  -H "Content-Type: application/json" \
  -d '{"identifier":"votre-email@exemple.com","password":"MotDePasseFort123!"}'
```

**Réponse :** `access` et `refresh` tokens. Conservez le `access_token` pour les requêtes authentifiées.

---

## 4. Lister les plans d’abonnement disponibles

Avant de créer une organisation, vous devez choisir un plan.

```bash
curl -H "Authorization: Bearer VOTRE_ACCESS_TOKEN" \
  https://sso-backend-6b1e.onrender.com/api/plans/
```

**Exemple de réponse :**
```json
[
  {
    "id": 1,
    "name": "Basic",
    "price_monthly": "9.99",
    "max_users": 500,
    "features": { "mfa": true, "oauth2": true }
  },
  ...
]
```

Notez l’`id` du plan que vous souhaitez.

---

## 5. Créer une organisation (client)

Une organisation représente votre entreprise. Elle possèdera vos applications OAuth2.

```bash
curl -X POST https://sso-backend-6b1e.onrender.com/api/clients/ \
  -H "Authorization: Bearer VOTRE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ma Société",
    "plan": 1,
    "primary_color": "#3366FF"
  }'
```

**Réponse :**
```json
{
  "id": 8,
  "name": "Ma Société",
  "slug": "ma-societe",
  "plan": 1,
  "logo": null,
  "primary_color": "#3366FF",
  "is_active": true
}
```

Conservez l’`id` du client (ici `8`) – vous en aurez besoin pour créer des applications OAuth.

---

## 6. Créer une application OAuth2

Une application OAuth2 correspond à votre service (site web, app mobile, API) qui utilisera notre SSO.

```bash
curl -X POST https://sso-backend-6b1e.onrender.com/api/clients/8/apps/ \
  -H "Authorization: Bearer VOTRE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mon Application Web",
    "redirect_uris": "https://monapp.com/callback",
    "client_type": "confidential",
    "grant_type": "authorization-code"
  }'
```

- **`client_type`** : `confidential` (avec secret) ou `public` (pour SPA / mobile – utilisez PKCE)
- **`grant_type`** : `authorization-code` (recommandé pour les utilisateurs) ou `client-credentials` (machine‑à‑machine)

**Réponse :**
```json
{
  "id": 10,
  "client_id": "XXX",
  "client_secret": "YYY",
  "name": "Mon Application Web",
  "redirect_uris": "https://monapp.com/callback",
  "client_type": "confidential",
  "authorization_grant_type": "authorization-code",
  "is_active": true
}
```

>  Le `client_secret` n’est affiché qu’une seule fois. Stockez‑le en lieu sûr.

---

## 7. Intégration OAuth2 dans votre application

### 7.1 Flux “Authorization Code” (pour applications avec serveur)

Ce flux redirige l’utilisateur vers notre page de connexion, puis retourne un code que votre serveur échange contre des jetons.

**Étape 1 – Rediriger l’utilisateur**

```
https://sso-backend-6b1e.onrender.com/o/authorize/?response_type=code&client_id=VOTRE_CLIENT_ID&redirect_uri=VOTRE_REDIRECT_URI&scope=openid%20profile%20email
```

**Étape 2 – Échanger le code contre des jetons**

```bash
curl -X POST https://sso-backend-6b1e.onrender.com/o/token/ \
  -d "grant_type=authorization_code" \
  -d "code=CODE_RECU" \
  -d "redirect_uri=VOTRE_REDIRECT_URI" \
  -d "client_id=VOTRE_CLIENT_ID" \
  -d "client_secret=VOTRE_CLIENT_SECRET"
```

**Réponse :**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "id_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Étape 3 – Utiliser l’`access_token`**

```bash
curl -H "Authorization: Bearer ACCESS_TOKEN" \
  https://sso-backend-6b1e.onrender.com/api/user/me/
```

### 7.2 Flux pour applications publiques (SPA / mobile) – PKCE

Pour les clients publics, **ne jamais utiliser `client_secret`**. Utilisez PKCE.

1. Générez un `code_verifier` (chaîne aléatoire) et un `code_challenge = base64url(sha256(code_verifier))`.
2. Redirigez l’utilisateur avec les paramètres supplémentaires :  
   `code_challenge` et `code_challenge_method=S256`
3. Lors de l’échange, envoyez `code_verifier` au lieu de `client_secret`.

Exemple de redirection :
```
/o/authorize/?response_type=code&client_id=PUBLIC_CLIENT_ID&redirect_uri=...&code_challenge=...&code_challenge_method=S256
```

### 7.3 Flux “Client Credentials” (machine‑à‑machine)

Utilisez ce flux si votre service doit accéder à nos API sans utilisateur.

```bash
curl -X POST https://sso-backend-6b1e.onrender.com/o/token/ \
  -d "grant_type=client_credentials" \
  -d "client_id=VOTRE_CLIENT_ID" \
  -d "client_secret=VOTRE_CLIENT_SECRET" \
  -d "scope=read"
```

---

## 8. OpenID Connect – Obtenir l’identité de l’utilisateur

Si vous avez demandé la portée `openid`, vous recevez un `id_token` (JWT) et pouvez appeler le point d’accès `/userinfo`.

```bash
curl -H "Authorization: Bearer ACCESS_TOKEN" \
  https://sso-backend-6b1e.onrender.com/o/userinfo/
```

**Réponse :**
```json
{
  "sub": "123",
  "email": "jean@exemple.com",
  "email_verified": true,
  "phone": "+33123456789",
  "given_name": "Jean",
  "family_name": "Dupont"
}
```

Vérifiez la signature de l’`id_token` à l’aide de notre JWKS :

```
https://sso-backend-6b1e.onrender.com/o/.well-known/jwks.json
```

---

## 9. Sécurité et bonnes pratiques

- **Conservez vos `client_secret` et `refresh_token` en lieu sûr.** Ne les incluez jamais dans du code client (frontend).
- Utilisez **PKCE** pour toute application publique (SPA, mobile).
- Demandez le **moins de portées possible** (principe du moindre privilège).
- **Rafraîchissez** le `access_token` avant son expiration (3600s) à l’aide du `refresh_token`.
- Activez la **double authentification (MFA)** pour vos comptes utilisateurs sensibles.

---

## 10. Gestion de l’équipe et des applications

### Lister les membres de votre organisation

```bash
curl -H "Authorization: Bearer ACCESS_TOKEN" \
  https://sso-backend-6b1e.onrender.com/api/clients/8/team/
```

### Inviter un utilisateur (il doit déjà avoir un compte)

```bash
curl -X POST https://sso-backend-6b1e.onrender.com/api/clients/8/team/ \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 42, "role": "member"}'
```

### Modifier les paramètres de votre application OAuth

```bash
curl -X PUT https://sso-backend-6b1e.onrender.com/api/clients/8/apps/10/ \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Nouveau nom", "redirect_uris": "https://nouvelleurl.com/callback"}'
```

### Supprimer une application

```bash
curl -X DELETE https://sso-backend-6b1e.onrender.com/api/clients/8/apps/10/ \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

## 11. Authentification par biométrie (facultatif)

Nos endpoints de connexion biométrique sont disponibles :

- **Enrôlement :** `POST /api/biometric/enroll/` (authentifié, avec image)
- **Connexion :** `POST /api/biometric/login/` (public, avec identifiant et image)

Voir la documentation dédiée pour plus de détails.

---

## 12. Dépannage des erreurs courantes

| Code HTTP | Message | Cause probable | Solution |
|-----------|---------|----------------|----------|
| 400 | `invalid_client` | Client ID / secret incorrect | Vérifiez vos identifiants |
| 400 | `invalid_grant` | Code d’autorisation expiré ou déjà utilisé | Recommencez le flux |
| 401 | `Unauthorized` | Access token manquant / invalide / expiré | Rafraîchissez ou reconnectez‑vous |
| 403 | `Forbidden` | Permissions insuffisantes | Vérifiez que vous êtes admin du client |
| 404 | Not Found | Mauvais endpoint ou ID client | Corrigez l’URL |

---

## 13. Exemple complet d’intégration en Python

```python
import requests

# 1. Rediriger l’utilisateur (vous le faites dans votre backend)
auth_url = "https://sso-backend-6b1e.onrender.com/o/authorize/"
params = {
    "response_type": "code",
    "client_id": "VOTRE_CLIENT_ID",
    "redirect_uri": "https://votreapp.com/callback",
    "scope": "openid profile email"
}
# Générez l’URL et redirigez l’utilisateur

# 2. Recevoir le code dans votre callback
code = request.args.get('code')

# 3. Échanger le code
token_resp = requests.post(
    "https://sso-backend-6b1e.onrender.com/o/token/",
    data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "https://votreapp.com/callback",
        "client_id": "VOTRE_CLIENT_ID",
        "client_secret": "VOTRE_CLIENT_SECRET"
    }
)
tokens = token_resp.json()

# 4. Récupérer l’utilisateur
user_resp = requests.get(
    "https://sso-backend-6b1e.onrender.com/o/userinfo/",
    headers={"Authorization": f"Bearer {tokens['access_token']}"}
)
user = user_resp.json()
print(user)
```


