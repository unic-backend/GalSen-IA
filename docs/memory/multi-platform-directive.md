# Directive Multi-Plateforme — GalSen IA

**Statut** : Permanent — 2026-07-30

## Vision

GalSen IA est une plateforme IA unifiée disponible sur :

- **Web Application**
- **Android Application** (Google Play)
- **iOS Application** (Apple App Store)

## Règles permanentes

1. Le backend doit rester complètement indépendant de la plateforme.
2. Chaque API doit être conçue pour Web, Android et iOS.
3. Ne jamais implémenter de fonctionnalités qui ne fonctionnent que pour le Web.
4. L'authentification doit toujours rester compatible avec les applications mobiles.
5. Les uploads, downloads, streaming, notifications et futures fonctionnalités doivent fonctionner correctement sur Web, Android et iOS.
6. Tout nouveau endpoint doit être mobile-friendly.
7. Les réponses doivent rester propres, stables et versionnables.
8. Éviter les choix d'architecture qui nécessiteraient de réécrire le backend pour les applications mobiles.
9. Quand plusieurs solutions techniques existent, préférer celle qui supporte le mieux Web + Android + iOS depuis le même backend.
10. Garder le projet prêt pour une future publication sur Google Play et Apple App Store.
11. Garder le support futur pour : Push Notifications, synchronisation offline, authentification sécurisée, tâches en arrière-plan, optimisation des performances mobiles.
12. Si une implémentation future pouvait impacter négativement la compatibilité Web, Android ou iOS, le signaler explicitement avant de l'implémenter.
