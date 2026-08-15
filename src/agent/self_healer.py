"""
Diagnosing a failure, proposing a fix, and refusing to keep one that is not.

This is the engine the whole harness exists to restrain. Its shape follows from
one observation: the dangerous part of automated repair is not writing the patch,
it is **deciding the patch worked**. So the lifecycle separates the two, and
everything after `propose_patch` is a gate rather than a step.

    diagnose → workspace → propose → validate scope → apply (isolated)
    → tests → security tests → ruff → integrity → merge | rollback

Four rules shape the implementation:

**A traceback is data.** It arrives from a crashing program, and a crashing
program can be made to say anything. Text inside it — "ignore the rules", "delete
the tests" — is parsed for a file, a line and an exception type, and is never
read as an instruction. The parser looks for the shapes CPython emits and
nothing else.

**`UNKNOWN_DIAGNOSIS` is a real answer.** A guess dressed as a diagnosis sends a
repair at the wrong file, which is worse than stopping.

**Nothing is repaired in place.** Every attempt happens in its own git worktree.
Rollback destroys that worktree; the user's tree was never written to, so there
is nothing to restore.

**Three attempts, then stop.** A loop that keeps trying is a loop that keeps
changing a repository nobody is watching.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .audit import AuditJournal
from .policies.immutability import REPARATION_ORDINAIRE, check_patch_scope
from .policies.integrity import (
    compare_inventories,
    compare_protected_hashes,
    protected_test_hashes,
    inventory,
)
from .tools.commands import run_ruff, run_test_suite
from .tools.git_tools import (
    create_isolated_workspace,
    destroy_isolated_workspace,
    get_changed_files,
    get_diff,
    git_commit_changes,
)
from .tools.workspace import read_file, resolve, write_file

#: Tentatives maximales par incident. Au-delà, on s'arrête : un moteur qui
#: réessaie indéfiniment est un moteur qui modifie sans fin un dépôt que
#: personne ne regarde.
MAX_REPAIR_ATTEMPTS = 3

#: Fichiers modifiables au maximum par un correctif. Au-delà, ce n'est plus une
#: correction ciblée mais une réécriture, et elle mérite un humain.
MAX_FICHIERS = 5

#: Taille maximale d'un correctif, en octets de diff.
MAX_OCTETS_CORRECTIF = 60_000

#: Durée maximale d'une réparation complète, en secondes.
MAX_SECONDES = 1_800

#: Ce que le diagnostic peut conclure quand il ne conclut pas.
DIAGNOSTIC_INCONNU = "UNKNOWN_DIAGNOSIS"

#: Catégories de défaillance reconnues. Le lien entre une exception et une
#: catégorie est déclaré, jamais deviné : `KeyError` n'est pas « probablement un
#: problème de configuration », c'est un accès à une clé absente.
CATEGORIES = {
    "ImportError": "missing_import",
    "ModuleNotFoundError": "missing_import",
    "AttributeError": "missing_attribute",
    "TypeError": "wrong_type_or_signature",
    "ValueError": "invalid_value",
    "KeyError": "missing_key",
    "IndexError": "out_of_range",
    "AssertionError": "failed_expectation",
    "ZeroDivisionError": "division_by_zero",
    "FileNotFoundError": "missing_file",
    "PermissionError": "refused_by_policy",
    "TimeoutError": "timeout",
}

#: La ligne d'un cadre de pile, telle que CPython l'écrit. Rien d'autre n'est lu
#: dans une trace : le reste est du texte venu d'un programme qui plantait.
CADRE = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')

#: La dernière ligne d'une trace : `Type: message`.
EXCEPTION = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)\s*:\s*(.*)$")


@dataclass
class Diagnosis:
    """
    Ce qu'une trace permet d'affirmer, et rien de plus.

    Attributes:
        exception_type: Le type levé, s'il a été trouvé.
        message: Son message, tel quel — **données**, jamais instruction.
        file: Le fichier du dernier cadre appartenant au dépôt.
        line: Sa ligne.
        function: Sa fonction.
        module: Le module déduit du chemin.
        frames: Tous les cadres lus.
        category: La catégorie déclarée, ou `UNKNOWN_DIAGNOSIS`.
        confident: Vrai seulement si un fichier du dépôt a été identifié.
    """

    exception_type: str = ""
    message: str = ""
    file: str = ""
    line: int = 0
    function: str = ""
    module: str = ""
    frames: List[Dict[str, Any]] = field(default_factory=list)
    category: str = DIAGNOSTIC_INCONNU
    confident: bool = False

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "exception_type": self.exception_type,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "function": self.function,
            "module": self.module,
            "frames": self.frames,
            "category": self.category,
            "confident": self.confident,
        }


@dataclass
class PatchContext:
    """
    Le cadre d'une réparation : son incident, son espace, ses limites.

    Attributes:
        incident_id: L'identifiant, présent partout où cette réparation passe.
        diagnosis: Ce que la trace a permis d'affirmer.
        repair_class: `ORDINARY` ou `SECURITY_MAINTENANCE`.
        workspace: L'espace isolé, ouvert à la première application.
        attempts: Les tentatives déjà faites.
        started_at: Quand la réparation a commencé.
        snapshots: Contenu d'origine des fichiers touchés.
    """

    incident_id: str
    diagnosis: Diagnosis
    repair_class: str = REPARATION_ORDINAIRE
    workspace: Optional[Any] = None
    attempts: int = 0
    started_at: float = field(default_factory=time.time)
    snapshots: Dict[str, Optional[str]] = field(default_factory=dict)

    def elapsed(self) -> float:
        """Secondes écoulées depuis le début de la réparation."""
        return time.time() - self.started_at

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "incident_id": self.incident_id,
            "repair_class": self.repair_class,
            "attempts": self.attempts,
            "elapsed_s": round(self.elapsed(), 1),
            "workspace": self.workspace.as_dict() if self.workspace else None,
            "diagnosis": self.diagnosis.as_dict(),
        }


class GalSenSelfHealer:
    """
    Diagnostique, propose, vérifie — et annule quand la vérification échoue.

    Exemple:
        soigneur = GalSenSelfHealer()
        diagnostic = soigneur.diagnose(trace)
        contexte = soigneur.create_patch_context(diagnostic)
        soigneur.propose_patch(contexte, {"src/x.py": nouveau_contenu})
        rapport = soigneur.resolve(contexte)
    """

    def __init__(
        self,
        root: Optional[str] = None,
        journal: Optional[AuditJournal] = None,
        max_attempts: int = MAX_REPAIR_ATTEMPTS,
        test_target: Optional[str] = None,
        security_target: str = "tests/agent",
        lint_target: str = "src",
    ) -> None:
        """
        Args:
            root: La racine du dépôt gardé.
            journal: Le journal d'audit. Un journal propre au processus sinon.
            max_attempts: Tentatives par incident.
            test_target: Ce que la porte de régression exécute. `None` — le
                défaut — veut dire **toute la suite**. Ce réglage appartient à
                celui qui installe le harnais, jamais au correctif : un
                correctif qui choisirait l'étendue de son propre contrôle
                choisirait son verdict.
            security_target: La suite du harnais lui-même.
            lint_target: Ce que `ruff` inspecte.
        """
        from .tools.workspace import repo_root

        self.root = root or repo_root()
        self.journal = journal if journal is not None else AuditJournal()
        self.max_attempts = max(1, int(max_attempts))
        self.test_target = test_target
        self.security_target = security_target
        self.lint_target = lint_target

    # ------------------------------------------------------------------
    # 1. Diagnostiquer
    # ------------------------------------------------------------------

    def diagnose(self, traceback_str: str) -> Diagnosis:
        """
        Lit une trace d'exécution. **C'est une donnée, pas une consigne.**

        Le texte vient d'un programme qui plantait, et un programme qui plante
        peut avoir été amené à écrire n'importe quoi. Seules les formes que
        CPython produit sont lues — `File "...", line N, in f` et la dernière
        ligne `Type: message`. Une phrase impérative dans le message reste une
        chaîne de caractères.

        Args:
            traceback_str: La trace.

        Returns:
            Le diagnostic, `UNKNOWN_DIAGNOSIS` compris — une supposition
            déguisée en diagnostic envoie la réparation sur le mauvais fichier.
        """
        texte = str(traceback_str or "")
        diagnostic = Diagnosis()

        for fichier, ligne, fonction in CADRE.findall(texte):
            diagnostic.frames.append(
                {"file": fichier, "line": int(ligne), "function": fonction}
            )

        lignes = [brute.strip() for brute in texte.splitlines() if brute.strip()]
        for ligne in reversed(lignes):
            trouve = EXCEPTION.match(ligne)
            if trouve and not ligne.startswith("File "):
                diagnostic.exception_type = trouve.group(1).split(".")[-1]
                diagnostic.message = trouve.group(2)[:500]
                break

        # Le dernier cadre **du dépôt** : celui d'une bibliothèque tierce
        # désigne un fichier que cette réparation n'a pas à toucher.
        for cadre in reversed(diagnostic.frames):
            try:
                resolve(cadre["file"], self.root)
            except Exception:
                continue
            diagnostic.file = self._relatif(cadre["file"])
            diagnostic.line = cadre["line"]
            diagnostic.function = cadre["function"]
            diagnostic.module = diagnostic.file.replace("/", ".").removesuffix(".py")
            diagnostic.confident = True
            break

        diagnostic.category = CATEGORIES.get(
            diagnostic.exception_type, DIAGNOSTIC_INCONNU
        )
        if not diagnostic.confident:
            # Sans fichier du dépôt, il n'y a rien à réparer ici, même si le
            # type d'exception est connu.
            diagnostic.category = DIAGNOSTIC_INCONNU

        self.journal.record(
            "diagnosis", target=diagnostic.file or "—",
            result="found" if diagnostic.confident else DIAGNOSTIC_INCONNU,
            detail=f"{diagnostic.exception_type or 'inconnue'} → {diagnostic.category}",
        )
        return diagnostic

    def _relatif(self, chemin: str) -> str:
        """Le chemin d'un cadre, relativement au dépôt."""
        absolu = resolve(chemin, self.root)
        return os.path.relpath(absolu, self.root).replace(os.sep, "/")

    # ------------------------------------------------------------------
    # 2. Ouvrir un cadre de réparation
    # ------------------------------------------------------------------

    def create_patch_context(
        self, diagnosis: Diagnosis, repair_class: str = REPARATION_ORDINAIRE,
        incident_id: Optional[str] = None,
    ) -> PatchContext:
        """
        Ouvre le cadre d'une réparation.

        Args:
            diagnosis: Ce que la trace a donné.
            repair_class: La classification de la réparation.
            incident_id: Un identifiant imposé, pour les tests.

        Returns:
            Le contexte. **Aucun espace n'est encore ouvert** : un diagnostic
            inconnu ne doit pas créer de branche.
        """
        identifiant = incident_id or f"inc-{uuid.uuid4().hex[:10]}"
        contexte = PatchContext(
            incident_id=identifiant, diagnosis=diagnosis, repair_class=repair_class,
        )
        self.journal.record(
            "patch", incident_id=identifiant, target=diagnosis.file or "—",
            result="context_created", detail=f"classe {repair_class}",
        )
        return contexte

    # ------------------------------------------------------------------
    # 3. Proposer, valider, appliquer
    # ------------------------------------------------------------------

    def propose_patch(
        self, context: PatchContext, changes: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Retient un correctif sans rien écrire, et le juge sur sa portée.

        Args:
            context: Le cadre de la réparation.
            changes: Le contenu complet visé, par fichier.

        Returns:
            Le verdict de portée et les limites de ressources.
        """
        fichiers = sorted(changes)
        verdict = check_patch_scope(fichiers, context.repair_class)
        octets = sum(len(str(c).encode("utf-8")) for c in changes.values())

        limites = []
        if len(fichiers) > MAX_FICHIERS:
            limites.append(
                f"{len(fichiers)} fichiers, au-delà de {MAX_FICHIERS} : ce n'est "
                "plus une correction ciblée mais une réécriture."
            )
        if octets > MAX_OCTETS_CORRECTIF:
            limites.append(
                f"{octets} octets, au-delà de {MAX_OCTETS_CORRECTIF}."
            )
        if not fichiers:
            limites.append("Correctif vide : il n'y a rien à valider.")

        accepte = verdict["allowed"] and not limites
        self.journal.record(
            "policy", incident_id=context.incident_id, target=", ".join(fichiers)[:400],
            result="accepted" if accepte else "refused",
            detail="; ".join(limites) or "; ".join(r["reason"] for r in verdict["refused"]),
        )
        return {
            "accepted": accepte, "files": fichiers, "bytes": octets,
            "scope": verdict, "limits": limites,
        }

    def apply_patch(
        self, context: PatchContext, changes: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Écrit le correctif **dans un espace isolé**, jamais dans le dépôt.

        L'espace est ouvert au premier besoin ; les contenus d'origine sont
        retenus avant écriture, ce qui permet de restaurer un fichier sans
        toucher à git.

        Args:
            context: Le cadre de la réparation.
            changes: Le contenu complet visé, par fichier.

        Returns:
            Ce qui a été écrit, et où.

        Raises:
            RuntimeError: Si la portée n'a pas été acceptée, ou si les limites
                de tentatives ou de durée sont dépassées.
        """
        verdict = self.propose_patch(context, changes)
        if not verdict["accepted"]:
            raise RuntimeError(
                "Correctif refusé avant écriture : "
                + ("; ".join(verdict["limits"])
                   or "; ".join(r["reason"] for r in verdict["scope"]["refused"]))
            )
        if context.attempts >= self.max_attempts:
            raise RuntimeError(
                f"{context.attempts} tentatives pour « {context.incident_id} » : "
                f"la limite de {self.max_attempts} est atteinte, la réparation "
                "s'arrête."
            )
        if context.elapsed() > MAX_SECONDES:
            raise RuntimeError(
                f"Réparation « {context.incident_id} » au-delà de "
                f"{MAX_SECONDES} s : arrêt."
            )

        if context.workspace is None:
            context.workspace = create_isolated_workspace(
                context.incident_id, root=self.root
            )
            self.journal.record(
                "branch", incident_id=context.incident_id,
                target=context.workspace.branch, result="created",
                detail=f"espace isolé : {context.workspace.path}",
            )

        espace = context.workspace.path
        ecrits = []
        for chemin, contenu in sorted(changes.items()):
            if chemin not in context.snapshots:
                try:
                    context.snapshots[chemin] = read_file(chemin, root=espace)
                except Exception:
                    # `None` dit « ce fichier n'existait pas » : le restaurer
                    # voudra dire le supprimer, ce qui est la bonne réponse.
                    context.snapshots[chemin] = None
            ecrit = write_file(chemin, contenu, root=espace)
            ecrits.append(ecrit)
            self.journal.record(
                "write", incident_id=context.incident_id, target=chemin,
                result="written", hashes={"after": ecrit["sha256"]},
            )

        context.attempts += 1
        return {
            "workspace": espace, "branch": context.workspace.branch,
            "files": [e["path"] for e in ecrits], "attempt": context.attempts,
        }

    # ------------------------------------------------------------------
    # 4. Vérifier
    # ------------------------------------------------------------------

    def validate_patch(self, context: PatchContext) -> Dict[str, Any]:
        """
        Contrôle statique du correctif écrit : portée réelle et diff.

        Ce qui est jugé ici est ce que l'espace contient **réellement**, pas ce
        que l'appelant avait annoncé : un correctif qui touche un fichier de plus
        que prévu est exactement le cas à attraper.

        Args:
            context: Le cadre de la réparation.

        Returns:
            Les fichiers réellement modifiés, le diff et le verdict de portée.
        """
        if context.workspace is None:
            return {"valid": False, "reason": "Aucun correctif n'a été appliqué."}

        espace = context.workspace.path
        modifies = get_changed_files(espace)
        diff = get_diff(espace)
        verdict = check_patch_scope(modifies, context.repair_class)

        trop_gros = len(diff.encode("utf-8")) > MAX_OCTETS_CORRECTIF
        trop_nombreux = len(modifies) > MAX_FICHIERS
        valide = verdict["allowed"] and not trop_gros and not trop_nombreux

        self.journal.record(
            "patch", incident_id=context.incident_id, target=", ".join(modifies)[:400],
            result="valid" if valide else "invalid",
            detail=f"{len(modifies)} fichiers, {len(diff)} caractères de diff",
        )
        return {
            "valid": valide, "changed_files": modifies, "diff": diff[:MAX_OCTETS_CORRECTIF],
            "scope": verdict, "too_large": trop_gros, "too_many_files": trop_nombreux,
        }

    def run_validation(
        self, context: PatchContext, before: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Les portes qu'un correctif doit franchir pour être gardé.

        Toutes sont exécutées, même après un échec : savoir *combien* de portes
        cèdent vaut mieux que savoir laquelle a cédé en premier.

        Args:
            context: Le cadre de la réparation.
            before: L'inventaire des tests pris avant le correctif. Pris sur le
                dépôt d'origine s'il n'est pas fourni.

        Returns:
            Chaque porte, son verdict, et le verdict d'ensemble.
        """
        if context.workspace is None:
            return {"passed": False, "gates": {}, "reason": "Aucun correctif appliqué."}

        espace = context.workspace.path
        avant = before or inventory(self.root)
        empreintes_avant = protected_test_hashes(self.root)

        statique = self.validate_patch(context)
        tests = run_test_suite(target=self.test_target, cwd=espace, root=espace)
        lint = run_ruff(self.lint_target, cwd=espace, root=espace)

        # La suite de sécurité peut ne pas exister dans le dépôt gardé — ce
        # harnais est fait pour en garder d'autres que celui-ci. Une porte qui
        # échoue faute de cible ferait annuler **toute** réparation sur un tel
        # dépôt, ce qui n'est pas une garantie mais une panne.
        #
        # Elle n'est déclarée non applicable que si la cible manquait **déjà**
        # avant le correctif : la faire disparaître pour esquiver la porte est
        # attrapé par l'intégrité des tests, qui voit les fichiers supprimés.
        cible_avant = os.path.isdir(os.path.join(self.root, self.security_target))
        cible_apres = os.path.isdir(os.path.join(espace, self.security_target))
        if not cible_avant and not cible_apres:
            securite = {
                "applicable": False,
                "reason": (
                    f"Aucune suite de sécurité à « {self.security_target} » dans "
                    "ce dépôt : la porte n'est pas mesurée, et ne prétend pas "
                    "l'avoir été."
                ),
            }
        else:
            mesure = run_test_suite(
                target=self.security_target, cwd=espace, root=espace,
            )
            securite = {
                "applicable": True, "meaningful": mesure["meaningful"],
                "passed": mesure["passed"], "failed": mesure["failed"],
            }
        integrite = compare_inventories(avant, inventory(espace))
        proteges = compare_protected_hashes(empreintes_avant, protected_test_hashes(espace))

        portes = {
            "scope": {"passed": statique["valid"], "detail": statique.get("scope")},
            "tests": {"passed": tests["meaningful"], "detail": {
                "passed": tests["passed"], "failed": tests["failed"],
                "errors": tests["errors"], "timed_out": tests["timed_out"],
            }},
            "security_tests": {
                "passed": securite.get("meaningful", False),
                "applicable": securite["applicable"],
                "detail": securite,
            },
            "ruff": {"passed": lint["clean"], "detail": lint["stdout"][:1000]},
            "test_integrity": {"passed": integrite["intact"], "detail": {
                "deleted_files": integrite["deleted_files"],
                "deleted_tests": integrite["deleted_tests"],
                "disabled_tests": integrite["disabled_tests"],
                "weakened_tests": integrite["weakened_tests"],
            }},
            "protected_tests": {"passed": proteges["unchanged"], "detail": proteges},
        }

        # Une porte non applicable ne compte ni comme franchie ni comme tombée :
        # elle est **nommée**, et le rapport dit ce qui n'a pas été mesuré.
        tombees = [
            nom for nom, p in portes.items()
            if p.get("applicable", True) and not p["passed"]
        ]
        non_mesurees = [
            nom for nom, p in portes.items() if not p.get("applicable", True)
        ]

        self.journal.record(
            "test", incident_id=context.incident_id, target=espace,
            result="passed" if not tombees else "failed",
            detail=", ".join(
                f"{nom}=" + ("n/a" if not p.get("applicable", True)
                             else "ok" if p["passed"] else "KO")
                for nom, p in portes.items()
            ),
        )
        return {
            "passed": not tombees,
            "gates": portes,
            "failed_gates": tombees,
            "not_measured": non_mesurees,
        }

    # ------------------------------------------------------------------
    # 5. Conclure
    # ------------------------------------------------------------------

    def resolve(
        self, context: PatchContext, before: Optional[Dict[str, Any]] = None,
        merge: bool = False,
    ) -> Dict[str, Any]:
        """
        Décide du sort d'une réparation : garder, ou annuler.

        Args:
            context: Le cadre de la réparation.
            before: L'inventaire des tests pris avant.
            merge: Valider dans la branche de réparation quand tout passe. La
                fusion dans la branche de travail n'est **jamais** faite ici :
                elle appartient à quelqu'un qui a lu le diff.

        Returns:
            Le rapport complet : portes, décision, et ce qui reste.
        """
        validation = self.run_validation(context, before)

        if not validation["passed"]:
            annulation = self.rollback(context, raison="; ".join(validation["failed_gates"]))
            return {
                "incident_id": context.incident_id, "decision": "ROLLBACK",
                "validation": validation, "rollback": annulation,
                "attempts": context.attempts,
                "attempts_left": max(0, self.max_attempts - context.attempts),
                "detail": (
                    "Portes non franchies : " + ", ".join(validation["failed_gates"])
                ),
            }

        commit = None
        if merge:
            commit = git_commit_changes(
                f"fix({context.incident_id}): {context.diagnosis.category} — "
                f"réparation automatique validée",
                cwd=context.workspace.path,
            )
            self.journal.record(
                "merge", incident_id=context.incident_id,
                target=context.workspace.branch, result="committed",
                detail=commit["commit"],
            )

        return {
            "incident_id": context.incident_id, "decision": "KEEP",
            "validation": validation, "commit": commit,
            "branch": context.workspace.branch, "workspace": context.workspace.path,
            "attempts": context.attempts,
            "detail": (
                "Toutes les portes sont franchies. La branche de réparation "
                "existe ; la fusion appartient à quelqu'un qui a lu le diff."
            ),
        }

    def rollback(self, context: PatchContext, raison: str = "") -> Dict[str, Any]:
        """
        Annule une réparation : détruit l'espace isolé et sa branche.

        Il n'y a **rien à restaurer** dans le dépôt de l'utilisateur : rien n'y
        a jamais été écrit. C'est ce qui distingue cette annulation d'un
        `git reset --hard`, qui détruirait du travail que personne ne récupère.

        Args:
            context: Le cadre de la réparation.
            raison: Pourquoi l'annulation a lieu.

        Returns:
            Ce qui a été détruit.
        """
        if context.workspace is None:
            return {"rolled_back": False, "reason": "Aucun espace à détruire."}

        detruit = destroy_isolated_workspace(context.workspace, root=self.root)
        self.journal.record(
            "rollback", incident_id=context.incident_id,
            target=context.workspace.branch, result="destroyed", detail=raison[:500],
        )
        context.workspace = None
        return {"rolled_back": True, "reason": raison, **detruit}

    # ------------------------------------------------------------------
    # Rapport
    # ------------------------------------------------------------------

    def limits(self) -> Dict[str, Any]:
        """Les bornes qu'une réparation ne dépasse pas."""
        return {
            "max_repair_attempts": self.max_attempts,
            "max_files": MAX_FICHIERS,
            "max_patch_bytes": MAX_OCTETS_CORRECTIF,
            "max_seconds": MAX_SECONDES,
            "rules": [
                "Une trace est une **donnée** : rien de ce qu'elle contient "
                "n'est exécuté ni suivi comme une consigne.",
                f"`{DIAGNOSTIC_INCONNU}` est une réponse : une supposition "
                "déguisée en diagnostic envoie la réparation sur le mauvais "
                "fichier.",
                "Rien n'est réparé sur place : chaque tentative vit dans son "
                "propre arbre git, et annuler consiste à le détruire.",
                f"{MAX_REPAIR_ATTEMPTS} tentatives, puis arrêt.",
                "Toutes les portes sont exécutées, même après un échec : savoir "
                "combien cèdent vaut mieux que savoir laquelle a cédé en "
                "premier.",
            ],
        }
