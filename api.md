# 📘 Documentation complète de l'API – Plateforme d’Identité Numérique

**Version** : 1.0  
**Base URL** : `https://api.votre-domaine.com/api`  
*(Développement : `http://localhost:8000/api`)*  
**Format** : JSON  
**Authentification** : Jetons JWT (Bearer) sauf pour les endpoints publics.

---

# Table des matières

1. [Authentification (JWT)](#1-authentification-jwt)
2. [Multi-Factor Authentication (MFA)](#2-multi-factor-authentication-mfa)
3. [Tableau de bord utilisateur](#3-tableau-de-bord-utilisateur)
4. [Gestion des clients (multi-tenancy)](#4-gestion-des-clients-multi-tenancy)
5. [OAuth2 / OpenID Connect](#5-oauth2--openid-connect)
6. [Biométrie](#6-biométrie)
7. [Codes d’erreur](#7-codes-derreur)
8. [Annexes](#8-annexes)

---

# 1. Authentification (JWT)

## 1.1 Inscription

**Endpoint**


POST /signup/


Crée un nouveau compte utilisateur.

### Requête

```json
{
  "email": "user@example.com",
  "phone": "0123456789",
  "password": "MotDePasse123!",
  "password2": "MotDePasse123!"
}
Réponse
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "phone": "0123456789"
  },
  "access": "eyJ0eXAiOiJKV1Qi...",
  "refresh": "eyJ0eXAiOiJKV1Qi..."
}
1.2 Connexion
POST /login/

Authentifie un utilisateur et retourne des jetons JWT.

Si le MFA est activé, un mfa_token temporaire est renvoyé.

Requête
{
  "identifier": "user@example.com",
  "password": "MotDePasse123!"
}
Réponse sans MFA
{
  "access": "eyJ0eXAiOiJKV1Qi...",
  "refresh": "eyJ0eXAiOiJKV1Qi...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "phone": "0123456789"
  }
}
Réponse avec MFA
{
  "mfa_required": true,
  "mfa_methods": ["totp", "email"],
  "mfa_token": "eyJ0eXAiOiJKV1Qi..."
}
1.3 Rafraîchissement du token
POST /token/refresh/
Requête
{
  "refresh": "eyJ0eXAiOiJKV1Qi..."
}
Réponse
{
  "access": "eyJ0eXAiOiJKV1Qi..."
}
1.4 Déconnexion
POST /logout/
Header
Authorization: Bearer <access_token>
Requête
{
  "refresh": "eyJ0eXAiOiJKV1Qi..."
}
Réponse
{
  "message": "Déconnexion réussie"
}
2. Multi-Factor Authentication (MFA)
2.1 Activer TOTP
GET /mfa/totp/enable/
Header
Authorization: Bearer <access_token>
Réponse
{
  "secret": "JBSWY3DPEHPK3PXP",
  "uri": "otpauth://totp/MaPlateforme:user@example.com?secret=...",
  "qr_code": "data:image/png;base64,iVBORw0KGgo..."
}
2.2 Valider et activer
POST /mfa/totp/enable/
Requête
{
  "code": "123456"
}
Réponse
{
  "detail": "TOTP activé avec succès"
}
2.3 Désactiver TOTP
POST /mfa/totp/disable/
Requête
{
  "password": "MotDePasse123!"
}
Réponse
{
  "detail": "TOTP désactivé"
}
2.4 Vérifier MFA
POST /mfa/verify/
Requête
{
  "mfa_token": "eyJ0eXAiOiJKV1Qi...",
  "code": "123456",
  "method": "totp"
}
Réponse

Même réponse que /login/ sans MFA.

3. Tableau de bord utilisateur

Tous les endpoints nécessitent un JWT valide.

3.1 Applications autorisées
GET /user/apps/
Réponse
[
  {
    "application_id": 5,
    "name": "Mon Application",
    "client_id": "...",
    "authorized_at": "2026-03-08T10:00:00Z",
    "last_used": "2026-03-08T10:05:00Z",
    "active_sessions": 2
  }
]
3.2 Révoquer une application
DELETE /user/apps/{app_id}/revoke/
Réponse
{
  "message": "Accès révoqué pour 2 session(s)"
}
3.3 Appareils de confiance
GET /user/devices/
Réponse
[
  {
    "id": 3,
    "device_name": "Mon PC",
    "device_fingerprint": "abc123...",
    "last_used": "2026-03-08T10:05:00Z",
    "expires_at": "2026-04-07T10:05:00Z"
  }
]
3.4 Supprimer un appareil
DELETE /user/devices/{id}/

Réponse :

204 No Content
3.5 Historique d’activité
GET /user/activity/
Réponse
[
  {
    "id": 42,
    "event_type": "login_success",
    "description": "Connexion réussie",
    "ip_address": "192.168.1.10",
    "user_agent": "Mozilla/5.0...",
    "created_at": "2026-03-08T10:00:00Z"
  }
]
4. Gestion des clients (multi-tenancy)
4.1 Créer un client
POST /clients/
Requête
{
  "name": "Entreprise ABC",
  "plan": 1,
  "primary_color": "#FF5733"
}
Réponse
{
  "id": 1,
  "name": "Entreprise ABC",
  "slug": "entreprise-abc",
  "plan": 1,
  "logo": null,
  "primary_color": "#FF5733",
  "is_active": true
}
4.2 Détail du client
GET /clients/{id}/
4.3 Mettre à jour un client
PUT /clients/{id}/
4.4 Lister les applications
GET /clients/{id}/apps/
Réponse
[
  {
    "id": 10,
    "application_id": 5,
    "client_id": "...",
    "name": "Mon App",
    "redirect_uris": "https://app.example.com/callback",
    "client_type": "confidential",
    "authorization_grant_type": "authorization-code",
    "is_active": true
  }
]
4.5 Créer une application OAuth2
POST /clients/{id}/apps/
4.6 Gérer l’équipe
GET /clients/{id}/team/
4.7 Ajouter un membre
POST /clients/{id}/team/
Requête
{
  "user_id": 2,
  "role": "member"
}
4.8 Statistiques
GET /clients/{id}/stats/
Réponse
{
  "total_users": 25,
  "active_users_last_30_days": 10,
  "total_applications": 3,
  "authentications_last_30_days": 145
}
5. OAuth2 / OpenID Connect

Les endpoints OAuth2 sont sous :

/o/

Documentation officielle :

https://django-oauth-toolkit.readthedocs.io/

Autorisation
GET /o/authorize/

Paramètres :

response_type=code

client_id

redirect_uri

scope

state

code_challenge

code_challenge_method

Échange de token
POST /o/token/
Authorization Code
grant_type=authorization_code
code=<code>
redirect_uri=<redirect_uri>
client_id=<client_id>
client_secret=<client_secret>
code_verifier=<code_verifier>
Réponse
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "scope": "read write"
}
Révoquer un token
POST /o/revoke_token/
UserInfo (OpenID)
GET /api/userinfo/
Header
Authorization: Bearer <access_token>
Réponse
{
  "sub": "123456789",
  "email": "user@example.com",
  "email_verified": true,
  "phone": "+33123456789",
  "phone_verified": true,
  "name": "Jean Dupont"
}
6. Biométrie
Enrôlement
POST /biometric/enroll/
Champs

image (obligatoire)

video (optionnel)

Réponse
{
  "message": "Profil biométrique enregistré avec succès",
  "created": true,
  "liveness_score": 0.85
}
Connexion biométrique
POST /biometric/login/
Réponse succès
{
  "access": "eyJ0eXAiOiJKV1Qi...",
  "refresh": "eyJ0eXAiOiJKV1Qi...",
  "similarity": 0.92,
  "liveness_score": 0.88
}
Réponse échec
{
  "error": "Visage non reconnu",
  "similarity": 0.45
}
Statut biométrique
GET /biometric/status/
Supprimer profil biométrique
DELETE /biometric/delete/