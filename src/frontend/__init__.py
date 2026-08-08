"""
Interface d'administration web GalSen IA.

Dashboard minimal monté comme sous-application FastAPI sur `/admin`.
Utilise Jinja2 pour le rendu côté serveur.
"""

from .dashboard import create_dashboard_app

__all__ = ["create_dashboard_app"]