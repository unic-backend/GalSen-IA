"""
Ce que sait faire un modèle local, et **d'où on le sait**.

## Le défaut que ce module corrige

Mesuré le 2026-08-24. `LocalProvider._build_descriptor` construisait le même
descripteur pour tous les modèles : pas de vision, pas d'outils, un contexte de
8192, et trois atouts (`local`, `no_cost`, `offline`) qui n'appartiennent à
aucun vocabulaire de routage. Sur un parc de cinq modèles spécialisés
(`qwen2.5-coder`, `deepseek-r1`, `llava`, `phi3`, `qwen2.5`) :

| Tâche demandée | Modèle retenu |
|---|---|
| `code_generation` | `qwen2.5-coder:14b` — le premier de la liste |
| `reasoning` | `qwen2.5-coder:14b` — le même |
| `conversation` | `qwen2.5-coder:14b` — le même |
| `vision` | **aucun** |
| `document_analysis` | **aucun** |
| `summarization` | **aucun** |

Les trois premières lignes ne sont pas un bon choix suivi de deux erreurs :
c'est **le premier élément de la liste**, trois fois. La couche de sélection
existait, était branchée, et ne sélectionnait rien — parce que les descripteurs
qu'elle comparait étaient identiques.

## Trois origines, jamais confondues

- `measured` — constaté sur `/api/show` du serveur Ollama. La réponse porte un
  tableau `capabilities` (`vision`, `tools`, `completion`…) et un objet
  `model_info` dont une clé se termine par `.context_length`. C'est la seule
  origine qui **constate** au lieu de supposer.
- `declared` — lu dans `config/model_routing.yaml`. Une décision d'exploitation :
  l'opérateur dit quel modèle il a installé et à quoi il sert.
- `default` — rien n'est su. Le contexte reste celui de `/api/tags`, et aucun
  atout n'est annoncé.

**Une mesure écrase une déclaration ; une déclaration écrase un défaut.** Et le
descripteur porte l'origine de chaque champ, parce qu'un contexte de 131072
deviné et un contexte de 131072 mesuré n'autorisent pas les mêmes conclusions.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Clé de la section, dans le fichier de politique de routage. Le catalogue vit
#: là plutôt que dans un fichier à lui : c'est la même décision d'exploitation
#: que le reste — quel modèle sert quelle tâche.
SECTION = "local_models"

#: Les trois origines possibles d'une capacité.
MESURE = "measured"
DECLARE = "declared"
DEFAUT = "default"


@dataclass
class ProfilLocal:
    """
    Ce qu'on sait d'un modèle local, champ par champ, avec son origine.

    `None` n'est pas `False` : un modèle dont la vision n'a pas été constatée
    n'est pas un modèle sans vision. Le premier est une ignorance, le second une
    mesure, et les confondre est exactement ce qui rendait `llava` introuvable.
    """

    #: Atouts, dans le vocabulaire de `preferred_features`.
    features: List[str] = field(default_factory=list)
    #: `True`, `False`, ou `None` quand personne ne l'a constaté.
    supports_vision: Optional[bool] = None
    supports_tools: Optional[bool] = None
    context_window: Optional[int] = None
    #: Origine de chaque champ renseigné : `features`, `supports_vision`,
    #: `supports_tools`, `context_window`.
    origines: Dict[str, str] = field(default_factory=dict)

    def fusionner(self, plus_fort: "ProfilLocal") -> "ProfilLocal":
        """
        Superpose un profil plus fort à celui-ci, champ par champ.

        Un champ absent du profil fort **ne remplace rien** : une mesure qui ne
        dit rien de la vision ne doit pas effacer ce que la configuration en
        disait. C'est la différence entre « mesuré faux » et « non mesuré ».

        Args:
            plus_fort: Profil dont les champs renseignés l'emportent.

        Returns:
            Un nouveau profil ; ni l'un ni l'autre n'est modifié.
        """
        fusion = ProfilLocal(
            features=list(self.features),
            supports_vision=self.supports_vision,
            supports_tools=self.supports_tools,
            context_window=self.context_window,
            origines=dict(self.origines),
        )
        for champ in ("features", "supports_vision", "supports_tools", "context_window"):
            valeur = getattr(plus_fort, champ)
            if valeur is None or valeur == []:
                continue
            setattr(fusion, champ, valeur)
            fusion.origines[champ] = plus_fort.origines.get(champ, MESURE)
        return fusion


class CatalogueLocal:
    """
    Profils déclarés des modèles locaux, reconnus par motif de nom.

    Exemple:
        catalogue = CatalogueLocal()
        profil = catalogue.profil("qwen2.5-coder:14b")
        profil.features  # ["code_generation", "reasoning"]
    """

    def __init__(self, entrees: Optional[List[Dict[str, Any]]] = None):
        """
        Args:
            entrees: Profils déclarés ; ceux de `config/model_routing.yaml`
                si rien n'est fourni.
        """
        self._entrees = entrees if entrees is not None else self._charger()

    @staticmethod
    def _charger() -> List[Dict[str, Any]]:
        """
        Lit la section du fichier de politique.

        Un fichier illisible donne un catalogue vide : la plateforme route moins
        finement, elle ne cesse pas de router.
        """
        from .routing_policy import RoutingPolicy

        chemin = RoutingPolicy._chemin_par_defaut()
        if not os.path.isfile(chemin):
            return []
        try:
            import yaml

            with open(chemin, "r", encoding="utf-8") as fichier:
                politique = yaml.safe_load(fichier) or {}
        except (OSError, ValueError) as erreur:
            logger.warning(
                "Catalogue des modèles locaux illisible (%s) : les modèles "
                "locaux seront routés sans profil.", erreur,
            )
            return []

        entrees = politique.get(SECTION) or []
        return entrees if isinstance(entrees, list) else []

    def profil(self, nom_modele: str) -> ProfilLocal:
        """
        Retourne le profil déclaré d'un modèle.

        Le **premier** motif qui correspond gagne : l'ordre du fichier est la
        règle de priorité, ce qui permet d'y placer `coder` avant `qwen2.5`.

        Args:
            nom_modele: Nom du modèle tel qu'Ollama l'annonce, étiquette
                comprise (`qwen2.5-coder:14b`).

        Returns:
            Le profil déclaré, ou un profil vide si aucun motif ne correspond.
            Un profil vide n'est pas une absence de capacités : c'est une
            absence de connaissance.
        """
        nom = (nom_modele or "").lower()
        for entree in self._entrees:
            motifs = entree.get("matches") or []
            if not any(str(motif).lower() in nom for motif in motifs):
                continue
            return self._profil_de(entree)
        return ProfilLocal()

    @staticmethod
    def _profil_de(entree: Dict[str, Any]) -> ProfilLocal:
        """Construit un profil déclaré à partir d'une entrée du fichier."""
        profil = ProfilLocal()
        features = entree.get("features") or []
        if features:
            profil.features = [str(f) for f in features]
            profil.origines["features"] = DECLARE
        if "supports_vision" in entree:
            profil.supports_vision = bool(entree["supports_vision"])
            profil.origines["supports_vision"] = DECLARE
        if "supports_tools" in entree:
            profil.supports_tools = bool(entree["supports_tools"])
            profil.origines["supports_tools"] = DECLARE
        if entree.get("context_window"):
            profil.context_window = int(entree["context_window"])
            profil.origines["context_window"] = DECLARE
        return profil


def profil_mesure(reponse_api_show: Dict[str, Any]) -> ProfilLocal:
    """
    Traduit une réponse `/api/show` d'Ollama en profil mesuré.

    Deux champs de la réponse sont exploités, et rien n'est déduit du reste :

    - `capabilities` — un tableau où `vision` et `tools` apparaissent quand le
      modèle les possède. Le tableau étant la liste **complète** de ce que le
      serveur reconnaît, l'absence de `vision` y est une mesure négative, pas
      une ignorance : le profil porte donc `False`, pas `None`.
    - `model_info` — un objet de métadonnées GGML dont une clé se termine par
      `.context_length`, préfixée par l'architecture (`llama.context_length`,
      `qwen2.context_length`…). Le préfixe varie d'un modèle à l'autre, donc la
      clé est **cherchée** au lieu d'être devinée.

    Args:
        reponse_api_show: Corps JSON renvoyé par `POST /api/show`.

    Returns:
        Un profil ne portant que ce que la réponse a réellement dit. Une réponse
        sans `capabilities` laisse `supports_vision` à `None` — le serveur n'a
        pas répondu « non », il n'a pas répondu.
    """
    profil = ProfilLocal()

    capacites = reponse_api_show.get("capabilities")
    if isinstance(capacites, list):
        annoncees = {str(c).lower() for c in capacites}
        profil.supports_vision = "vision" in annoncees
        profil.supports_tools = "tools" in annoncees
        profil.origines["supports_vision"] = MESURE
        profil.origines["supports_tools"] = MESURE

    contexte = _contexte_de(reponse_api_show.get("model_info"))
    if contexte:
        profil.context_window = contexte
        profil.origines["context_window"] = MESURE

    return profil


def _contexte_de(model_info: Any) -> Optional[int]:
    """Cherche la clé de contexte, dont le préfixe dépend de l'architecture."""
    if not isinstance(model_info, dict):
        return None
    for cle, valeur in model_info.items():
        if str(cle).endswith(".context_length") and isinstance(valeur, int) and valeur > 0:
            return valeur
    return None
