"""
Research Agent for GalSen IA.

Gathers information about a request from three sources, in order of trust: the
knowledge base (verified, project-owned), the shared memory of the current
request (what other agents already found), and the web (unverified, so always
reported with its source).

Documents referenced in the request are read through the Document Intelligence
Engine, and images through the Vision Engine.
"""

import os
import re
from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module


class ResearcherAgent(BaseAgent):
    """Agent qui rassemble et recoupe l'information nécessaire à une demande."""

    agent_id = "researcher"
    required_engines = ("knowledge", "memory", "tool", "document", "vision")

    # Extensions reconnues comme documents et comme images dans une demande
    DOCUMENT_EXTENSIONS = (".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv", ".html", ".json")
    IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")

    # Repère un chemin de fichier dans un texte libre
    _PATH_PATTERN = re.compile(r'[\w./\\-]+\.\w{2,5}')

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Rassemble l'information disponible sur la demande.

        Args:
            context: Contexte d'exécution

        Returns:
            Sources consultées, constats établis et lacunes restantes
        """
        request = context.request_text()

        knowledge_results = context.search_knowledge(request, limit=5)
        memory_results = context.recall(request, limit=5)
        web_results = context.search_web(request, max_results=5)
        documents = self._analyze_referenced_documents(context, request)
        images = self._analyze_referenced_images(context, request)

        findings = self._build_findings(knowledge_results, web_results, documents)

        # Les résultats web sont conservés en connaissance pour éviter de
        # relancer la même recherche au prochain passage
        self._store_web_findings(context, web_results)

        return {
            "query": request,
            "sources_consulted": {
                "knowledge_base": len(knowledge_results),
                "shared_memory": len(memory_results),
                "web": len(web_results),
                "documents": len(documents),
                "images": len(images),
            },
            "findings": findings,
            "documents": documents,
            "images": images,
            "web_results": web_results,
            "gaps": self._identify_gaps(knowledge_results, web_results, documents),
        }

    def _analyze_referenced_documents(self, context: AgentContext, request: str) -> List[Dict[str, Any]]:
        """Analyse les documents dont le chemin apparaît dans la demande."""
        analyses: List[Dict[str, Any]] = []

        for path in self._extract_paths(request, self.DOCUMENT_EXTENSIONS):
            analysis = context.analyze_document(path)
            if analysis:
                analyses.append(analysis)

        return analyses

    def _analyze_referenced_images(self, context: AgentContext, request: str) -> List[Dict[str, Any]]:
        """Analyse les images dont le chemin apparaît dans la demande."""
        analyses: List[Dict[str, Any]] = []

        for path in self._extract_paths(request, self.IMAGE_EXTENSIONS):
            analysis = context.analyze_image(path)
            if analysis:
                analyses.append({"path": path, "analysis": analysis})

        return analyses

    def _extract_paths(self, text: str, extensions: tuple) -> List[str]:
        """Relève les chemins de fichiers existants correspondant aux extensions."""
        candidates = self._PATH_PATTERN.findall(text)
        return [
            candidate for candidate in candidates
            if candidate.lower().endswith(extensions) and os.path.isfile(candidate)
        ]

    def _build_findings(
        self,
        knowledge_results: List[Dict[str, Any]],
        web_results: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Assemble les résultats en constats attribués à leur source.

        Chaque constat porte son origine et son niveau de confiance : une
        information issue du web n'a pas le même statut qu'une connaissance
        validée du projet.
        """
        findings: List[Dict[str, Any]] = []

        for item in knowledge_results:
            findings.append({
                "source": "knowledge_base",
                "content": item["content"],
                "confidence": item["confidence"],
                "verified": True,
            })

        for document in documents:
            findings.append({
                "source": f"document:{document.get('title')}",
                "content": document.get("summary", ""),
                "confidence": 0.8,
                "verified": True,
            })

        for result in web_results:
            findings.append({
                "source": result.get("url") or result.get("link") or "web",
                "content": result.get("snippet") or result.get("title") or "",
                # Une source web n'est pas vérifiée : la confiance reste basse
                "confidence": 0.4,
                "verified": False,
            })

        return findings

    def _store_web_findings(self, context: AgentContext, web_results: List[Dict[str, Any]]) -> None:
        """Conserve les résultats web dans la base de connaissances."""
        for result in web_results[:3]:
            content = result.get("snippet") or result.get("title")
            if not content:
                continue

            context.add_knowledge(
                content=content,
                tags=["web", "researcher", "unverified"],
                confidence=0.4,
            )

    def _identify_gaps(
        self,
        knowledge_results: List[Dict[str, Any]],
        web_results: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
    ) -> List[str]:
        """Signale ce que la recherche n'a pas permis d'établir."""
        gaps: List[str] = []

        if not knowledge_results:
            gaps.append("Aucune connaissance interne sur ce sujet: la base doit être enrichie")
        if not web_results:
            gaps.append("Aucun résultat web: recherche indisponible ou requête trop spécifique")
        if not documents:
            gaps.append("Aucun document source analysé: les constats reposent sur des sources indirectes")

        return gaps


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter

    Returns:
        Résultat de l'agent au format standard
    """
    return run_agent_module(ResearcherAgent, input_data)
