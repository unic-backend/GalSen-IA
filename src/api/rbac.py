"""
RBAC — Role-Based Access Control for GalSen IA.

Defines roles, permissions and the authorization logic used by the API layer.
Every protected endpoint declares the minimum permission required.

Roles are associated with API keys via the GALSEN_API_KEYS environment variable
using the format: "key1:role1,key2:role2".

A role without an explicit mapping defaults to "user".

Les clés ne sont jamais conservées en clair : seul leur condensé SHA-256 est
gardé en mémoire, et la comparaison passe par `hmac.compare_digest`. Une clé
présentée est donc condensée avant d'être cherchée, et rien de réversible ne
subsiste après le démarrage — ni dans un attribut, ni dans un journal, ni dans
le contexte porté par la requête (VOLET 02 chapitre 08, *Secure secret
management*).
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Literal, Optional, Set

logger = logging.getLogger(__name__)

# Sujet attribué à une clé déclarée sans nom. C'est une valeur réelle et non
# `None` : filtrer dessus a un sens, cela regroupe exactement les clés que
# personne n'a attribuées (ADR-010).
ANONYMOUS_SUBJECT = "anonymous"


class Role(str, enum.Enum):
    """Rôles utilisateur dans la plateforme GalSen IA."""

    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"
    READONLY = "readonly"

    # Rôles éducatifs (Darra J, VOLET 13). Ils décrivent une position dans un
    # système scolaire, pas un niveau de privilège : une autorité éducative
    # publie un curriculum et ne lit aucune copie d'élève, un chercheur lit des
    # agrégats et jamais un enfant.
    STUDENT = "student"
    PARENT = "parent"
    TEACHER = "teacher"
    SCHOOL_ADMIN = "school_admin"
    EDUCATION_AUTHORITY = "education_authority"
    RESEARCHER = "researcher"


class Permission(str, enum.Enum):
    """Permissions granulaires pour chaque ressource de la plateforme."""

    # Santé et métadonnées
    HEALTH_VIEW = "health:view"

    # Mémoire
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_DELETE = "memory:delete"

    # Modèles IA
    MODEL_GENERATE = "model:generate"
    MODEL_MANAGE = "model:manage"

    # Outils
    TOOL_EXECUTE = "tool:execute"
    TOOL_MANAGE = "tool:manage"

    # Connaissances
    KNOWLEDGE_SEARCH = "knowledge:search"
    KNOWLEDGE_WRITE = "knowledge:write"

    # Approbation humaine
    APPROVAL_VIEW = "approval:view"
    APPROVAL_DECIDE = "approval:decide"

    # Connecteurs externes (ADR-007)
    # La lecture décrit les intégrations et interroge leur état ; la
    # vérification déclenche un appel sortant, elle est donc distinguée.
    CONNECTOR_VIEW = "connector:view"
    CONNECTOR_CHECK = "connector:check"

    # Administration
    ADMIN_MANAGE = "admin:manage"
    ADMIN_AUDIT = "admin:audit"

    # Curriculum officiel (Darra J, VOLET 13)
    CURRICULUM_READ = "curriculum:read"
    CURRICULUM_PROPOSE = "curriculum:propose"
    CURRICULUM_VALIDATE = "curriculum:validate"
    CURRICULUM_PUBLISH = "curriculum:publish"

    # Évaluation
    ASSESSMENT_CREATE = "assessment:create"
    ASSESSMENT_SCORE = "assessment:score"

    # Données d'apprenant. Le nom porte la restriction : cette permission
    # n'ouvre **que** les apprenants rattachés au demandeur, et le rattachement
    # est vérifié séparément par `src/darra_j/access.py`. Aucune permission
    # n'ouvre un apprenant non rattaché — il n'en existe pas.
    LEARNER_DATA_READ_LINKED = "learner:read_linked"
    LEARNER_DECISION_RECORD = "learner:decide"

    # Recherche : des agrégats, jamais un enfant.
    RESEARCH_AGGREGATE_READ = "research:aggregate"


#: Les permissions qu'aucun rôle **de la plateforme** ne reçoit, même
#: administrateur.
#:
#: `Role.ADMIN` est calculé comme « toutes les permissions », ce qui est correct
#: tant que toute permission décrit un pouvoir de la plateforme. Deux familles
#: n'en sont pas : publier un curriculum appartient à une autorité éducative —
#: « GalSen IA n'est pas l'autorité qui définit le curriculum » — et lire le
#: travail d'un enfant appartient à ceux qui lui sont rattachés. Les laisser
#: entrer par la compréhension ferait de l'ajout d'un membre d'énumération un
#: élargissement silencieux du rôle administrateur.
PERMISSIONS_HORS_PLATEFORME: FrozenSet[Permission] = frozenset({
    Permission.CURRICULUM_VALIDATE,
    Permission.CURRICULUM_PUBLISH,
    Permission.LEARNER_DATA_READ_LINKED,
    Permission.LEARNER_DECISION_RECORD,
})

#: Les rôles éducatifs, distingués des rôles de plateforme.
EDUCATION_ROLES: FrozenSet[Role] = frozenset({
    Role.STUDENT, Role.PARENT, Role.TEACHER, Role.SCHOOL_ADMIN,
    Role.EDUCATION_AUTHORITY, Role.RESEARCHER,
})


# Correspondance rôle → permissions
_ROLE_PERMISSIONS: Dict[Role, FrozenSet[Permission]] = {
    # Toutes les permissions de la plateforme, et **seulement** celles-là : la
    # soustraction est explicite pour qu'un membre ajouté à l'énumération
    # n'élargisse pas le rôle administrateur sans que personne l'ait décidé.
    Role.ADMIN: frozenset(set(Permission) - PERMISSIONS_HORS_PLATEFORME),
    Role.OPERATOR: frozenset({
        Permission.HEALTH_VIEW,
        Permission.MEMORY_READ,
        Permission.KNOWLEDGE_SEARCH,
        Permission.TOOL_EXECUTE,
        Permission.APPROVAL_VIEW,
        Permission.APPROVAL_DECIDE,
        Permission.ADMIN_AUDIT,
        Permission.CONNECTOR_VIEW,
        Permission.CONNECTOR_CHECK,
    }),
    Role.USER: frozenset({
        Permission.HEALTH_VIEW,
        Permission.MEMORY_READ,
        Permission.MEMORY_WRITE,
        Permission.MODEL_GENERATE,
        Permission.KNOWLEDGE_SEARCH,
        Permission.TOOL_EXECUTE,
        Permission.APPROVAL_VIEW,
        Permission.CONNECTOR_VIEW,
    }),
    Role.READONLY: frozenset({
        Permission.HEALTH_VIEW,
        Permission.KNOWLEDGE_SEARCH,
        Permission.APPROVAL_VIEW,
        Permission.CONNECTOR_VIEW,
    }),

    # --- Rôles éducatifs (Darra J, VOLET 13) ---------------------------------
    # Chacun tient une position, pas un niveau de privilège. Un élève et une
    # autorité éducative ne sont pas comparables : leurs ensembles ne
    # s'emboîtent pas, et c'est voulu.
    Role.STUDENT: frozenset({
        Permission.CURRICULUM_READ,
        Permission.LEARNER_DATA_READ_LINKED,
    }),
    Role.PARENT: frozenset({
        Permission.CURRICULUM_READ,
        Permission.LEARNER_DATA_READ_LINKED,
    }),
    Role.TEACHER: frozenset({
        Permission.CURRICULUM_READ,
        Permission.LEARNER_DATA_READ_LINKED,
        Permission.ASSESSMENT_CREATE,
        Permission.ASSESSMENT_SCORE,
        Permission.LEARNER_DECISION_RECORD,
    }),
    Role.SCHOOL_ADMIN: frozenset({
        Permission.CURRICULUM_READ,
        Permission.LEARNER_DATA_READ_LINKED,
        Permission.LEARNER_DECISION_RECORD,
    }),
    # Une autorité éducative définit le curriculum et **ne lit aucune copie
    # d'élève** : publier un programme national n'a jamais demandé de savoir ce
    # qu'un enfant a répondu.
    Role.EDUCATION_AUTHORITY: frozenset({
        Permission.CURRICULUM_READ,
        Permission.CURRICULUM_PROPOSE,
        Permission.CURRICULUM_VALIDATE,
        Permission.CURRICULUM_PUBLISH,
    }),
    # Un chercheur lit des agrégats. Aucun rattachement ne peut lui ouvrir un
    # enfant, parce qu'il n'a pas la permission qui le demanderait.
    Role.RESEARCHER: frozenset({
        Permission.CURRICULUM_READ,
        Permission.RESEARCH_AGGREGATE_READ,
    }),
}


def get_permissions_for_role(role: Role) -> FrozenSet[Permission]:
    """
    Retourne l'ensemble des permissions associées à un rôle.

    Args:
        role: Le rôle dont on veut les permissions.

    Returns:
        Ensemble immuable de permissions.
    """
    return _ROLE_PERMISSIONS.get(role, frozenset())


def hash_api_key(api_key: str) -> str:
    """
    Retourne le condensé SHA-256 d'une clé API, en hexadécimal.

    Args:
        api_key: La clé présentée par un client.

    Returns:
        Le condensé, seule forme sous laquelle la plateforme conserve une clé.
    """
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def key_fingerprint(digest: str) -> str:
    """
    Retourne une empreinte courte, non réversible, utilisable en journal.

    Douze caractères hexadécimaux suffisent à distinguer les clés d'une
    installation sans permettre de remonter à la clé : c'est ce qui permet de
    tracer un appelant dans l'audit sans écrire de secret.
    """
    return digest[:12]


def parse_api_key_mappings() -> Dict[str, "KeyIdentity"]:
    """
    Parse `GALSEN_API_KEYS` en un mapping clé API → identité.

    Format attendu, le sujet étant facultatif (ADR-010) :
        "cle-admin:admin:awa, cle-terrain:user:moussa, cle-scrutin:readonly"
         └ secret ┘ └ rôle ┘ └ sujet ┘

    Une clé sans rôle explicite reçoit le rôle USER ; une clé sans sujet est
    attribuée au sujet anonyme, de sorte qu'un déploiement existant continue de
    fonctionner sans modification.

    Returns:
        Dictionnaire {condensé de la clé: identité}. La clé en clair n'est
        jamais conservée : elle disparaît avec la variable locale.
    """
    raw = os.environ.get("GALSEN_API_KEYS", "").strip()
    if not raw:
        return {}

    mappings: Dict[str, "KeyIdentity"] = {}
    parts = [p.strip() for p in raw.split(",") if p.strip()]

    for part in parts:
        # `split(":", 2)` et non `split(":", 1)` : le troisième champ est le
        # sujet. Un secret contenant lui-même un « : » resterait mal découpé,
        # mais c'était déjà vrai avant ce champ.
        morceaux = [m.strip() for m in part.split(":", 2)]
        key = morceaux[0]
        role_name = (morceaux[1].lower() if len(morceaux) > 1 and morceaux[1] else "user")
        subject = morceaux[2] if len(morceaux) > 2 and morceaux[2] else ANONYMOUS_SUBJECT

        if not key:
            continue

        try:
            role = Role(role_name)
        except ValueError:
            # L'empreinte, jamais le début de la clé : huit caractères d'un
            # secret journalisés restent huit caractères de secret divulgués.
            logger.warning(
                "Rôle '%s' inconnu pour la clé d'empreinte %s. "
                "Rôles valides : %s. Utilisation du rôle 'user' par défaut.",
                role_name, key_fingerprint(hash_api_key(key)), [r.value for r in Role],
            )
            role = Role.USER

        mappings[hash_api_key(key)] = KeyIdentity(role=role, subject=subject)

    return mappings


@dataclass(frozen=True)
class KeyIdentity:
    """
    Ce qu'une clé déclare : un rôle, et à qui elle appartient (ADR-010).

    Le sujet est un identifiant stable, pas un secret : il apparaît dans les
    traces d'audit et dans les réponses d'administration, jamais la clé.

    Attributes:
        role: Le rôle accordé par cette clé.
        subject: L'identifiant de la personne ou du service porteur, ou
            `ANONYMOUS_SUBJECT` quand la déclaration n'en nomme aucun.
    """

    role: "Role"
    subject: str = ANONYMOUS_SUBJECT


@dataclass
class RBACContext:
    """
    Contexte d'autorisation pour une requête.

    Porté par chaque requête authentifiée, il permet aux dépendances
    FastAPI de vérifier rapidement si l'utilisateur a le droit d'effectuer
    une action.

    Il porte l'**empreinte** de la clé, jamais la clé : un contexte peut se
    retrouver dans un journal, une trace d'audit ou un message d'erreur, et rien
    de ce qu'il contient ne doit permettre de rejouer un appel.
    """

    key_fingerprint: str
    role: Role
    # À qui appartient la clé (ADR-010). Une trace d'audit disant « awa a fait X »
    # est exploitable ; « la clé 745df677f426 a fait X » ne l'est pas.
    subject: str = ANONYMOUS_SUBJECT
    # Par quel moyen l'appelant s'est authentifié. `api_key` est le seul chemin
    # actif aujourd'hui ; `jwt` et `oauth` n'existent que sur cette branche, et
    # ADR-010 refuse pour l'instant le magasin d'identifiants qu'ils supposent.
    # Le champ est déclaré ici parce qu'une trace d'audit qui ne dit pas
    # **comment** quelqu'un est entré ne permet pas de révoquer le bon chemin.
    auth_method: Literal["api_key", "jwt", "oauth"] = "api_key"
    # Identifiant du compte, quand il y en a un. Distinct de `subject` : le
    # sujet est ce qu'une clé **déclare**, l'identifiant est ce qu'un annuaire
    # **vérifie**. Les confondre ferait passer une déclaration pour une preuve.
    user_id: Optional[str] = None
    permissions: FrozenSet[Permission] = field(init=False)

    def __post_init__(self):
        self.permissions = get_permissions_for_role(self.role)

    def has_permission(self, permission: Permission) -> bool:
        """
        Vérifie si ce contexte dispose d'une permission donnée.

        Args:
            permission: La permission à vérifier.

        Returns:
            True si l'utilisateur a cette permission.
        """
        return permission in self.permissions

    def has_any_permission(self, *permissions: Permission) -> bool:
        """
        Vérifie si ce contexte dispose d'au moins une des permissions données.

        Args:
            permissions: Les permissions à vérifier.

        Returns:
            True si l'utilisateur a au moins une de ces permissions.
        """
        return any(p in self.permissions for p in permissions)

    def require_permission(self, permission: Permission) -> None:
        """
        Vérifie la permission et lève une exception si elle est absente.

        Args:
            permission: La permission requise.

        Raises:
            PermissionError: Si l'utilisateur n'a pas cette permission.
        """
        if not self.has_permission(permission):
            raise PermissionError(
                f"Permission '{permission.value}' requise. "
                f"Rôle actuel : '{self.role.value}'."
            )


class RBACManager:
    """
    Gestionnaire RBAC — point d'entrée unique pour l'autorisation.

    Maintient le mapping clé API → rôle à partir de la variable
    d'environnement et fournit la méthode d'authentification avec rôle.

    Il tient aussi une **liste de révocation** : une clé compromise doit cesser
    d'ouvrir la porte immédiatement, sans attendre un redémarrage. Cette liste
    ne survit pas au processus, et c'est assumé — la source durable des clés
    reste l'environnement du déploiement (ADR-004). Révoquer arrête l'hémorragie ;
    retirer la clé de l'environnement la referme pour de bon.
    """

    def __init__(self):
        """Initialise le gestionnaire en parsant la variable d'environnement."""
        self._key_role_map: Dict[str, KeyIdentity] = {}
        self._revoked_digests: Set[str] = set()
        self.reload()

    def reload(self) -> Dict[str, Any]:
        """
        Recharge le mapping clé → rôle depuis la variable d'environnement.

        Les révocations qui ne correspondent plus à aucune clé connue sont
        oubliées : la clé a disparu de l'environnement, la révoquer n'a plus
        d'objet et garder l'entrée ferait grossir la liste sans fin.

        Returns:
            Un résumé du changement : nombre de clés avant et après, empreintes
            ajoutées et retirées. Jamais de clé en clair.
        """
        avant = set(self._key_role_map)
        self._key_role_map = parse_api_key_mappings()
        apres = set(self._key_role_map)

        self._revoked_digests &= apres

        roles_present = {identite.role for identite in self._key_role_map.values()}
        logger.info(
            "RBAC chargé : %s clé(s) mappée(s) vers %s",
            len(self._key_role_map),
            {r.value for r in roles_present} if roles_present else "{}",
        )
        return {
            "before": len(avant),
            "after": len(apres),
            "added": sorted(key_fingerprint(d) for d in apres - avant),
            "removed": sorted(key_fingerprint(d) for d in avant - apres),
        }

    def revoke(self, fingerprint: str) -> bool:
        """
        Révoque une clé à partir de son empreinte, avec effet immédiat.

        L'empreinte suffit : l'opérateur qui révoque n'a pas à détenir la clé,
        et n'a donc aucune raison de la manipuler.

        Args:
            fingerprint: Les 12 caractères retournés par `list_keys()`.

        Returns:
            True si une clé correspondait, False si l'empreinte est inconnue.
        """
        for digest in self._key_role_map:
            if key_fingerprint(digest) == fingerprint:
                self._revoked_digests.add(digest)
                logger.warning("Clé d'empreinte %s révoquée.", fingerprint)
                return True
        return False

    def restore(self, fingerprint: str) -> bool:
        """Lève une révocation ; retourne False si la clé n'était pas révoquée."""
        for digest in list(self._revoked_digests):
            if key_fingerprint(digest) == fingerprint:
                self._revoked_digests.discard(digest)
                logger.info("Révocation levée pour l'empreinte %s.", fingerprint)
                return True
        return False

    def list_keys(self) -> List[Dict[str, Any]]:
        """
        Retourne l'inventaire des clés : empreinte, rôle, état de révocation.

        Aucune clé n'y figure : un opérateur doit pouvoir voir *combien* de clés
        existent et *avec quels droits*, sans obtenir de quoi s'en servir.
        """
        return sorted(
            (
                {
                    "fingerprint": key_fingerprint(digest),
                    "role": identite.role.value,
                    "subject": identite.subject,
                    "revoked": digest in self._revoked_digests,
                }
                for digest, identite in self._key_role_map.items()
            ),
            key=lambda entree: entree["fingerprint"],
        )

    def active_key_digests(self) -> Set[str]:
        """Retourne les condensés des clés valides **et non révoquées**."""
        return set(self._key_role_map) - self._revoked_digests

    def authenticate(self, api_key: Optional[str]) -> RBACContext:
        """
        Authentifie une clé API et retourne son contexte RBAC.

        Args:
            api_key: La clé API à authentifier. None si aucune clé fournie.

        Returns:
            Contexte RBAC avec le rôle et les permissions.

        Raises:
            PermissionError: Si la clé est absente, inconnue ou révoquée. Les
                trois cas renvoient le même message : dire à un appelant que sa
                clé « a été révoquée » lui confirmerait qu'elle a existé.
        """
        if not api_key:
            raise PermissionError("Clé API manquante.")

        digest = hash_api_key(api_key)

        # La recherche dans le dictionnaire suffirait, mais elle n'est pas à
        # temps constant : la comparaison explicite ferme cette mesure de temps.
        for connu, identite in self._key_role_map.items():
            if not hmac.compare_digest(connu, digest):
                continue

            if connu in self._revoked_digests:
                # Le message ne distingue pas « révoquée » de « inconnue » :
                # confirmer qu'une clé a existé renseignerait un attaquant.
                logger.warning(
                    "Tentative avec une clé révoquée (empreinte %s).",
                    key_fingerprint(digest),
                )
                raise PermissionError("Clé API invalide.")

            return RBACContext(
                key_fingerprint=key_fingerprint(digest),
                role=identite.role,
                subject=identite.subject,
                auth_method="api_key",
            )

        raise PermissionError("Clé API invalide.")

    def get_valid_key_digests(self) -> Set[str]:
        """
        Retourne l'ensemble des **condensés** des clés API valides.

        Utile pour synchroniser avec le limiteur de taux, qui doit reconnaître
        un client authentifié sans jamais détenir sa clé.

        Returns:
            Ensemble des condensés SHA-256.
        """
        return set(self._key_role_map.keys())

    @property
    def has_keys(self) -> bool:
        """Indique si au moins une clé API est configurée."""
        return len(self._key_role_map) > 0