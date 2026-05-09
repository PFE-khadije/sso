# User Stories

## Rôle : Utilisateur final

1. En tant qu’**utilisateur final**, je veux m’inscrire avec mon email et un mot de passe, afin de créer un compte sur la plateforme.
2. En tant qu’**utilisateur final**, je veux m’inscrire avec mon numéro de téléphone et un mot de passe, afin de créer un compte sur la plateforme.
3. En tant qu’**utilisateur final**, je veux m’inscrire avec mon authentification biométrique (reconnaissance faciale), afin de créer un compte sur la plateforme.
4. En tant qu’**utilisateur final**, je veux me connecter avec mon email et mon mot de passe, afin d’accéder aux applications utilisant le SSO.
5. En tant qu’**utilisateur final**, je veux me connecter avec mon numéro de téléphone et mon mot de passe, afin d’accéder aux applications utilisant le SSO.
6. En tant qu’**utilisateur final**, je veux me connecter avec mon authentification biométrique (reconnaissance faciale), afin d’accéder aux applications utilisant le SSO.
7. En tant qu’**utilisateur final**, je veux recevoir un email de confirmation après mon inscription, afin de vérifier mon adresse électronique.
8. En tant qu’**utilisateur final**, je veux recevoir un SMS de confirmation après mon inscription, afin de vérifier mon numéro de téléphone.
9. En tant qu’**utilisateur final**, je veux réinitialiser mon mot de passe si je l’ai oublié, afin de retrouver l’accès à mon compte.
10. En tant qu’**utilisateur final**, je veux activer la double authentification via une application (Google Authenticator), afin de renforcer la sécurité de mon compte.
11. En tant qu’**utilisateur final**, je veux activer la double authentification par SMS, afin de renforcer la sécurité de mon compte.
12. En tant qu’**utilisateur final**, je veux activer la double authentification par email, afin de renforcer la sécurité de mon compte.
13. En tant qu’**utilisateur final**, je veux recevoir un code de vérification par email lors de la connexion si j’ai activé le MFA, afin de valider mon identité.
14. En tant qu’**utilisateur final**, je veux recevoir un code de vérification par SMS lors de la connexion si j’ai activé le MFA, afin de valider mon identité.
15. En tant qu’**utilisateur final**, je veux gérer mes méthodes MFA (ajout/suppression), afin de contrôler ma sécurité.
16. En tant qu’**utilisateur final**, je veux me déconnecter de toutes mes sessions à distance, afin de protéger mon compte en cas de perte de l’appareil.
17. En tant qu’**utilisateur final**, je veux recevoir une alerte (email/SMS) si une connexion suspecte est détectée sur mon compte, afin de réagir rapidement en cas d’intrusion.
18. En tant qu’**utilisateur final**, je veux voir la liste de mes sessions actives (appareils, localisation, date), afin de vérifier qu’aucune session inconnue n’est en cours.
19. En tant qu’**utilisateur final**, je veux marquer un appareil comme “de confiance”, afin de ne pas avoir à refaire le MFA à chaque connexion sur cet appareil.

## Rôle : Développeur intégrateur

20. En tant que **développeur**, je veux enregistrer une nouvelle application cliente via une interface d’administration, afin d’obtenir un `client_id` et un `client_secret`.
21. En tant que **développeur**, je veux utiliser le flow Authorization Code avec PKCE pour connecter mes utilisateurs depuis une application web ou mobile, afin de respecter les bonnes pratiques de sécurité.
22. En tant que **développeur**, je veux échanger un code d’autorisation contre un token d’accès via un endpoint sécurisé, afin d’accéder aux ressources protégées.
23. En tant que **développeur**, je veux rafraîchir un token d’accès expiré à l’aide d’un refresh token, afin de maintenir une session active sans ressaisir les identifiants.
24. En tant que **développeur**, je veux révoquer un token (accès ou rafraîchissement), afin de permettre aux utilisateurs de terminer une session.
25. En tant que **développeur**, je veux obtenir les informations de l’utilisateur (email, téléphone, nom, etc.) via un endpoint UserInfo standard (OpenID Connect), afin de personnaliser l’expérience dans mon application.
26. En tant que **développeur**, je veux une documentation complète et des exemples de code, afin d’intégrer rapidement le SSO.

## Rôle : Administrateur de la plateforme

27. En tant qu’**administrateur**, je veux visualiser la liste des clients OAuth enregistrés, afin de gérer les accès aux applications.
28. En tant qu’**administrateur**, je veux activer/désactiver un client OAuth, afin de bloquer une application compromise.
29. En tant qu’**administrateur**, je veux consulter les logs d’authentification (succès, échecs, MFA, etc.), afin de détecter des activités suspectes.
30. En tant qu’**administrateur**, je veux définir des règles de mot de passe (complexité, expiration), afin de renforcer la sécurité globale.
31. En tant qu’**administrateur**, je veux pouvoir suspendre un utilisateur, afin de bloquer un compte en cas d’abus.
32. En tant qu’**administrateur**, je veux visualiser les méthodes MFA activées par les utilisateurs, afin de superviser la sécurité globale.
33. En tant qu’**administrateur**, je veux forcer la réauthentification d’un utilisateur suspect, afin de protéger la plateforme.
34. En tant qu’**administrateur**, je veux activer une authentification adaptative (risk-based authentication) basée sur des critères (localisation, heure, appareil), afin de renforcer la sécurité sans gêner les utilisateurs légitimes.

## Rôle : Administrateur d’organisation (client SaaS)

35. En tant qu’**administrateur d’organisation**, je veux gérer les utilisateurs de mon entreprise (création, suspension, attribution de rôles), afin de contrôler les accès.
36. En tant qu’**administrateur d’organisation**, je veux personnaliser le branding de la page de connexion (logo, couleurs) pour mes employés, afin de refléter l’identité de mon entreprise.