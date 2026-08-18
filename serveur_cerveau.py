#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cerveau GalSen IA — Serveur REST local.

Point d'entrée pour le Cerveau GalSen IA.
- Expose les engines GalSen IA via API REST
- Utilise Ollama (qwen2.5-coder:14b) pour la génération
- Fournit état de santé, chat, et introspection des engines

Démarrage :
    python serveur_cerveau.py
    # ou via le Lancer_GalSen_IA.bat
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Ajouter src au chemin pour importer les engines
PROJET = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJET))
sys.path.insert(0, str(PROJET / "src"))

# Configuration
HOTE = os.environ.get("GALSEN_HOST", "0.0.0.0")
PORT = int(os.environ.get("GALSEN_PORT", "8000"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODELE = os.environ.get("GALSEN_MODELE", "qwen2.5-coder:14b")
HISTORIQUE_MAX = 50  # messages conservés en mémoire

# --- Import optionnel des engines GalSen IA ---
# On les importe ici pour que le serveur les ait en mémoire.
# Si un engine manque, on le signale sans planter.

ENGINES_DISPO = {}

# Les engines GalSen IA utilisent des chemins d'import explicites
# (leurs __init__.py sont vides, il faut importer les classes internes)
try:
    from memory_engine.memory_manager import MemoryManager
    ENGINES_DISPO["memory"] = MemoryManager()
    print("  [CERVEAN] Memory Engine charge")
except Exception as e:
    ENGINES_DISPO["memory"] = None
    print(f"  [CERVEAN] Memory Engine : {e}")

try:
    from knowledge_engine.knowledge_retriever import KnowledgeRetriever
    ENGINES_DISPO["knowledge"] = KnowledgeRetriever._get_instance() \
        if hasattr(KnowledgeRetriever, '_get_instance') else KnowledgeRetriever
    # Si c'est une classe abstraite, on crée une instance fonctionnelle via le manager
    try:
        from knowledge_engine import KnowledgeManagerImpl
        ENGINES_DISPO["knowledge"] = KnowledgeManagerImpl()
    except Exception:
        pass
    if not ENGINES_DISPO["knowledge"]:
        ENGINES_DISPO["knowledge"] = KnowledgeRetriever
    print("  [CERVEAN] Knowledge Engine charge")
except Exception as e:
    ENGINES_DISPO["knowledge"] = None
    print(f"  [CERVEAN] Knowledge Engine : {e}")

try:
    from model_engine.model_manager import ModelManagerImpl
    ENGINES_DISPO["model"] = ModelManagerImpl()
    print("  [CERVEAN] Model Engine charge")
except Exception as e:
    # Fallback: InMemoryModelStore
    try:
        from model_engine.model_store import InMemoryModelStore
        ENGINES_DISPO["model"] = InMemoryModelStore()
        print("  [CERVEAN] Model Store (InMemory) charge")
    except Exception as e2:
        ENGINES_DISPO["model"] = None
        print(f"  [CERVEAN] Model Engine : {e} / {e2}")

try:
    from tool.tool_engine import ToolEngine
    ENGINES_DISPO["tool"] = ToolEngine("tools/tools.yaml")
    print("  [CERVEAN] Tool Engine charge")
except Exception as e:
    ENGINES_DISPO["tool"] = None
    print(f"  [CERVEAN] Tool Engine : {e}")

try:
    from document_intelligence_engine import DocumentManagerImpl
    ENGINES_DISPO["document"] = DocumentManagerImpl()
    print("  [CERVEAN] Document Intelligence Engine charge")
except Exception as e:
    ENGINES_DISPO["document"] = None
    print(f"  [CERVEAN] Document Engine : {e}")

try:
    from vision_intelligence_engine.vision_manager import VisionManagerImpl
    ENGINES_DISPO["vision"] = VisionManagerImpl()
    print("  [CERVEAN] Vision Intelligence Engine charge")
except Exception as e:
    ENGINES_DISPO["vision"] = None
    print(f"  [CERVEAN] Vision Engine : {e}")

try:
    from router.config_loader import ConfigLoader
    from router.agent_loader import AgentLoader
    ENGINES_DISPO["router"] = {
        "config": ConfigLoader("config/settings.yaml"),
        "agents": AgentLoader("agents/registry.yaml"),
    }
    print("  [CERVEAN] Router Engine charge")
except Exception as e:
    ENGINES_DISPO["router"] = None
    print(f"  [CERVEAN] Router Engine : {e}")

# --- Mémoire de conversation (in-memory) ---
historique: list[dict] = []


# ----------------------------------------------------------------
#  Appel à Ollama
# ----------------------------------------------------------------
def ollama_generate(prompt: str, system: str = "", contexte: str = "") -> str:
    """
    Envoie une requête à Ollama et retourne la réponse texte.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})

    # Contexte du projet si fourni
    if contexte:
        messages.append({"role": "user", "content": f"[CONTEXTE PROJET]\n{contexte}\n\n---\n\n"})

    # Derniers tours de l'historique (concis)
    for msg in historique[-6:]:  # garder les 6 derniers échanges
        messages.append(msg)

    messages.append({"role": "user", "content": prompt})

    corps = {
        "model": MODELE,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 4096,
        }
    }

    requete = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(corps).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(requete, timeout=120) as reponse:
            resultat = json.loads(reponse.read().decode("utf-8"))
            return resultat.get("message", {}).get("content", "")
    except urllib.error.HTTPError as e:
        return f"[ERREUR OLLAMA HTTP {e.code}] {e.read().decode('utf-8', errors='replace')}"
    except urllib.error.URLError:
        return "[ERREUR] Ollama n'est pas joignable. Vérifie qu'il tourne (ollama serve)."
    except Exception as e:
        return f"[ERREUR] {e}"


# ----------------------------------------------------------------
#  Interface REST avec FastAPI
# ----------------------------------------------------------------
tentative_fastapi = False
app = None

if not tentative_fastapi:
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel

        app = FastAPI(
            title="Cerveau GalSen IA",
            description="API REST du cerveau local GalSen IA — moteurs + Ollama",
            version="1.0.0",
        )

        class ChatRequest(BaseModel):
            message: str
            system: str = ""
            contexte: str = ""

        class ChatResponse(BaseModel):
            reponse: str
            messages_utilises: int = 0

        @app.get("/")
        async def racine():
            return {
                "cerveau": "GalSen IA",
                "modele": MODELE,
                "engines": {k: v is not None for k, v in ENGINES_DISPO.items()},
                "statut": "actif",
                "docs": "/docs",
            }

        @app.get("/health")
        async def sante():
            """Retourne l'état de santé du serveur et de ses dépendances."""
            ollama_ok = False
            try:
                with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5):
                    ollama_ok = True
            except Exception:
                pass

            return {
                "serveur": "actif",
                "ollama": ollama_ok,
                "modele": MODELE,
                "engines": sum(1 for v in ENGINES_DISPO.values() if v is not None),
                "engines_total": len(ENGINES_DISPO),
                "historique": len(historique),
            }

        @app.get("/engines")
        async def lister_engines():
            """Liste tous les engines et leur état."""
            return {
                k: {
                    "disponible": v is not None,
                    "type": type(v).__name__ if v else None,
                }
                for k, v in ENGINES_DISPO.items()
            }

        @app.get("/models")
        async def lister_modeles():
            """Liste les modèles disponibles dans Ollama."""
            try:
                with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
                    data = json.loads(r.read().decode("utf-8"))
                    return {"modeles": data.get("models", [])}
            except Exception as e:
                return {"modeles": [], "erreur": str(e)}

        @app.post("/chat", response_model=ChatResponse)
        async def chat(requete: ChatRequest):
            """
            Envoie un message au cerveau GalSen IA via Ollama.
            """
            if not requete.message.strip():
                raise HTTPException(status_code=400, detail="Message vide")

            # Charger les instructions système par défaut
            system = requete.system
            if not system:
                fichier_system = PROJET / "prompts" / "systeme.md"
                if fichier_system.exists():
                    system = fichier_system.read_text("utf-8")

            # Ajouter l'état des engines dans le contexte
            etat_engines = "\n".join(
                f"- {k}: {'✅ actif' if v else '❌ indisponible'}"
                for k, v in ENGINES_DISPO.items()
            )
            contexte_base = (
                f"[ETAT ENGINES GALSEN IA]\n{etat_engines}\n\n"
                f"[REPERTOIRE PROJET] {PROJET}\n"
                f"[MODELE] {MODELE} sur {OLLAMA_URL}\n"
            )
            if requete.contexte:
                contexte_base += f"\n[CONTEXTE SUPPLEMENTAIRE]\n{requete.contexte}\n"

            reponse = ollama_generate(
                prompt=requete.message,
                system=system,
                contexte=contexte_base,
            )

            # Enregistrer dans l'historique
            historique.append({"role": "user", "content": requete.message})
            historique.append({"role": "assistant", "content": reponse})
            if len(historique) > HISTORIQUE_MAX * 2:
                del historique[:len(historique) - HISTORIQUE_MAX * 2]

            return ChatResponse(reponse=reponse, messages_utilises=len(historique))

        @app.post("/reinitialiser")
        async def reinitialiser():
            """Vide l'historique de conversation."""
            historique.clear()
            return {"statut": "historique vide"}

        tentative_fastapi = True
        print("[CERVEAN] Interface FastAPI initialisee")

    except ImportError as e:
        print(f"[CERVEAN] FastAPI non disponible ({e}) — mode CLI uniquement")


# ----------------------------------------------------------------
#  Mode CLI (quand FastAPI n'est pas disponible)
# ----------------------------------------------------------------
def mode_cli():
    """Mode conversation en ligne de commande directe."""
    fichier_system = PROJET / "prompts" / "systeme.md"
    system = fichier_system.read_text("utf-8") if fichier_system.exists() else ""

    print("\n" + "=" * 60)
    print("  🧠 Cerveau GalSen IA — Mode CLI")
    print(f"  Modèle : {MODELE}")
    print("  Tape 'quit' pour quitter, 'reset' pour vider l'historique")
    print("=" * 60 + "\n")

    while True:
        try:
            entree = input("👤 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Au revoir.")
            break

        if not entree:
            continue
        if entree.lower() in ("quit", "exit", "q"):
            print("👋 Au revoir.")
            break
        if entree.lower() == "reset":
            historique.clear()
            print("🧹 Historique vide.")
            continue

        # Contexte des engines
        etat = "\n".join(
            f"- {k}: {'actif' if v else 'indisponible'}"
            for k, v in ENGINES_DISPO.items()
        )
        contexte = f"[ETAT ENGINES]\n{etat}\n"

        debut = time.time()
        reponse = ollama_generate(entree, system=system, contexte=contexte)
        duree = time.time() - debut

        print(f"\n🧠 Cerveau ({duree:.1f}s) >")
        print(reponse)
        print()

        # Historique
        historique.append({"role": "user", "content": entree})
        historique.append({"role": "assistant", "content": reponse})
        if len(historique) > HISTORIQUE_MAX * 2:
            del historique[:len(historique) - HISTORIQUE_MAX * 2]


# ----------------------------------------------------------------
#  Point d'entrée
# ----------------------------------------------------------------
if __name__ == "__main__":
    if app is not None:
        import uvicorn
        print(f"[CERVEAN] Demarrage du serveur GalSen IA sur {HOTE}:{PORT}")
        print(f"[CERVEAN] API : http://{HOTE}:{PORT}")
        print(f"[CERVEAN] Docs : http://{HOTE}:{PORT}/docs")
        print(f"[CERVEAN] Modele : {MODELE}")
        uvicorn.run(app, host=HOTE, port=PORT, log_level="info")
    else:
        mode_cli()