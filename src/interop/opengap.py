"""
OpenGAP : lecture et écriture d'agents au format ouvert (ADR-023).

OpenGAP décrit un agent par un dossier contenant deux fichiers obligatoires —
`agent.yaml` (le manifeste) et `SOUL.md` (l'identité). C'est un format de
texte, versionné avec le code, lisible par Claude Code, CrewAI ou LangChain.

Ce module implémente **la spécification**, pas le programme de référence : ce
dernier est écrit en TypeScript, et ADR-001 fixe Python. La spécification que
nous suivons est recopiée dans `third_party/opengap/NOTICE.md` ; la licence MIT
d'origine est à côté. Rien ici ne dépend du dépôt amont : s'il est supprimé,
la plateforme continue.

Ce que le module fait :

- **Exporter** les agents de `agents/registry.yaml` au format OpenGAP, ce qui
  les rend utilisables hors de GalSen IA.
- **Lire** un agent OpenGAP écrit ailleurs, en le validant.

Ce que le module ne fait **pas**, et c'est délibéré : exécuter quoi que ce soit
d'un dossier importé. Un agent importé est une **donnée**. Le faire tourner
suppose une classe Python déclarée dans `agents/registry.yaml` par un humain.
La note de sécurité complète est dans `third_party/opengap/NOTICE.md`.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

# Version de la spécification que ce module implémente.
SPEC_VERSION = "0.1.0"

FICHIER_MANIFESTE = "agent.yaml"
FICHIER_AME = "SOUL.md"

# Contraintes imposées par la spécification.
MOTIF_NOM = re.compile(r"^[a-z][a-z0-9-]*$")
MOTIF_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

# Un manifeste est un fichier de description : au-delà, c'est autre chose.
# La borne évite qu'un dossier hostile fasse gonfler la mémoire à la lecture.
TAILLE_MAX_FICHIER = 1024 * 1024

# Champs que ce module interprète. Tous les autres sont conservés tels quels
# (`extends`, `dependencies`, `runtime`, `delegation`, `a2a`, `compliance`…) :
# un agent écrit ailleurs ne doit rien perdre en passant par ici.
CHAMPS_INTERPRETES = frozenset({
    "spec_version", "name", "version", "description",
    "author", "license", "model", "skills", "tools", "tags", "metadata",
})

# Types admis par la spécification pour les valeurs de `metadata`.
TYPES_METADATA = (str, int, float, bool)


class OpenGAPError(ValueError):
    """Manifeste invalide, illisible, ou dossier incomplet."""


@dataclass(frozen=True)
class OpenGAPAgent:
    """
    Un agent au format OpenGAP, tel que lu ou tel qu'il sera écrit.

    Attributes:
        name: Identifiant kebab-case de l'agent.
        version: Version sémantique de l'agent.
        description: Description d'une ligne.
        soul: Contenu de `SOUL.md`.
        spec_version: Version de spécification visée par le manifeste.
        author: Personne ou organisation à l'origine de l'agent.
        license: Identifiant SPDX de la licence de l'agent.
        model_preferred: Modèle souhaité, sans garantie qu'il soit disponible.
        model_fallback: Modèles de repli, dans l'ordre.
        skills: Compétences déclarées.
        tools: Outils déclarés.
        tags: Étiquettes de classement.
        metadata: Métadonnées libres (chaînes, nombres, booléens).
        extensions: Sections non interprétées, conservées à l'identique.
    """

    name: str
    version: str
    description: str
    soul: str
    spec_version: str = SPEC_VERSION
    author: Optional[str] = None
    license: Optional[str] = None
    model_preferred: Optional[str] = None
    model_fallback: Tuple[str, ...] = ()
    skills: Tuple[str, ...] = ()
    tools: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def to_manifest(self) -> Dict[str, Any]:
        """
        Construit le dictionnaire `agent.yaml` correspondant.

        Les champs vides sont omis : un manifeste ne doit pas déclarer un
        modèle préféré nul ou une liste de compétences vide, qui se liraient
        comme des choix alors qu'ils sont des absences.

        Returns:
            Le manifeste, dans l'ordre de lecture de la spécification.
        """
        manifeste: Dict[str, Any] = {
            "spec_version": self.spec_version,
            "name": self.name,
            "version": self.version,
            "description": self.description,
        }
        if self.author:
            manifeste["author"] = self.author
        if self.license:
            manifeste["license"] = self.license

        modele: Dict[str, Any] = {}
        if self.model_preferred:
            modele["preferred"] = self.model_preferred
        if self.model_fallback:
            modele["fallback"] = list(self.model_fallback)
        if modele:
            manifeste["model"] = modele

        if self.skills:
            manifeste["skills"] = list(self.skills)
        if self.tools:
            manifeste["tools"] = list(self.tools)
        if self.tags:
            manifeste["tags"] = list(self.tags)
        if self.metadata:
            manifeste["metadata"] = dict(self.metadata)

        # Les sections que nous n'interprétons pas repartent telles quelles.
        manifeste.update({k: v for k, v in self.extensions.items()})
        return manifeste


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------

def valider_manifeste(donnees: Any) -> List[str]:
    """
    Contrôle un manifeste chargé et retourne la liste des fautes trouvées.

    La fonction ne lève pas : elle rend **toutes** les fautes d'un coup, pour
    qu'un auteur d'agent corrige son fichier en une passe au lieu de dix.

    Args:
        donnees: Le contenu de `agent.yaml`, déjà désérialisé.

    Returns:
        Les messages d'erreur, en français. Liste vide si le manifeste est valide.
    """
    if not isinstance(donnees, dict):
        return ["Le manifeste doit être un objet YAML (clés → valeurs)."]

    fautes: List[str] = []

    nom = donnees.get("name")
    if not isinstance(nom, str) or not nom:
        fautes.append("`name` est obligatoire et doit être une chaîne.")
    elif not MOTIF_NOM.match(nom):
        fautes.append(
            f"`name` doit être en kebab-case ({MOTIF_NOM.pattern}) ; reçu « {nom} »."
        )

    version = donnees.get("version")
    if not isinstance(version, str) or not version:
        fautes.append("`version` est obligatoire et doit être une chaîne.")
    elif not MOTIF_VERSION.match(version):
        fautes.append(
            f"`version` doit être une version sémantique X.Y.Z ; reçu « {version} »."
        )

    description = donnees.get("description")
    if not isinstance(description, str) or not description.strip():
        fautes.append("`description` est obligatoire et ne peut pas être vide.")

    fautes.extend(_fautes_de_listes(donnees))
    fautes.extend(_fautes_de_modele(donnees.get("model")))
    fautes.extend(_fautes_de_metadata(donnees.get("metadata")))
    return fautes


def _fautes_de_listes(donnees: Mapping[str, Any]) -> List[str]:
    """Contrôle les champs qui doivent être des listes de chaînes."""
    fautes = []
    for champ in ("skills", "tools", "tags"):
        valeur = donnees.get(champ)
        if valeur is None:
            continue
        if not isinstance(valeur, list) or not all(isinstance(e, str) for e in valeur):
            fautes.append(f"`{champ}` doit être une liste de chaînes.")
    return fautes


def _fautes_de_modele(modele: Any) -> List[str]:
    """Contrôle la section `model` et ses contraintes numériques."""
    if modele is None:
        return []
    if not isinstance(modele, dict):
        return ["`model` doit être un objet."]

    fautes = []
    prefere = modele.get("preferred")
    if prefere is not None and not isinstance(prefere, str):
        fautes.append("`model.preferred` doit être une chaîne.")

    repli = modele.get("fallback")
    if repli is not None and (
        not isinstance(repli, list) or not all(isinstance(e, str) for e in repli)
    ):
        fautes.append("`model.fallback` doit être une liste de chaînes.")

    contraintes = modele.get("constraints")
    if contraintes is None:
        return fautes
    if not isinstance(contraintes, dict):
        fautes.append("`model.constraints` doit être un objet.")
        return fautes

    temperature = contraintes.get("temperature")
    # `bool` est un `int` en Python : le refuser explicitement évite qu'un
    # `true` passe pour une température valide.
    if temperature is not None and (
        isinstance(temperature, bool)
        or not isinstance(temperature, (int, float))
        or not 0.0 <= temperature <= 2.0
    ):
        fautes.append("`model.constraints.temperature` doit être un nombre entre 0.0 et 2.0.")

    max_tokens = contraintes.get("max_tokens")
    if max_tokens is not None and (
        isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0
    ):
        fautes.append("`model.constraints.max_tokens` doit être un entier positif.")

    return fautes


def _fautes_de_metadata(metadata: Any) -> List[str]:
    """Contrôle que `metadata` ne porte que des valeurs simples."""
    if metadata is None:
        return []
    if not isinstance(metadata, dict):
        return ["`metadata` doit être un objet."]
    mauvaises = [
        cle for cle, valeur in metadata.items() if not isinstance(valeur, TYPES_METADATA)
    ]
    if mauvaises:
        return [
            "`metadata` n'accepte que des chaînes, nombres ou booléens ; "
            f"en faute : {', '.join(sorted(str(c) for c in mauvaises))}."
        ]
    return []


# ----------------------------------------------------------------------
# Lecture
# ----------------------------------------------------------------------

def lire_agent(dossier: Any) -> OpenGAPAgent:
    """
    Lit un dossier d'agent OpenGAP.

    Rien n'est exécuté : le YAML est chargé en mode sûr, `hooks/` et `tools/`
    ne sont ni lus ni lancés, et ni `extends` ni `dependencies` ne déclenchent
    de téléchargement. Lire un agent ne doit jamais avoir d'effet.

    Args:
        dossier: Chemin du dossier contenant `agent.yaml` et `SOUL.md`.

    Returns:
        L'agent lu, avec ses sections non interprétées conservées.

    Raises:
        OpenGAPError: Fichier manquant, YAML illisible, ou manifeste invalide.
    """
    chemin = Path(dossier)
    manifeste_brut = _lire_texte(chemin / FICHIER_MANIFESTE)
    ame = _lire_texte(chemin / FICHIER_AME)

    try:
        donnees = yaml.safe_load(manifeste_brut)
    except yaml.YAMLError as erreur:
        raise OpenGAPError(f"{chemin / FICHIER_MANIFESTE} : YAML illisible — {erreur}") from erreur

    fautes = valider_manifeste(donnees)
    if not ame.strip():
        fautes.append(f"`{FICHIER_AME}` doit contenir au moins un paragraphe non vide.")
    if fautes:
        raise OpenGAPError(f"{chemin} : " + " ".join(fautes))

    modele = donnees.get("model") or {}
    return OpenGAPAgent(
        name=donnees["name"],
        version=donnees["version"],
        description=donnees["description"],
        soul=ame,
        spec_version=donnees.get("spec_version", SPEC_VERSION),
        author=donnees.get("author"),
        license=donnees.get("license"),
        model_preferred=modele.get("preferred"),
        model_fallback=tuple(modele.get("fallback") or ()),
        skills=tuple(donnees.get("skills") or ()),
        tools=tuple(donnees.get("tools") or ()),
        tags=tuple(donnees.get("tags") or ()),
        metadata=dict(donnees.get("metadata") or {}),
        extensions={k: v for k, v in donnees.items() if k not in CHAMPS_INTERPRETES},
    )


def _lire_texte(chemin: Path) -> str:
    """Lit un fichier obligatoire du dossier, en bornant sa taille."""
    if not chemin.is_file():
        raise OpenGAPError(f"{chemin} : fichier obligatoire absent.")
    if chemin.stat().st_size > TAILLE_MAX_FICHIER:
        raise OpenGAPError(
            f"{chemin} : {chemin.stat().st_size} octets, au-delà de la borne "
            f"de {TAILLE_MAX_FICHIER} octets attendue pour un fichier de description."
        )
    return chemin.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Écriture
# ----------------------------------------------------------------------

def ecrire_agent(agent: OpenGAPAgent, destination: Any) -> Path:
    """
    Écrit un agent dans `destination/<nom>/`.

    Args:
        agent: L'agent à écrire.
        destination: Dossier parent ; il est créé s'il n'existe pas.

    Returns:
        Le chemin du dossier de l'agent.

    Raises:
        OpenGAPError: Si l'agent produirait un manifeste invalide. Le nom est
            validé **avant** de servir à construire un chemin : un nom forgé ne
            doit pas pouvoir écrire hors de la destination.
    """
    manifeste = agent.to_manifest()
    fautes = valider_manifeste(manifeste)
    if fautes:
        raise OpenGAPError(f"Agent « {agent.name} » non conforme : " + " ".join(fautes))
    if not agent.soul.strip():
        raise OpenGAPError(f"Agent « {agent.name} » : {FICHIER_AME} serait vide.")

    dossier = Path(destination) / agent.name
    dossier.mkdir(parents=True, exist_ok=True)

    (dossier / FICHIER_MANIFESTE).write_text(
        yaml.safe_dump(manifeste, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (dossier / FICHIER_AME).write_text(agent.soul, encoding="utf-8")
    return dossier


# ----------------------------------------------------------------------
# Passage depuis le registre GalSen IA
# ----------------------------------------------------------------------

def depuis_entree_registre(entree: Mapping[str, Any], version: str) -> OpenGAPAgent:
    """
    Convertit une entrée d'`agents/registry.yaml` en agent OpenGAP.

    Aucune capacité n'est inventée : le manifeste ne porte que ce que le
    registre déclare réellement. Notamment, aucun modèle préféré n'est écrit —
    GalSen IA choisit son modèle à l'exécution selon ce qui est disponible.

    Args:
        entree: Une entrée de la liste `agents:` du registre.
        version: Version à inscrire, celle de la plateforme.

    Returns:
        L'agent correspondant.

    Raises:
        OpenGAPError: Si l'entrée n'a pas d'identifiant exploitable.
    """
    identifiant = entree.get("id")
    if not isinstance(identifiant, str) or not identifiant:
        raise OpenGAPError("Entrée de registre sans `id`.")

    nom = nom_opengap(identifiant)
    role = entree.get("role") or identifiant
    description = entree.get("description") or role

    metadata: Dict[str, Any] = {"galsen_role": role}
    if nom != identifiant:
        # Le registre reste la source ; l'export en est dérivé. Sans cette
        # trace, un manifeste exporté ne permettrait pas de revenir à l'agent
        # qu'il décrit — `project-manager` et `project_manager` ne se croisent
        # nulle part ailleurs.
        metadata["galsen_id"] = identifiant
    if entree.get("module"):
        metadata["galsen_module"] = entree["module"]
    if entree.get("priority") is not None:
        metadata["galsen_priority"] = entree["priority"]
    metadata["galsen_enabled"] = bool(entree.get("enabled", True))

    return OpenGAPAgent(
        name=nom,
        version=version,
        description=description,
        soul=rediger_ame(identifiant, role, description),
        author="GalSen IA",
        tags=["galsen-ia", _etiquette(role)],
        metadata=metadata,
    )


def nom_opengap(identifiant: str) -> str:
    """
    Traduit un identifiant d'agent GalSen en nom conforme au format.

    La spécification impose le kebab-case ; le registre de la plateforme admet
    aussi le snake_case, et sept agents s'en servent. Convertir à l'export est
    la seule option qui ne demande pas de renommer les agents : le registre est
    la source, l'export en est dérivé, et l'identifiant d'origine est conservé
    dans `metadata.galsen_id` dès qu'il diffère.

    Args:
        identifiant: L'identifiant tel qu'il figure au registre.

    Returns:
        Le nom conforme.

    Raises:
        OpenGAPError: Si rien de conforme ne peut en être tiré — un identifiant
            qui ne donne pas de nom valide doit être signalé, pas remplacé par
            une invention.
    """
    candidat = identifiant.strip().lower().replace("_", "-")
    candidat = re.sub(r"[^a-z0-9-]+", "-", candidat).strip("-")
    if not MOTIF_NOM.match(candidat):
        raise OpenGAPError(
            f"« {identifiant} » ne donne aucun nom conforme au format "
            f"({MOTIF_NOM.pattern}). Renommez l'agent au registre."
        )
    return candidat


def _etiquette(role: str) -> str:
    """Transforme un rôle en étiquette kebab-case."""
    return re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-") or "agent"


def rediger_ame(identifiant: str, role: str, description: str) -> str:
    """
    Rédige le `SOUL.md` d'un agent GalSen IA.

    Le texte est en anglais : `SOUL.md` est lu par d'autres cadriciels, c'est de
    la documentation technique (`.claude/rules/documentation.md`). Il ne décrit
    que des propriétés vraies de la plateforme — les règles que ces agents
    suivent réellement — et n'attribue aucune capacité que l'agent n'a pas.

    Args:
        identifiant: Identifiant de l'agent.
        role: Rôle déclaré au registre.
        description: Description déclarée au registre.

    Returns:
        Le contenu du fichier `SOUL.md`.
    """
    return f"""# {role}

## Core Identity

`{identifiant}` is an agent of the GalSen IA platform, an AI platform built for
Senegal first, then Africa, then further. Its declared responsibility:
{description}

It holds one responsibility and does not widen it. Work outside that
responsibility is handed to the agent that owns it.

## Communication Style

Answers are written in French, the platform's user-facing language, whatever
language the request came in. They are short by default — an answer, not a
report — and they lead with the result rather than with a description of the
work.

## Values & Principles

- Never present unverified work as finished. Something that was not run is
  reported as not run.
- Never fabricate a plausible answer. An unfinished capability reports its
  status; it does not return something that merely looks right.
- A failure is reported with its real output, never softened.
- Read existing code before changing it, and reuse the existing architecture
  rather than inventing a parallel one.
- Never expose secrets, credentials or personal data.

## Domain Expertise

The African context comes first: constrained bandwidth, intermittent power,
mobile-first usage, French and Wolof, and the cost of every external API call.
The platform is designed to run against local models when they are available.

## Collaboration Style

Work is orchestrated by the `router` agent, which routes a request through a
declared pipeline. This agent receives a task with its context, does its part,
and returns a result the next agent can use. It does not call the user, and it
does not reorder the pipeline.
"""


def exporter_registre(
    chemin_registre: Any,
    destination: Any,
    version: str,
) -> List[Path]:
    """
    Exporte tous les agents du registre au format OpenGAP.

    Args:
        chemin_registre: Chemin de `agents/registry.yaml`.
        destination: Dossier parent des dossiers d'agents.
        version: Version à inscrire dans chaque manifeste.

    Returns:
        Les dossiers écrits, dans l'ordre du registre.

    Raises:
        OpenGAPError: Si le registre est illisible ou ne déclare aucun agent.
    """
    chemin = Path(chemin_registre)
    try:
        registre = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as erreur:
        raise OpenGAPError(f"{chemin} : registre illisible — {erreur}") from erreur

    entrees: Sequence[Any] = (registre or {}).get("agents") or []
    if not entrees:
        raise OpenGAPError(f"{chemin} : aucun agent déclaré.")

    return [
        ecrire_agent(depuis_entree_registre(entree, version), destination)
        for entree in entrees
    ]
