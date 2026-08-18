"""
Écrire du code sous portillon, et vérifier ce qu'on a écrit (VOLET 31, ch. 02-03).

C'est la capacité la plus dangereuse de la plateforme : un agent qui modifie des
fichiers. Elle est donc construite dans l'autre sens que d'habitude — **le refus
est le défaut**, et chaque autorisation doit être obtenue, jamais supposée.

Quatre garanties, et aucune n'est configurable :

1. **Rien ne s'écrit sans approbation humaine accordée** (ADR-006). Le portillon
   existait déjà, mais `submit_approval()` est *consultatif* : il dépose une
   demande et rend un identifiant. Un appelant pouvait soumettre puis écrire
   sans attendre. Ici, une demande non approuvée **bloque** l'écriture. Le
   VOLET 01 avait mesuré le risque : `approval_required` vaut `False` par
   défaut, donc « le premier agent qui écrira le fera sans portillon ». Celui-ci
   ne le peut pas.
2. **Le moteur d'approbation absent interdit d'écrire.** Ailleurs dans la
   plateforme, un moteur manquant dégrade proprement ; ici, il **ferme**. Un
   portillon qu'on peut faire disparaître en éteignant un service n'est pas un
   portillon.
3. **Rien ne sort du dépôt**, et certains fichiers restent hors de portée quoi
   qu'on approuve : `.env`, clés, bases de données, `.git`.
4. **Une modification qui casse ses tests est annulée.** L'ancien contenu est
   conservé et remis en place ; l'agent reçoit la sortie réelle de l'échec.

La boucle « éditer → tester → corriger » est bornée : sans borne, un agent qui ne
sait pas réparer réessaie indéfiniment en consommant la requête.
"""

import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Fichiers auxquels aucune approbation ne donne accès. La liste est courte et
# volontairement absolue : ce sont les fichiers dont la modification ne peut pas
# être une intention légitime d'un agent de développement.
CHEMINS_INTERDITS = (
    ".env", ".git", ".ssh", "id_rsa", ".pem", ".key",
    ".sqlite", ".db", "secrets", "credentials",
)

# Tentatives maximales de la boucle éditer → tester → corriger.
MAX_TENTATIVES = 3

# Suites lancées au maximum après une modification (VOLET 34, ch. 10). Un
# fichier central est importé par des dizaines de tests ; les lancer tous
# reviendrait à passer la suite complète à chaque édition.
LIMITE_SUITES = 3

# Au-delà, ce n'est plus une correction ciblée : c'est une réécriture, et elle
# mérite une relecture humaine complète plutôt qu'une approbation de passage.
MAX_OCTETS = 200_000


@dataclass
class EditOutcome:
    """Ce qu'une tentative d'écriture a produit."""

    path: str
    status: str
    detail: str = ""
    approval_request_id: Optional[str] = None
    tests_run: Optional[str] = None
    tests_passed: Optional[bool] = None
    reverted: bool = False
    output: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat pour un agent ou un rapport."""
        donnees = {"path": self.path, "status": self.status}
        for champ in ("detail", "approval_request_id", "tests_run", "output"):
            valeur = getattr(self, champ)
            if valeur:
                donnees[champ] = valeur
        if self.tests_passed is not None:
            donnees["tests_passed"] = self.tests_passed
        if self.reverted:
            donnees["reverted"] = True
        return donnees


@dataclass
class LoopReport:
    """Le déroulé d'une boucle éditer → tester → corriger."""

    attempts: List[EditOutcome] = field(default_factory=list)
    succeeded: bool = False
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le déroulé."""
        return {
            "succeeded": self.succeeded,
            "attempts": [tentative.to_dict() for tentative in self.attempts],
            "attempt_count": len(self.attempts),
            "detail": self.detail,
        }


class ApprovalRequired(PermissionError):
    """Une écriture a été tentée sans approbation accordée."""


class GuardedEditor:
    """
    Écrit un fichier du dépôt, sous approbation, et vérifie le résultat.

    Exemple:
        editeur = GuardedEditor(context)
        demande = editeur.propose("src/x.py", nouveau_contenu, "corrige le calcul")
        # un humain approuve `demande.approval_request_id`
        resultat = editeur.apply(demande.approval_request_id)
    """

    def __init__(self, context, root: Optional[str] = None):
        """
        Args:
            context: `AgentContext` de l'agent qui écrit — il porte le portillon,
                l'audit et l'identité de l'agent.
            root: Racine autorisée ; la racine du dépôt par défaut.
        """
        self._context = context
        self.root = os.path.realpath(root or self._racine_par_defaut())
        # Contenus proposés, en attente d'approbation : identifiant de demande
        # vers ce qu'il faudra écrire si un humain l'accorde.
        self._en_attente: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _racine_par_defaut() -> str:
        """Retourne la racine du dépôt."""
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # ------------------------------------------------------------------
    # Contrôles
    # ------------------------------------------------------------------

    def _verifier_chemin(self, chemin: str) -> str:
        """
        Résout un chemin et refuse tout ce qui sort du cadre.

        Raises:
            PermissionError: Si le chemin sort du dépôt ou vise un fichier
                interdit. Le message nomme la raison : un refus muet ferait
                chercher au mauvais endroit.
        """
        absolu = os.path.realpath(os.path.join(self.root, chemin))
        if not (absolu == self.root or absolu.startswith(self.root + os.sep)):
            raise PermissionError(
                f"« {chemin} » sort du dépôt. Aucune approbation ne donne accès "
                f"à l'extérieur de {self.root}."
            )

        minuscule = absolu.lower()
        for interdit in CHEMINS_INTERDITS:
            if interdit in minuscule:
                raise PermissionError(
                    f"« {chemin} » touche un fichier protégé ({interdit}). Ces "
                    f"fichiers restent hors de portée quelle que soit l'approbation."
                )
        return absolu

    # ------------------------------------------------------------------
    # Proposer, puis appliquer
    # ------------------------------------------------------------------

    def propose(self, chemin: str, contenu: str, raison: str) -> EditOutcome:
        """
        Soumet une modification au portillon, sans rien écrire.

        Args:
            chemin: Fichier visé, relatif à la racine du dépôt.
            contenu: Contenu complet proposé.
            raison: Ce que la modification fait, pour l'humain qui décidera.

        Returns:
            Le résultat : `pending_approval` avec l'identifiant de la demande, ou
            `refused` avec la raison.
        """
        try:
            absolu = self._verifier_chemin(chemin)
        except PermissionError as refus:
            return EditOutcome(path=chemin, status="refused", detail=str(refus))

        if not raison or not raison.strip():
            return EditOutcome(
                path=chemin, status="refused",
                detail="Une raison est exigée : un humain doit pouvoir décider sans lire le diff.",
            )
        if len(contenu.encode("utf-8")) > MAX_OCTETS:
            return EditOutcome(
                path=chemin, status="refused",
                detail=f"Modification trop grande (> {MAX_OCTETS} octets) : "
                       f"une réécriture demande une relecture complète, pas une approbation de passage.",
            )

        if self._context.approval is None:
            # Ailleurs, un moteur absent dégrade proprement. Ici il ferme : un
            # portillon qu'on peut faire disparaître n'est pas un portillon.
            return EditOutcome(
                path=chemin, status="refused",
                detail="Moteur d'approbation indisponible : aucune écriture n'est possible (ADR-006).",
            )

        existant = os.path.isfile(absolu)
        demande = self._context.submit_approval(
            action="code_edit",
            description=f"{raison} — {chemin} ({'modification' if existant else 'création'})",
            metadata={
                "path": chemin,
                "bytes": len(contenu.encode("utf-8")),
                "exists": existant,
                "reason": raison,
            },
        )
        if demande is None:
            return EditOutcome(
                path=chemin, status="refused",
                detail="Le portillon a refusé la soumission : rien n'est écrit.",
            )

        self._en_attente[demande] = {"path": chemin, "absolu": absolu, "content": contenu}
        return EditOutcome(
            path=chemin, status="pending_approval", approval_request_id=demande,
            detail="En attente d'une décision humaine. Rien n'est écrit tant qu'elle n'est pas prise.",
        )

    def apply(self, approval_request_id: str, run_tests: bool = True) -> EditOutcome:
        """
        Applique une modification **approuvée**, puis lance ses tests.

        Args:
            approval_request_id: Identifiant rendu par `propose`.
            run_tests: Lance le test qui couvre le fichier, et annule si l'échec
                vient de la modification.

        Returns:
            Le résultat de l'écriture.

        Raises:
            ApprovalRequired: Si la demande n'est pas approuvée. Lever est
                correct ici : appliquer sans approbation est la faute que ce
                module existe pour rendre impossible.
        """
        en_attente = self._en_attente.get(approval_request_id)
        if en_attente is None:
            raise ApprovalRequired(
                f"Aucune modification en attente sous « {approval_request_id} »."
            )

        portillon = self._context.approval
        if portillon is None:
            raise ApprovalRequired(
                "Moteur d'approbation indisponible : l'écriture est refusée (ADR-006)."
            )

        demande = portillon.get(approval_request_id)
        statut = getattr(demande, "status", None)
        statut = getattr(statut, "value", statut)
        if statut != "approved":
            raise ApprovalRequired(
                f"La demande « {approval_request_id} » est « {statut} » et non "
                f"« approved » : rien n'est écrit."
            )

        chemin, absolu, contenu = en_attente["path"], en_attente["absolu"], en_attente["content"]
        ancien = None
        if os.path.isfile(absolu):
            with open(absolu, "r", encoding="utf-8") as fichier:
                ancien = fichier.read()

        os.makedirs(os.path.dirname(absolu) or self.root, exist_ok=True)
        with open(absolu, "w", encoding="utf-8") as fichier:
            fichier.write(contenu)
        self._en_attente.pop(approval_request_id, None)
        self._context.post("code_edit", {"path": chemin, "approved": approval_request_id})

        resultat = EditOutcome(
            path=chemin, status="applied", approval_request_id=approval_request_id,
        )
        if not run_tests:
            return resultat

        suites = self._tests_de(chemin)
        if not suites:
            resultat.detail = (
                "Aucun test n'atteint ce fichier, ni par import ni par nom : la "
                "modification est appliquée mais **non vérifiée**."
            )
            return resultat

        reussi, sortie = self.run_tests(suites)
        resultat.tests_run = ", ".join(suites)
        resultat.tests_passed = reussi
        resultat.output = sortie[-2000:]

        if not reussi:
            # Annuler plutôt que laisser un dépôt cassé : l'agent reçoit la
            # sortie réelle et peut proposer autre chose.
            self._restaurer(absolu, ancien)
            resultat.status = "reverted"
            resultat.reverted = True
            resultat.detail = "Les tests échouent : la modification a été annulée."
        return resultat

    @staticmethod
    def _restaurer(absolu: str, ancien: Optional[str]) -> None:
        """Remet le fichier dans son état antérieur, ou le supprime s'il était neuf."""
        if ancien is None:
            try:
                os.unlink(absolu)
            except OSError:
                pass
            return
        with open(absolu, "w", encoding="utf-8") as fichier:
            fichier.write(ancien)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def _test_de(self, chemin: str) -> Optional[str]:
        """
        Retourne le test couvrant un fichier, via la carte du dépôt.

        Conservée pour ce qu'elle est : la convention de nom. `_tests_de` lui
        est préférée — elle ne trouvait de test que pour 67 fichiers sur 308.
        """
        from .repo_map import RepoMap

        return RepoMap(self.root).build().tests_for(chemin)

    def _tests_de(self, chemin: str) -> List[str]:
        """
        Retourne les suites à lancer après une modification.

        Trois sources, dans l'ordre du plus précis au plus large :

        1. les tests qui **importent le fichier** (graphe d'imports, ch. 10) ;
        2. ceux qui importent son rayon d'impact, quand aucun ne le touche
           directement ;
        3. la convention de nom, en dernier recours.

        Le nombre de suites est plafonné : un fichier central est importé par
        des dizaines de tests, et les lancer tous reviendrait à passer la suite
        complète à chaque édition. Le plafond est dit dans le résultat plutôt
        que silencieux.
        """
        from .repo_graph import RepoGraph

        graphe = RepoGraph(root=self.root).build()
        prefixe = "tests/"
        directs = [f for f in graphe.imported_by(chemin) if f.startswith(prefixe)]
        suites = directs or graphe.tests_to_run(chemin)
        if not suites:
            nomme = self._test_de(chemin)
            suites = [nomme] if nomme else []
        return suites[:LIMITE_SUITES]

    def run_tests(self, suite, timeout: int = 600) -> tuple:
        """
        Lance une ou plusieurs suites de tests et retourne le verdict.

        Args:
            suite: Fichier de tests, ou liste de fichiers.
            timeout: Délai maximal, en secondes.

        Returns:
            `(réussi, sortie)`. Un délai dépassé compte comme un échec : une
            suite qui ne rend pas la main n'est pas une suite qui passe.
        """
        suites = [suite] if isinstance(suite, str) else list(suite)
        if not suites:
            return False, "Aucune suite à lancer."
        try:
            execution = subprocess.run(
                [sys.executable, "-m", "pytest", *suites, "-q", "-p", "no:randomly"],
                cwd=self.root, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return False, f"« {', '.join(suites)} » n'a pas rendu la main en {timeout}s."
        except (OSError, subprocess.SubprocessError) as erreur:
            return False, f"pytest n'a pas pu s'exécuter : {erreur}"
        return execution.returncode == 0, execution.stdout + execution.stderr

    # ------------------------------------------------------------------
    # Boucle éditer → tester → corriger
    # ------------------------------------------------------------------

    def edit_test_fix(
        self,
        chemin: str,
        proposer: Any,
        raison: str,
        approuver: Any = None,
        max_tentatives: int = MAX_TENTATIVES,
    ) -> LoopReport:
        """
        Boucle bornée : proposer, tester, corriger avec le retour de l'échec.

        Args:
            chemin: Fichier visé.
            proposer: Fonction `(echec_precedent) -> contenu` produisant le
                contenu. C'est **elle** qui appelle un modèle, quand il y en a
                un ; la boucle ne fabrique aucun code.
            raison: Motif transmis au portillon.
            approuver: Fonction `(request_id) -> bool` représentant la décision
                humaine. Sans elle, la boucle s'arrête sur `pending_approval` —
                elle n'auto-approuve jamais.
            max_tentatives: Nombre maximal de tours.

        Returns:
            Le déroulé complet, tentative par tentative.
        """
        rapport = LoopReport()
        echec_precedent = ""

        for _ in range(max(1, max_tentatives)):
            contenu = proposer(echec_precedent)
            if not contenu:
                rapport.detail = "Aucun contenu proposé : la boucle s'arrête."
                break

            propose = self.propose(chemin, contenu, raison)
            rapport.attempts.append(propose)
            if propose.status != "pending_approval":
                rapport.detail = propose.detail
                break

            if approuver is None or not approuver(propose.approval_request_id):
                rapport.detail = (
                    "Modification en attente d'une décision humaine : la boucle "
                    "ne s'auto-approuve pas (ADR-006)."
                )
                break

            applique = self.apply(propose.approval_request_id)
            rapport.attempts.append(applique)
            if applique.status == "applied" and applique.tests_passed is not False:
                rapport.succeeded = True
                rapport.detail = "Modification appliquée et vérifiée."
                return rapport

            echec_precedent = applique.output or applique.detail

        if not rapport.succeeded and not rapport.detail:
            rapport.detail = (
                f"{len(rapport.attempts)} tentative(s) sans succès : la boucle est "
                f"bornée pour ne pas consommer la requête."
            )
        return rapport
