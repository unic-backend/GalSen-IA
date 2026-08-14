"""
What the three Google connectors share, written once.

Gmail, Drive and Calendar differ in what they read and how their answers are
shaped. Everything else — the data contract, the privileges asked for, the
description, the configuration check, the way a request is built and gated — is
identical. Three copies of it would be three places to fix a mistake, and the
second copy is where two versions start to disagree.

The shape below is deliberately narrow, and each connector inherits it whole:

- **`user_private`, per subject, retaining nothing of the content.** That is
  true of a mailbox, a drive and a calendar alike.
- **Read, and only read.** No write privilege is requested by any of them.
  Sending a mail, uploading a file and creating an event are three different
  objects with three different consents, and none of them is this one.
- **No request without a usable authorization**, and none built at all when the
  access was never granted, expired, or was withdrawn.
- **The token travels in a header**, never in the URL, where it would be
  written into a server log by machines nobody controls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...tool.capabilities import DataScope, Effect
from ..contract import DataContract
from ..lifecycle import SubjectBinding
from ..oauth.config import Provider
from ..oauth.session import OAuthSession
from ..oauth.tokens import TokenStore
from ..safety import Privilege, PrivilegeRequest
from ..types import ConnectorCheck, ConnectorDescription, ConnectorKind, ConnectorStatus
from .apis import GoogleApi, get_api


class GoogleReadConnector(OAuthSession):
    """
    Base des connecteurs Google en lecture, liés à une personne.

    Une sous-classe fournit quatre choses : son identifiant, sa catégorie, le
    nom de son API, et un résumé. Tout le reste vient d'ici.
    """

    #: Identifiant du connecteur au registre. À redéfinir.
    CONNECTOR_ID = ""

    #: Nom de l'API dans `config/connectors/google.yaml`. À redéfinir.
    API_NAME = ""

    #: Catégorie de système externe. À redéfinir.
    KIND = ConnectorKind.OTHER

    #: Ce que la sous-classe lit, en une phrase, pour la description.
    SUMMARY = ""

    #: Ce qu'elle sait faire, pour la description.
    OPERATIONS: List[str] = []

    def __init__(
        self,
        provider: Provider,
        tokens: Optional[TokenStore] = None,
        api: Optional[GoogleApi] = None,
    ) -> None:
        """
        Args:
            provider: Le fournisseur Google déclaré.
            tokens: Le magasin de jetons. **À partager** entre les connecteurs
                Google d'une même installation : sans cela, une personne devrait
                consentir une fois par connecteur au même compte.
            api: La surface d'API, lue en configuration par défaut.
        """
        if not self.CONNECTOR_ID or not self.API_NAME:
            raise NotImplementedError(
                f"{type(self).__name__} doit déclarer CONNECTOR_ID et API_NAME."
            )
        self.api = api or get_api(self.API_NAME)
        super().__init__(provider, [self.api.scope_read], tokens=tokens)

    # ------------------------------------------------------------------
    # Le contrat `Connector`
    # ------------------------------------------------------------------

    @property
    def connector_id(self) -> str:
        """Identifiant stable du connecteur."""
        return self.CONNECTOR_ID

    @property
    def kind(self) -> ConnectorKind:
        """Catégorie de système externe."""
        return self.KIND

    @property
    def data_contract(self) -> DataContract:
        """
        Ce qu'il touche, et pour qui.

        Identique pour les trois : une boîte, un disque et un agenda
        appartiennent tous à quelqu'un, et rien de leur contenu n'est conservé.
        """
        return DataContract(
            data_scope=DataScope.USER_PRIVATE,
            per_subject=True,
            effects=frozenset({Effect.READ, Effect.EXTERNAL}),
            retention=(
                "Rien du contenu. Seuls les jetons sont conservés, chiffrés, "
                "et effacés au retrait."
            ),
            rationale=f"{self.SUMMARY} Pour son titulaire seul.",
        )

    @property
    def requested_privileges(self) -> List[PrivilegeRequest]:
        """
        La lecture, et rien d'autre.

        Aucun des trois ne demande d'écriture : envoyer un courriel, téléverser
        un fichier et créer un rendez-vous sont trois actes, avec trois
        consentements, et aucun n'est celui-ci.
        """
        return [PrivilegeRequest(
            Privilege.READ,
            rationale=f"{self.SUMMARY} À la demande du titulaire.",
        )]

    def describe(self) -> ConnectorDescription:
        """Décrit le connecteur, sans aucun appel réseau ni aucun secret."""
        return ConnectorDescription(
            connector_id=self.CONNECTOR_ID,
            kind=self.KIND,
            summary=self.SUMMARY,
            environment_variables=[
                self.provider.client_id_variable,
                self.provider.client_secret_variable,
                self.provider.redirect_uri_variable,
            ],
            operations=list(self.OPERATIONS),
            owner="équipe plateforme",
        )

    def is_configured(self) -> bool:
        """Indique si les identifiants OAuth sont présents. Aucun appel réseau."""
        return self.provider.is_configured()

    def check(self) -> ConnectorCheck:
        """
        Vérifie l'état du connecteur.

        Ne contacte rien : sans identifiants il n'y a rien à contacter, et avec
        eux, une vérification demanderait le jeton d'une personne — ce qui n'est
        pas une vérification de service mais une lecture de ses données.
        """
        if not self.is_configured():
            return ConnectorCheck(
                connector_id=self.CONNECTOR_ID,
                kind=self.KIND,
                status=ConnectorStatus.NOT_CONFIGURED,
                detail=(
                    "Variables absentes : "
                    + ", ".join(self.provider.missing_variables())
                ),
            )
        return ConnectorCheck(
            connector_id=self.CONNECTOR_ID,
            kind=self.KIND,
            status=ConnectorStatus.READY,
            detail=(
                "Identifiants présents. L'accès reste par personne : voir "
                "l'état d'autorisation de chacune."
            ),
        )

    # ------------------------------------------------------------------
    # Les requêtes, construites et non envoyées
    # ------------------------------------------------------------------

    def _requete(
        self,
        binding: SubjectBinding,
        chemin: str,
        parametres: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Dict[str, Any]:
        """
        Construit une requête authentifiée pour le porteur du lien.

        Passe par `binding.call`, donc un accès non utilisable — jamais accordé,
        périmé, retiré — refuse **avant** que la requête n'existe.

        Args:
            binding: Le lien à la personne.
            chemin: Le chemin sous la racine de l'API.
            parametres: Les paramètres de requête.
            method: La méthode HTTP. `GET` pour tout ce que fait la lecture.

        Returns:
            La requête à envoyer.
        """
        def _construire() -> Dict[str, Any]:
            jeton = self.tokens.get(self.provider.id, binding.subject)
            return {
                "method": method,
                "url": self.api.url(chemin),
                # En en-tête, jamais dans l'URL : une URL est écrite dans les
                # journaux de tous les intermédiaires du chemin.
                "headers": {"Authorization": f"Bearer {jeton.access_token}"},
                "params": dict(parametres or {}),
            }

        return binding.call(_construire)

    @staticmethod
    def _plafonner(demande: Any, defaut: int, maximum: int) -> int:
        """
        Ramène une taille de page dans ses bornes.

        Ramener plutôt que refuser : l'appelant obtient moins, jamais rien.
        """
        try:
            valeur = int(demande)
        except (TypeError, ValueError):
            return defaut
        return max(1, min(valeur, maximum))

    # ------------------------------------------------------------------
    # Rapport
    # ------------------------------------------------------------------

    def connector_report(self, subject: Optional[str] = None) -> Dict[str, Any]:
        """
        Ce que ce connecteur est, et ce qu'il refuse d'être.

        Args:
            subject: La personne, quand on veut son état.

        Returns:
            L'API visée, la session, et les refus communs aux trois.
        """
        rapport = self.session_report(subject)
        rapport["api"] = self.api.as_dict()
        rapport["refuses"] = [
            "Écrire quoi que ce soit — ces connecteurs lisent.",
            "Rendre un contenu autrement qu'enveloppé en donnée.",
            "Faire un appel réseau : les requêtes sont construites, pas envoyées.",
        ] + list(self.extra_refusals())
        return rapport

    def extra_refusals(self) -> List[str]:
        """Les refus propres à une sous-classe. Vide par défaut."""
        return []
