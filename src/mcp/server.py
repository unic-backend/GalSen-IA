"""
Serveur MCP de GalSen IA (VOLET 34, ch. 09, phase 1).

MCP est devenu la façon dont les outils atteignent les modèles : plus de 18 000
serveurs recensés en un an, OpenAI, Google, Meta et Microsoft compris. ADR-017 §6
décide d'y entrer **par le serveur** : être appelé garde le risque de notre côté,
là où être client charge les descriptions d'outils d'autrui dans notre invite.

## Pas de dépendance

Le protocole est du JSON-RPC 2.0 avec trois méthodes qui comptent — `initialize`,
`tools/list`, `tools/call`. Les implémenter fait une centaine de lignes ; ajouter
une dépendance pour cela contredirait ADR-014 sans rien apporter. Le format est
public, et c'est ce que la plateforme parle déjà pour les fournisseurs de modèles
compatibles.

## Ce que ce serveur garantit

- **Une liste blanche d'exposition** (`exposure.py`) : le terminal, l'écran, le
  contrôle GUI, les fichiers et la base ne sortent pas. Un client MCP manipulé —
  par une page web, par exemple — ne récupère pas les mains de la plateforme.
- **Une identité par appel.** Aucun appel anonyme : le jeton présenté est
  résolu en sujet et en rôle, et un outil non autorisé est refusé.
- **Un événement d'audit par appel**, avec le sujet et l'outil, jamais les
  arguments — ils peuvent porter le texte de quelqu'un.
- **Des erreurs JSON-RPC conformes** : un client doit pouvoir distinguer
  « méthode inconnue » de « outil refusé » de « l'outil a échoué ».
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from .exposure import expose, refusal_reason, report

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "galsen-ia"

# Codes JSON-RPC 2.0. Les trois premiers sont normalisés ; le dernier est dans
# la plage réservée aux erreurs applicatives.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
FORBIDDEN = -32000


class MCPServer:
    """
    Sert le catalogue exposable de GalSen IA en JSON-RPC 2.0.

    Exemple:
        serveur = MCPServer(executor=executeur, resolve_identity=resoudre)
        reponse = serveur.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                 token="cle-de-l-appelant")
    """

    def __init__(
        self,
        executor: Any,
        catalogue: Optional[Dict[str, Dict[str, Any]]] = None,
        resolve_identity: Optional[Callable[[Optional[str]], Optional[Dict[str, Any]]]] = None,
        audit: Optional[Callable[..., None]] = None,
    ) -> None:
        """
        Args:
            executor: Exécuteur d'outils de la plateforme (`ToolExecutor`).
            catalogue: Configurations d'outils ; celles de l'exécuteur sinon.
            resolve_identity: Résout un jeton en `{"subject", "role"}`, ou None
                si le jeton est inconnu. **Sans elle, tout appel est refusé** :
                un serveur qui sert sans identité ne peut ni autoriser ni tracer.
            audit: Fonction d'audit appelée à chaque appel d'outil.
        """
        self._executor = executor
        self._catalogue = catalogue if catalogue is not None else self._catalogue_par_defaut()
        self._resolve_identity = resolve_identity
        self._audit = audit

    def _catalogue_par_defaut(self) -> Dict[str, Dict[str, Any]]:
        """Retourne les outils déclarés, depuis le chargeur de l'exécuteur."""
        chargeur = getattr(self._executor, "tool_loader", None)
        if chargeur is None:
            return {}
        return chargeur.get_all_tool_configs()

    # ------------------------------------------------------------------
    # Entrée
    # ------------------------------------------------------------------

    def handle(self, requete: Any, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Traite une requête JSON-RPC et retourne la réponse.

        Args:
            requete: Objet JSON-RPC déjà décodé.
            token: Jeton présenté par l'appelant.

        Returns:
            La réponse, ou `None` pour une notification — une requête sans `id`
            n'attend pas de réponse, et en renvoyer une romprait le protocole.
        """
        if not isinstance(requete, dict) or requete.get("jsonrpc") != "2.0":
            return self._erreur(None, INVALID_REQUEST, "Requête JSON-RPC 2.0 attendue.")

        identifiant = requete.get("id")
        methode = requete.get("method")
        parametres = requete.get("params") or {}

        if not isinstance(methode, str):
            return self._erreur(identifiant, INVALID_REQUEST, "Méthode absente.")

        traitement = {
            "initialize": self._initialize,
            "tools/list": self._tools_list,
            "tools/call": self._tools_call,
            "ping": lambda p, i: {},
        }.get(methode)

        if traitement is None:
            return self._erreur(
                identifiant, METHOD_NOT_FOUND,
                f"Méthode « {methode} » inconnue. Disponibles : initialize, "
                "tools/list, tools/call, ping.",
            )

        try:
            resultat = traitement(parametres, self._identite(token))
        except _Refus as refus:
            return self._erreur(identifiant, FORBIDDEN, str(refus))
        except Exception as erreur:  # noqa: BLE001 - une panne d'outil est rapportée, pas propagée
            logger.exception("Erreur MCP sur « %s »", methode)
            return self._erreur(identifiant, INTERNAL_ERROR, str(erreur))

        if identifiant is None:
            # Notification : aucune réponse. En renvoyer une casserait le client.
            return None
        return {"jsonrpc": "2.0", "id": identifiant, "result": resultat}

    def handle_line(self, ligne: str, token: Optional[str] = None) -> Optional[str]:
        """
        Traite une ligne JSON, telle qu'un transport stdio la fournit.

        Un JSON illisible rend une erreur `-32700`, jamais une exception : le
        transport ne doit pas tomber parce qu'un octet s'est perdu.
        """
        try:
            requete = json.loads(ligne)
        except ValueError as erreur:
            return json.dumps(self._erreur(None, PARSE_ERROR, f"JSON illisible : {erreur}"))
        reponse = self.handle(requete, token=token)
        return None if reponse is None else json.dumps(reponse, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Méthodes
    # ------------------------------------------------------------------

    def _initialize(self, parametres: Dict[str, Any], identite: Dict[str, Any]) -> Dict[str, Any]:
        """Annonce le serveur, sa version de protocole et ce qu'il sait faire."""
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": SERVER_NAME, "version": _version()},
            "capabilities": {"tools": {"listChanged": False}},
            # L'exposition est annoncée : un client doit savoir qu'une partie du
            # catalogue est retenue, plutôt que de la croire inexistante.
            "instructions": (
                "Catalogue partiellement exposé : les outils qui agissent sur la "
                "machine (terminal, écran, interface, fichiers, base) ne sont pas "
                "servis par MCP."
            ),
        }

    def _tools_list(self, parametres: Dict[str, Any], identite: Dict[str, Any]) -> Dict[str, Any]:
        """Liste les outils exposés, avec leur description."""
        outils: List[Dict[str, Any]] = []
        for tool_id, configuration in sorted(self._catalogue.items()):
            if not configuration.get("enabled", False) or not expose(tool_id):
                continue
            outils.append({
                "name": tool_id,
                "description": configuration.get("description")
                or f"Outil « {tool_id} » de GalSen IA.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string"},
                        "arguments": {"type": "array"},
                    },
                    "required": ["operation"],
                },
            })
        return {"tools": outils}

    def _tools_call(self, parametres: Dict[str, Any], identite: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute un outil exposé, au nom d'une identité connue."""
        nom = parametres.get("name")
        if not isinstance(nom, str) or not nom:
            raise _Refus("Le nom de l'outil est requis.")
        if not expose(nom):
            raise _Refus(refusal_reason(nom))

        configuration = self._catalogue.get(nom)
        if configuration is None or not configuration.get("enabled", False):
            raise _Refus(f"Outil « {nom} » absent du catalogue ou désactivé.")

        arguments = parametres.get("arguments") or {}
        operation = arguments.get("operation")
        if not isinstance(operation, str) or not operation:
            raise _Refus("Une opération est requise.")

        positionnels = arguments.get("args") or []
        nommes = arguments.get("kwargs") or {}

        self._tracer(nom, operation, identite)
        try:
            resultat = self._executor.execute(nom, operation, *positionnels, **nommes)
        except Exception as erreur:  # noqa: BLE001 - l'échec de l'outil est un résultat
            return {
                "content": [{"type": "text", "text": f"Échec de « {nom} » : {erreur}"}],
                "isError": True,
            }

        return {
            "content": [{"type": "text", "text": _en_texte(resultat)}],
            "isError": False,
        }

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _identite(self, token: Optional[str]) -> Dict[str, Any]:
        """
        Résout le jeton présenté, ou refuse.

        Un serveur qui sert sans identité ne peut ni autoriser ni tracer, et
        « le risque est de notre côté » cesse alors d'être vrai.
        """
        if self._resolve_identity is None:
            raise _Refus(
                "Aucun résolveur d'identité : le serveur MCP refuse de servir "
                "anonymement (ADR-010)."
            )
        identite = self._resolve_identity(token)
        if not identite:
            raise _Refus("Jeton absent ou inconnu.")
        return identite

    def _tracer(self, tool_id: str, operation: str, identite: Dict[str, Any]) -> None:
        """
        Inscrit l'appel au journal d'audit.

        **Les arguments ne sont pas tracés** : ils portent le texte de quelqu'un,
        et l'audit persiste.
        """
        if self._audit is None:
            return
        try:
            self._audit(
                action=f"mcp:{tool_id}:{operation}",
                subject=identite.get("subject"),
                metadata={"tool": tool_id, "operation": operation,
                          "role": identite.get("role")},
            )
        except Exception as erreur:  # noqa: BLE001 - une trace ratée ne défait pas l'appel
            logger.warning("Appel MCP exécuté mais non tracé : %s", erreur)

    @staticmethod
    def _erreur(identifiant: Any, code: int, message: str) -> Dict[str, Any]:
        """Construit une erreur JSON-RPC."""
        return {
            "jsonrpc": "2.0", "id": identifiant,
            "error": {"code": code, "message": message},
        }

    def exposure_report(self) -> Dict[str, Any]:
        """Décrit ce que ce serveur laisse passer du catalogue."""
        return report(list(self._catalogue))


class _Refus(PermissionError):
    """Refus applicatif, rendu en erreur JSON-RPC `-32000`."""


def _version() -> str:
    """Retourne la version de la plateforme."""
    try:
        from src.version import __version__

        return __version__
    except Exception:  # noqa: BLE001 - la version est un confort, pas une dépendance
        return "0"


def _en_texte(resultat: Any) -> str:
    """Rend un résultat d'outil sous forme de texte, sans le déformer."""
    if isinstance(resultat, str):
        return resultat
    try:
        return json.dumps(resultat, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(resultat)
