"""
Tests du Coding Engine — contrat, confinement, routage, gouvernance (ADR-028).

Ces tests sont **déterministes** : aucun ne parle à un modèle, à un moteur
externe ou au réseau. Les moteurs réels sont éprouvés séparément dans
`tests/test_coding_adapters.py`, contre des exécutables et des serveurs
bouchons ; les tests vivants, eux, sont marqués `live` et ignorés par défaut.

Aucun test de ce fichier ne peut attendre indéfiniment : la seule fonction qui
lance un processus refuse un délai nul ou négatif, et les faux adaptateurs
rendent immédiatement.

Ce qui est vérifié ici, dans l'ordre de ce qui coûte cher quand c'est faux :

1. **Le confinement.** Rien ne s'écrit ni ne se lit hors de l'espace confié.
2. **La gouvernance.** Une instruction destructrice est refusée ; une
   instruction sensible passe par l'approbation existante ; l'audit reçoit une
   trace sans secret.
3. **La dégradation.** Un moteur absent ne fait pas tomber les autres.
4. **Le routage.** Le choix vient des capacités, jamais d'un nom en dur.
5. **La normalisation.** Tous les moteurs rendent la même forme de résultat.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def racines_declarees(monkeypatch, tmp_path_factory):
    """
    Déclare l'arborescence temporaire de pytest comme racine autorisée.

    Sans cela, `resolve_workspace()` refuse tout : une variable
    `GALSEN_CODING_WORKSPACE_ROOTS` absente ne vaut pas « tout l'hôte ». La
    déclaration est faite ici, visible, plutôt que contournée — c'est
    exactement le geste qu'un exploitant devra poser.
    """
    monkeypatch.setenv(
        "GALSEN_CODING_WORKSPACE_ROOTS", str(tmp_path_factory.getbasetemp())
    )


from src.approval_engine.approval_manager import ApprovalManagerImpl  # noqa: E402
from src.audit_engine.audit_manager import AuditManagerImpl  # noqa: E402
from src.audit_engine.types import AuditEventType, AuditStatus  # noqa: E402
from src.coding_engine import (  # noqa: E402
    CodingCapability,
    CodingEngineAdapter,
    CodingEngineManager,
    CodingRouter,
    CodingStatus,
    CodingTask,
    CodingTaskResult,
    EngineAvailability,
    ModelSpec,
    infer_capabilities,
)
from src.coding_engine.execution import politique_de_codage, run_process  # noqa: E402
# `TestReport` est renommé : pytest tenterait de collecter une classe dont le
# nom commence par `Test`, et signalerait qu'elle a un constructeur.
from src.coding_engine.types import FileChange  # noqa: E402
from src.coding_engine.types import TestReport as RapportDeTests  # noqa: E402
from src.coding_engine.workspace import (  # noqa: E402
    WorkspaceError,
    confine,
    declared_roots,
    diff_snapshots,
    inspect_instruction,
    resolve_workspace,
    sanitized_environment,
    snapshot,
)

MODELE = ModelSpec(provider_id="local", model_name="qwen2.5-coder:14b",
                   base_url="http://127.0.0.1:11434")


class _FauxAdaptateur(CodingEngineAdapter):
    """Adaptateur déterministe : il n'exécute rien, il enregistre."""

    def __init__(
        self,
        engine_id: str,
        capabilities: List[CodingCapability],
        primary: Optional[CodingCapability] = None,
        available: bool = True,
        leve: bool = False,
    ):
        self.engine_id = engine_id
        self.display_name = engine_id
        self.capabilities = capabilities
        self.primary_capability = primary
        self._available = available
        self._leve = leve
        self.appels: List[CodingTask] = []
        self.modeles: List[Optional[ModelSpec]] = []

    def check_availability(self) -> EngineAvailability:
        if self._leve:
            raise RuntimeError("sonde cassée")
        return EngineAvailability(
            engine_id=self.engine_id, available=self._available,
            detail="" if self._available else "moteur d'essai désactivé",
            capabilities=self.capabilities,
        )

    def execute(self, task: CodingTask, model: Optional[ModelSpec]) -> CodingTaskResult:
        if self._leve:
            raise RuntimeError("moteur cassé")
        self.appels.append(task)
        self.modeles.append(model)
        return CodingTaskResult(
            status=CodingStatus.SUCCESS, engine_id=self.engine_id, task_id=task.id,
            summary="fait", model=model,
        )


class _FauxModelManager:
    """Rend le modèle qu'on lui a donné, ou rien."""

    def __init__(self, item=None, leve: bool = False):
        self._item = item
        self._leve = leve

    def select_model_for_task(self, exigences):
        if self._leve:
            raise RuntimeError("moteur de modèles cassé")
        return self._item


class _FauxModelItem:
    """Imite `ModelItem` pour la traduction en `ModelSpec`."""

    def __init__(self, provider="local", name="qwen2.5-coder:14b", metadata=None):
        self.provider = provider
        self.name = name
        self.model_id = name
        self.metadata = metadata or {}


@pytest.fixture
def espace(tmp_path):
    """Un espace de travail avec un fichier dedans."""
    (tmp_path / "module.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def _gestionnaire(adaptateurs, **extras) -> CodingEngineManager:
    """Construit un gestionnaire avec audit et approbation réels en mémoire."""
    defauts = {
        "audit_manager": AuditManagerImpl(),
        "approval_manager": ApprovalManagerImpl(),
        "model_manager": _FauxModelManager(_FauxModelItem()),
    }
    defauts.update(extras)
    return CodingEngineManager(adapters=adaptateurs, **defauts)


# ======================================================================
# 1. Confinement
# ======================================================================

class TestConfinement:
    """Rien ne sort de l'espace de travail. C'est la garde qui compte le plus."""

    @pytest.mark.parametrize("chemin", ["../dehors.py", "a/../../dehors.py", "/etc/passwd", "~/x"])
    def test_un_chemin_qui_sort_est_refuse(self, espace, chemin):
        """Une instruction mal comprise ne doit pas pouvoir toucher `~/.ssh`."""
        with pytest.raises(WorkspaceError):
            confine(espace, chemin)

    def test_un_lien_symbolique_qui_sort_est_refuse(self, tmp_path):
        """Un chemin relatif inoffensif peut mener dehors par un lien."""
        interieur = tmp_path / "espace"
        interieur.mkdir()
        dehors = tmp_path / "dehors"
        dehors.mkdir()
        try:
            (interieur / "lien").symlink_to(dehors)
        except (OSError, NotImplementedError):  # pragma: no cover
            pytest.skip("Liens symboliques indisponibles.")
        with pytest.raises(WorkspaceError):
            confine(interieur.resolve(), "lien/cible.txt")

    def test_un_chemin_interieur_passe(self, espace):
        """Le confinement ne doit pas rendre l'espace inutilisable."""
        assert confine(espace, "module.py").name == "module.py"

    def test_un_espace_inexistant_est_refuse(self, tmp_path):
        """Travailler dans un dossier absent créerait des fichiers au hasard."""
        with pytest.raises(WorkspaceError, match="n'existe pas"):
            resolve_workspace(tmp_path / "absent")

    def test_un_fichier_n_est_pas_un_espace(self, espace):
        """Confondre fichier et dossier ferait échouer le moteur plus loin."""
        with pytest.raises(WorkspaceError, match="pas un dossier"):
            resolve_workspace(espace / "module.py")

    def test_le_gestionnaire_refuse_un_espace_invalide(self, tmp_path):
        """Le contrôle est fait avant tout choix de moteur."""
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])
        resultat = _gestionnaire([adaptateur]).execute(
            CodingTask(instruction="modifie x", workspace=str(tmp_path / "absent"))
        )
        assert resultat.status is CodingStatus.FAILURE
        assert adaptateur.appels == []


class TestEnvironnementFiltre:
    """Un sous-processus ne doit pas hériter des secrets de la plateforme."""

    def test_les_variables_de_la_plateforme_ne_passent_pas(self, monkeypatch):
        """C'est la fuite la plus facile à provoquer et la plus coûteuse."""
        monkeypatch.setenv("GALSEN_API_KEYS", "secret:admin:moi")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws_secret")
        environnement = sanitized_environment()
        assert "GALSEN_API_KEYS" not in environnement
        assert "GITHUB_TOKEN" not in environnement
        assert "AWS_SECRET_ACCESS_KEY" not in environnement

    def test_le_strict_necessaire_passe(self, monkeypatch):
        """Sans PATH, aucun exécutable ne démarre."""
        monkeypatch.setenv("PATH", "/usr/bin")
        assert sanitized_environment()["PATH"] == "/usr/bin"

    def test_ce_que_le_moteur_doit_savoir_est_ajoute(self):
        """L'adresse du modèle est ajoutée explicitement, pas héritée."""
        environnement = sanitized_environment({"OLLAMA_API_BASE": "http://x:11434"})
        assert environnement["OLLAMA_API_BASE"] == "http://x:11434"

    def test_une_valeur_nulle_n_est_pas_ajoutee(self):
        """Une variable à `None` casserait `subprocess`."""
        assert "VIDE" not in sanitized_environment({"VIDE": None})


# ======================================================================
# 2. Gouvernance : refus, approbation, audit
# ======================================================================

class TestInstructionsRefusees:
    """Certaines demandes ne sont pas approuvables : elles sont refusées."""

    @pytest.mark.parametrize("instruction", [
        "rm -rf / pour repartir propre",
        "fais un mkfs.ext4 sur le disque",
        "dd if=/dev/zero of=/dev/sda",
        "chmod -R 777 / pour régler les droits",
    ])
    def test_une_instruction_destructrice_est_refusee(self, espace, instruction):
        """Aucun moteur ne doit voir ces demandes, même avec approbation."""
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.SHELL_EXECUTION])
        resultat = _gestionnaire([adaptateur]).execute(
            CodingTask(instruction=instruction, workspace=str(espace))
        )
        assert resultat.status is CodingStatus.REJECTED
        assert adaptateur.appels == []

    def test_le_refus_dit_qu_il_n_est_pas_contournable(self, espace):
        """Sinon l'appelant chercherait une approbation qui n'existera jamais."""
        resultat = _gestionnaire([_FauxAdaptateur("e", [])]).execute(
            CodingTask(instruction="rm -rf / maintenant", workspace=str(espace))
        )
        assert "approbation" in resultat.summary.lower()

    def test_une_instruction_ordinaire_passe(self, espace):
        """Le filtre ne doit pas bloquer le travail normal."""
        verdict = inspect_instruction("Ajoute un test pour la fonction de calcul")
        assert verdict.allowed is True
        assert verdict.needs_approval is False


class TestApprobation:
    """Le moteur d'approbation existant (ADR-006) est réutilisé, pas doublé."""

    @pytest.mark.parametrize("instruction", [
        "fais un git push vers origin",
        "supprime avec rm -rf le dossier build",
        "mets à jour la configuration de production",
        "lis le fichier .env pour trouver la clé",
    ])
    def test_une_instruction_sensible_attend_un_humain(self, espace, instruction):
        """L'exécution s'arrête avant le moteur, pas après."""
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.SHELL_EXECUTION])
        resultat = _gestionnaire([adaptateur]).execute(
            CodingTask(instruction=instruction, workspace=str(espace))
        )
        assert resultat.status is CodingStatus.REQUIRES_APPROVAL
        assert resultat.approval_request_id
        assert adaptateur.appels == []

    def test_la_demande_entre_dans_la_file_existante(self, espace):
        """Une seconde file d'approbation serait une seconde vérité."""
        approbation = ApprovalManagerImpl()
        gestionnaire = _gestionnaire([_FauxAdaptateur("e", [])], approval_manager=approbation)
        gestionnaire.execute(
            CodingTask(instruction="git push origin main", workspace=str(espace))
        )
        assert approbation.count(status="pending") == 1

    def test_une_approbation_accordee_laisse_passer(self, espace):
        """Sans cela, la porte ne s'ouvrirait jamais."""
        approbation = ApprovalManagerImpl()
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.SHELL_EXECUTION])
        gestionnaire = _gestionnaire([adaptateur], approval_manager=approbation)

        premier = gestionnaire.execute(
            CodingTask(instruction="git push origin main", workspace=str(espace))
        )
        approbation.approve(premier.approval_request_id, decided_by="omar")

        second = gestionnaire.execute(CodingTask(
            instruction="git push origin main", workspace=str(espace),
            metadata={"approval_request_id": premier.approval_request_id},
        ))
        assert second.status is CodingStatus.SUCCESS
        assert len(adaptateur.appels) == 1

    def test_une_approbation_refusee_arrete_tout(self, espace):
        """Un refus humain doit peser autant qu'un accord."""
        approbation = ApprovalManagerImpl()
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.SHELL_EXECUTION])
        gestionnaire = _gestionnaire([adaptateur], approval_manager=approbation)

        premier = gestionnaire.execute(
            CodingTask(instruction="git push origin main", workspace=str(espace))
        )
        approbation.reject(premier.approval_request_id, reason="pas maintenant", decided_by="omar")

        second = gestionnaire.execute(CodingTask(
            instruction="git push origin main", workspace=str(espace),
            metadata={"approval_request_id": premier.approval_request_id},
        ))
        assert second.status is CodingStatus.REJECTED
        assert adaptateur.appels == []

    def test_sans_moteur_d_approbation_on_refuse(self, espace):
        """Une porte de gouvernance absente n'est pas une porte ouverte."""
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.SHELL_EXECUTION])
        gestionnaire = _gestionnaire([adaptateur], approval_manager=None)
        resultat = gestionnaire.execute(
            CodingTask(instruction="git push origin main", workspace=str(espace))
        )
        assert resultat.status is CodingStatus.REJECTED
        assert adaptateur.appels == []

    def test_allow_push_dispense_de_l_approbation(self, espace):
        """L'appelant qui a déjà déclaré vouloir publier ne la redemande pas."""
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.SHELL_EXECUTION])
        resultat = _gestionnaire([adaptateur]).execute(CodingTask(
            instruction="git push origin main", workspace=str(espace), allow_push=True,
        ))
        assert resultat.status is CodingStatus.SUCCESS


class TestAudit:
    """Chaque exécution laisse une trace, et aucune trace ne porte de secret."""

    def test_une_execution_est_tracee(self, espace):
        """Sans trace, une modification de dépôt n'a pas d'auteur."""
        audit = AuditManagerImpl()
        gestionnaire = _gestionnaire(
            [_FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])], audit_manager=audit
        )
        resultat = gestionnaire.execute(
            CodingTask(instruction="modifie module.py", workspace=str(espace))
        )
        assert resultat.audit_id
        assert audit.get_event(resultat.audit_id) is not None

    def test_la_trace_porte_sa_categorie(self, espace):
        """Rangée sous `tool`, elle se noierait parmi les lectures de fichiers."""
        audit = AuditManagerImpl()
        gestionnaire = _gestionnaire(
            [_FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])], audit_manager=audit
        )
        resultat = gestionnaire.execute(
            CodingTask(instruction="modifie module.py", workspace=str(espace))
        )
        assert audit.get_event(resultat.audit_id).event_type is AuditEventType.CODING

    def test_un_refus_est_trace_aussi(self, espace):
        """Ce qui a été refusé est aussi intéressant que ce qui a été fait."""
        audit = AuditManagerImpl()
        gestionnaire = _gestionnaire([_FauxAdaptateur("e", [])], audit_manager=audit)
        gestionnaire.execute(
            CodingTask(instruction="rm -rf / vite", workspace=str(espace))
        )
        assert audit.count() == 1

    def test_une_attente_d_approbation_est_tracee_comme_telle(self, espace):
        """L'audit doit distinguer « en attente » de « échoué »."""
        audit = AuditManagerImpl()
        gestionnaire = _gestionnaire([_FauxAdaptateur("e", [])], audit_manager=audit)
        resultat = gestionnaire.execute(
            CodingTask(instruction="git push origin main", workspace=str(espace))
        )
        evenement = audit.get_event(resultat.audit_id)
        assert evenement.status is AuditStatus.REQUIRES_APPROVAL

    def test_aucune_cle_n_entre_dans_la_trace(self, espace, monkeypatch):
        """`ModelSpec` ne porte que le **nom** de la variable, jamais sa valeur."""
        monkeypatch.setenv("MA_CLE_SECRETE", "valeur-tres-secrete")
        audit = AuditManagerImpl()
        gestionnaire = _gestionnaire(
            [_FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])],
            audit_manager=audit,
            model_manager=_FauxModelManager(
                _FauxModelItem(metadata={"api_key_env": "MA_CLE_SECRETE"})
            ),
        )
        resultat = gestionnaire.execute(
            CodingTask(instruction="modifie module.py", workspace=str(espace))
        )
        trace = str(audit.get_event(resultat.audit_id).to_dict())
        assert "valeur-tres-secrete" not in trace
        assert "MA_CLE_SECRETE" in trace

    def test_un_audit_en_panne_ne_casse_pas_l_execution(self, espace):
        """L'audit est une obligation, pas un point de défaillance unique."""
        class _AuditCasse:
            def record(self, evenement):
                raise RuntimeError("magasin plein")

        gestionnaire = _gestionnaire(
            [_FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])],
            audit_manager=_AuditCasse(),
        )
        resultat = gestionnaire.execute(
            CodingTask(instruction="modifie module.py", workspace=str(espace))
        )
        assert resultat.status is CodingStatus.SUCCESS
        assert resultat.audit_id is None


class TestPolitiqueDeConteneur:
    """L'exploitant peut exiger une isolation réelle."""

    def test_hors_conteneur_l_execution_est_refusee(self, espace, monkeypatch):
        """Sans conteneur, un moteur voit tout ce que voit l'utilisateur courant."""
        monkeypatch.setenv("GALSEN_CODING_REQUIRE_CONTAINER", "1")
        monkeypatch.setattr(
            "src.coding_engine.manager.running_in_container", lambda: False
        )
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])
        resultat = _gestionnaire([adaptateur]).execute(
            CodingTask(instruction="modifie module.py", workspace=str(espace))
        )
        assert resultat.status is CodingStatus.REJECTED
        assert adaptateur.appels == []

    def test_dans_un_conteneur_l_execution_passe(self, espace, monkeypatch):
        """L'exigence satisfaite ne doit rien bloquer."""
        monkeypatch.setenv("GALSEN_CODING_REQUIRE_CONTAINER", "1")
        monkeypatch.setattr(
            "src.coding_engine.manager.running_in_container", lambda: True
        )
        resultat = _gestionnaire(
            [_FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])]
        ).execute(CodingTask(instruction="modifie module.py", workspace=str(espace)))
        assert resultat.status is CodingStatus.SUCCESS


# ======================================================================
# 3. Dégradation : un moteur absent n'emporte pas les autres
# ======================================================================

class TestDegradation:
    """La plateforme reste utilisable quand un moteur manque."""

    def test_un_moteur_indisponible_n_est_jamais_choisi(self, espace):
        """Choisir un moteur absent produirait une panne au lieu d'un motif."""
        absent = _FauxAdaptateur("absent", [CodingCapability.TARGETED_EDIT], available=False)
        present = _FauxAdaptateur("present", [CodingCapability.TARGETED_EDIT])
        resultat = _gestionnaire([absent, present]).execute(
            CodingTask(instruction="modifie module.py", workspace=str(espace))
        )
        assert resultat.engine_id == "present"

    def test_aucun_moteur_disponible_rend_un_motif(self, espace):
        """Une indisponibilité doit se lire, pas se deviner."""
        resultat = _gestionnaire([
            _FauxAdaptateur("a", [CodingCapability.TARGETED_EDIT], available=False),
            _FauxAdaptateur("b", [CodingCapability.TARGETED_EDIT], available=False),
        ]).execute(CodingTask(instruction="modifie module.py", workspace=str(espace)))
        assert resultat.status is CodingStatus.UNAVAILABLE
        assert resultat.errors

    def test_une_sonde_qui_leve_ne_casse_pas_l_etat(self):
        """Un moteur tiers mal élevé ne doit pas faire tomber `/coding/engines`."""
        gestionnaire = _gestionnaire([
            _FauxAdaptateur("casse", [CodingCapability.TARGETED_EDIT], leve=True),
            _FauxAdaptateur("sain", [CodingCapability.TARGETED_EDIT]),
        ])
        etat = gestionnaire.status()
        assert etat["available_engines"] == ["sain"]
        assert etat["any_available"] is True

    def test_un_moteur_qui_leve_devient_un_echec_pas_une_exception(self, espace):
        """L'appelant reçoit un résultat, jamais une pile d'exécution."""
        class _Casse(_FauxAdaptateur):
            def check_availability(self):
                return EngineAvailability(engine_id=self.engine_id, available=True)

            def execute(self, task, model):
                raise RuntimeError("le moteur a explosé")

        resultat = _gestionnaire([
            _Casse("casse", [CodingCapability.TARGETED_EDIT])
        ]).execute(CodingTask(instruction="modifie module.py", workspace=str(espace)))
        assert resultat.status is CodingStatus.FAILURE
        assert "explosé" in resultat.errors[0]

    def test_un_moteur_impose_mais_absent_ne_bascule_pas_ailleurs(self, espace):
        """Un autre moteur ne serait pas ce qui a été demandé."""
        resultat = _gestionnaire([
            _FauxAdaptateur("voulu", [CodingCapability.TARGETED_EDIT], available=False),
            _FauxAdaptateur("autre", [CodingCapability.TARGETED_EDIT]),
        ]).execute(CodingTask(
            instruction="modifie module.py", workspace=str(espace), engine_id="voulu"
        ))
        assert resultat.status is CodingStatus.UNAVAILABLE

    def test_un_moteur_inconnu_est_signale(self, espace):
        """Une faute de frappe doit se voir tout de suite."""
        resultat = _gestionnaire([
            _FauxAdaptateur("aider", [CodingCapability.TARGETED_EDIT])
        ]).execute(CodingTask(
            instruction="modifie module.py", workspace=str(espace), engine_id="aidre"
        ))
        assert resultat.status is CodingStatus.UNAVAILABLE
        assert "aider" in resultat.summary


# ======================================================================
# 4. Routage
# ======================================================================

class TestRoutage:
    """Le choix vient des capacités. Aucun nom de moteur n'est écrit en dur."""

    def _routeur(self) -> CodingRouter:
        """Trois moteurs aux spécialités distinctes, comme les vrais."""
        return CodingRouter([
            _FauxAdaptateur(
                "edition", [CodingCapability.TARGETED_EDIT,
                            CodingCapability.REPOSITORY_EXPLORATION],
                primary=CodingCapability.TARGETED_EDIT,
            ),
            _FauxAdaptateur(
                "probleme", [CodingCapability.ISSUE_RESOLUTION,
                             CodingCapability.REPOSITORY_EXPLORATION,
                             CodingCapability.TARGETED_EDIT],
                primary=CodingCapability.ISSUE_RESOLUTION,
            ),
            _FauxAdaptateur(
                "autonome", [CodingCapability.AUTONOMOUS_IMPLEMENTATION,
                             CodingCapability.TEST_EXECUTION,
                             CodingCapability.TARGETED_EDIT,
                             CodingCapability.ISSUE_RESOLUTION,
                             CodingCapability.REPOSITORY_EXPLORATION],
                primary=CodingCapability.AUTONOMOUS_IMPLEMENTATION,
            ),
        ])

    @pytest.mark.parametrize("instruction,attendu", [
        ("Corrige ce bug et enquête dans le dépôt", "probleme"),
        ("Fix this issue and investigate the repository", "probleme"),
        ("Modifie ces fichiers selon mes instructions", "edition"),
        ("Modify these files according to my instructions", "edition"),
        ("Implémente cette fonctionnalité complète et itère", "autonome"),
        ("Implement this complete feature, run tests and iterate", "autonome"),
    ])
    def test_l_intention_mene_au_bon_moteur(self, instruction, attendu):
        """Les trois exemples du cahier des charges, en français et en anglais."""
        decision = self._routeur().route(CodingTask(instruction=instruction, workspace="."))
        assert decision.engine_id == attendu

    def test_la_decision_porte_sa_raison(self):
        """Un routage sans explication est impossible à corriger."""
        decision = self._routeur().route(
            CodingTask(instruction="Corrige ce bug", workspace=".")
        )
        assert decision.reason
        assert decision.inferred_capabilities

    def test_une_capacite_exigee_prime_sur_le_texte(self):
        """L'appelant qui sait ce qu'il veut ne doit pas être deviné."""
        decision = self._routeur().route(CodingTask(
            instruction="Corrige ce bug", workspace=".",
            capabilities=[CodingCapability.AUTONOMOUS_IMPLEMENTATION],
        ))
        assert decision.engine_id == "autonome"

    def test_un_moteur_qui_ne_couvre_pas_est_ecarte_avec_le_motif(self):
        """« ne couvre pas » et « indisponible » appellent des gestes différents."""
        decision = self._routeur().route(CodingTask(
            instruction="peu importe", workspace=".",
            capabilities=[CodingCapability.AUTONOMOUS_IMPLEMENTATION],
        ))
        assert "ne couvre pas" in decision.rejected["edition"]

    def test_une_demande_sans_signal_va_au_plus_polyvalent(self):
        """Rien n'est deviné : à défaut d'intention, on prend la plus large couverture."""
        decision = self._routeur().route(
            CodingTask(instruction="fais quelque chose d'utile", workspace=".")
        )
        assert decision.engine_id == "autonome"
        assert decision.inferred_capabilities == []

    def test_le_routage_est_reproductible(self):
        """Deux appels identiques doivent donner le même moteur."""
        routeur = self._routeur()
        tache = CodingTask(instruction="Corrige ce bug", workspace=".")
        assert routeur.route(tache).engine_id == routeur.route(tache).engine_id

    def test_un_moteur_ajoute_est_route_sans_toucher_au_routeur(self):
        """C'est la raison d'être de la couche : l'extensibilité se teste."""
        nouveau = _FauxAdaptateur(
            "documentation", [CodingCapability.TARGETED_EDIT],
            primary=CodingCapability.TARGETED_EDIT,
        )
        routeur = CodingRouter([nouveau])
        decision = routeur.route(
            CodingTask(instruction="Modifie ces fichiers", workspace=".")
        )
        assert decision.engine_id == "documentation"

    def test_l_enregistrement_remplace_un_moteur_de_meme_nom(self):
        """Remplacer un moteur externe ne doit pas demander de réécriture."""
        gestionnaire = _gestionnaire([_FauxAdaptateur("aider", [])])
        gestionnaire.register(_FauxAdaptateur("aider", [CodingCapability.TARGETED_EDIT]))
        assert gestionnaire.engine_ids.count("aider") == 1
        assert gestionnaire.get("aider").capabilities == [CodingCapability.TARGETED_EDIT]

    @pytest.mark.parametrize("instruction,capacite", [
        ("corrige le bogue de la page", CodingCapability.ISSUE_RESOLUTION),
        ("implémente la fonctionnalité complète", CodingCapability.AUTONOMOUS_IMPLEMENTATION),
        ("renomme la méthode dans ce fichier", CodingCapability.TARGETED_EDIT),
        ("lance les tests du dépôt", CodingCapability.TEST_EXECUTION),
    ])
    def test_la_table_de_signaux_reconnait_les_intentions(self, instruction, capacite):
        """La table est le seul endroit à modifier pour affiner le routage."""
        assert capacite in infer_capabilities(instruction)


# ======================================================================
# 5. Modèle : indépendance vis-à-vis des fournisseurs
# ======================================================================

class TestIndependanceDesFournisseurs:
    """Aucun moteur ne choisit son modèle ; aucun fournisseur n'est privilégié."""

    def test_le_modele_vient_du_model_engine(self, espace):
        """C'est la condition de l'indépendance : une seule source de décision."""
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])
        _gestionnaire(
            [adaptateur],
            model_manager=_FauxModelManager(
                _FauxModelItem(provider="openai_compatible", name="mon-modele")
            ),
        ).execute(CodingTask(instruction="modifie module.py", workspace=str(espace)))
        assert adaptateur.modeles[0].provider_id == "openai_compatible"
        assert adaptateur.modeles[0].model_name == "mon-modele"

    def test_sans_modele_l_adaptateur_recoit_none(self, espace):
        """À lui de rapporter l'indisponibilité, pas d'en inventer un."""
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])
        _gestionnaire([adaptateur], model_manager=_FauxModelManager(None)).execute(
            CodingTask(instruction="modifie module.py", workspace=str(espace))
        )
        assert adaptateur.modeles[0] is None

    def test_un_moteur_de_modeles_en_panne_ne_casse_pas_l_execution(self, espace):
        """La panne devient une absence de modèle, pas une exception."""
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])
        _gestionnaire([adaptateur], model_manager=_FauxModelManager(leve=True)).execute(
            CodingTask(instruction="modifie module.py", workspace=str(espace))
        )
        assert adaptateur.modeles[0] is None

    def test_aucune_dependance_cachee_a_un_fournisseur(self):
        """Le moteur n'importe, ne contacte et ne lit aucun fournisseur nommé.

        C'est la contrainte posée par le cahier des charges : GalSen IA ne doit
        pas acquérir de dépendance cachée à un fournisseur parce qu'un des
        projets intégrés en utilise un.

        Le test cherche une dépendance **réelle** — un import, une adresse, une
        variable de clé — et non l'apparition d'un mot : la documentation du
        moteur nomme précisément les fournisseurs qu'elle exclut, et un test
        qui compterait les mots ferait échouer cette phrase-là.
        """
        interdits = (
            "import anthropic", "from anthropic", "api.anthropic.com",
            "ANTHROPIC_API_KEY", "import openai", "from openai",
            "api.openai.com", "OPENAI_MODEL", "claude-opus", "claude-sonnet",
            "gpt-4", "gpt-5",
        )
        racine = os.path.join(os.path.dirname(__file__), "..", "src", "coding_engine")
        for dossier, _, fichiers in os.walk(racine):
            for nom in fichiers:
                if not nom.endswith(".py"):
                    continue
                contenu = open(os.path.join(dossier, nom), encoding="utf-8").read()
                for interdit in interdits:
                    assert interdit not in contenu, f"{nom} dépend de « {interdit} »"

    def test_la_cle_n_est_jamais_dans_le_modelspec(self):
        """Le type traverse l'audit : il ne porte que le **nom** de la variable."""
        spec = ModelSpec(provider_id="local", model_name="x", api_key_env="MA_CLE")
        assert "MA_CLE" in str(spec.to_dict())
        assert "api_key" not in spec.to_dict()


# ======================================================================
# 6. Bornes d'exécution
# ======================================================================

class TestBornes:
    """Aucune exécution ne peut attendre indéfiniment."""

    def test_un_delai_nul_est_refuse(self, tmp_path):
        """Un délai nul serait une attente sans fin déguisée."""
        with pytest.raises(ValueError):
            run_process(["true"], cwd=tmp_path, timeout_seconds=0)

    def test_une_commande_vide_est_refusee(self, tmp_path):
        """Rien à lancer n'est pas une réussite."""
        with pytest.raises(ValueError):
            run_process([], cwd=tmp_path, timeout_seconds=5)

    def test_un_processus_trop_long_est_arrete(self, tmp_path):
        """La garantie centrale de la couche d'exécution."""
        resultat = run_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path, timeout_seconds=2,
        )
        assert resultat.timed_out is True
        assert resultat.ok is False
        assert resultat.duration_seconds < 20

    def test_un_executable_absent_est_signale_sans_lever(self, tmp_path):
        """L'appelant reçoit un motif, pas une exception système."""
        resultat = run_process(
            ["executable-qui-n-existe-pas"], cwd=tmp_path, timeout_seconds=5,
        )
        assert resultat.started is False
        assert resultat.error

    def test_la_sortie_est_bornee(self, tmp_path):
        """Un moteur bavard ne doit pas remplir la mémoire ni l'audit."""
        resultat = run_process(
            [sys.executable, "-c", "print('x' * 2000000)"],
            cwd=tmp_path, timeout_seconds=30,
        )
        assert len(resultat.stdout) < 400_000

    def test_les_variables_fournies_atteignent_le_processus(self, tmp_path):
        """L'adresse du modèle ne passe ni par `os.environ` ni par la ligne.

        Par `os.environ` elle serait posée sur la plateforme entière ; en
        argument elle serait visible de toute la machine.
        """
        resultat = run_process(
            [sys.executable, "-c", "import os; print(os.environ.get('GALSEN_ESSAI', 'absent'))"],
            cwd=tmp_path, timeout_seconds=30,
            extra_environment={"GALSEN_ESSAI": "valeur-fournie"},
        )
        assert "valeur-fournie" in resultat.stdout
        assert "GALSEN_ESSAI" not in os.environ

    def test_les_bornes_du_codage_depassent_celles_d_un_fragment(self):
        """Un moteur de codage franchirait les bornes par défaut en démarrant."""
        politique = politique_de_codage(600)
        assert politique.wall_seconds == 600
        assert politique.memory_bytes >= 2 * 1024 ** 3
        assert politique.cpu_seconds >= 600

    def test_un_delai_demesure_est_ramene(self, espace):
        """Une heure au maximum : au-delà, un fil serait immobilisé la journée."""
        adaptateur = _FauxAdaptateur("essai", [CodingCapability.TARGETED_EDIT])
        _gestionnaire([adaptateur]).execute(CodingTask(
            instruction="modifie module.py", workspace=str(espace),
            timeout_seconds=999999,
        ))
        assert adaptateur.appels[0].timeout_seconds == 3600

    def test_la_commande_complete_n_entre_pas_dans_la_trace(self, tmp_path):
        """SWE-agent prend une clé en argument : la ligne ne doit pas être tracée."""
        resultat = run_process(
            [sys.executable, "-c", "pass", "--api-key=secret-en-argument"],
            cwd=tmp_path, timeout_seconds=30,
        )
        assert "secret-en-argument" not in str(resultat.to_dict())

    def test_l_execution_passe_par_le_bac_a_sable_de_la_plateforme(self, tmp_path):
        """Le Coding Engine ne porte pas sa propre boucle `subprocess`.

        La première version en avait une. Elle marchait et elle était moins
        bonne : le bac à sable ajoute les limites du noyau et nettoie le groupe
        même quand le noyau a tué le processus. Deux vocabulaires pour un geste
        dérivent — ce dépôt l'a déjà payé quatre fois.
        """
        source = (Path(__file__).parent.parent / "src" / "coding_engine" / "execution.py").read_text(
            encoding="utf-8"
        )
        assert "from src.sandbox.runner import" in source
        assert "subprocess.Popen" not in source


# ======================================================================
# 7. Normalisation du résultat
# ======================================================================

class TestNormalisation:
    """Tous les moteurs rendent la même forme, et aucune forme n'est inventée."""

    def test_un_resultat_se_serialise_entierement(self):
        """L'API et l'audit lisent ce dictionnaire ; il ne doit rien perdre."""
        resultat = CodingTaskResult(
            status=CodingStatus.SUCCESS, engine_id="essai", task_id="t1",
            summary="fait", files_changed=[FileChange("a.py", "modified", 3, 1)],
            tests=RapportDeTests(command="pytest", passed=10, failed=0, exit_code=0),
            model=MODELE,
        )
        charge = resultat.to_dict()
        assert charge["ok"] is True
        assert charge["files_changed"][0]["insertions"] == 3
        assert charge["tests"]["ok"] is True
        assert charge["model"]["provider_id"] == "local"

    def test_aucun_test_n_est_invente(self):
        """« 0 test échoué » et « je ne sais pas » sont deux informations."""
        resultat = CodingTaskResult(
            status=CodingStatus.SUCCESS, engine_id="essai", task_id="t1"
        )
        assert resultat.to_dict()["tests"] is None

    def test_une_indisponibilite_porte_son_motif(self):
        """Un moteur absent n'est jamais un succès vide."""
        resultat = CodingTaskResult.unavailable("aider", "t1", "aider n'est pas installé")
        assert resultat.ok is False
        assert resultat.errors == ["aider n'est pas installé"]

    def test_seul_success_vaut_ok(self):
        """Une attente d'approbation n'est pas une réussite."""
        for statut in CodingStatus:
            resultat = CodingTaskResult(status=statut, engine_id="e", task_id="t")
            assert resultat.ok is (statut is CodingStatus.SUCCESS)

    def test_la_tache_se_serialise_sans_secret(self):
        """La tâche entre dans l'audit ; elle ne doit rien porter de sensible."""
        charge = CodingTask(instruction="fais x", workspace="/tmp/x").to_dict()
        assert set(charge) >= {"id", "instruction", "workspace", "timeout_seconds"}


class TestConstatDesChangements:
    """Ce que le moteur dit avoir fait et ce qu'il a fait sont deux choses."""

    def test_les_creations_et_suppressions_sont_vues(self, espace):
        """Le constat se fait sur le disque, pas sur la parole du moteur."""
        avant = snapshot(espace)
        (espace / "nouveau.py").write_text("y = 2\n", encoding="utf-8")
        (espace / "module.py").unlink()
        changements = {c.path: c.change_type for c in diff_snapshots(avant, snapshot(espace))}
        assert changements == {"nouveau.py": "created", "module.py": "deleted"}

    def test_une_modification_est_vue(self, espace):
        """Taille et date changent : c'est ce que le relevé compare."""
        avant = snapshot(espace)
        (espace / "module.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
        changements = diff_snapshots(avant, snapshot(espace))
        assert [(c.path, c.change_type) for c in changements] == [("module.py", "modified")]

    def test_les_dossiers_de_service_sont_ignores(self, espace):
        """`__pycache__` et `.git` noieraient les vrais changements."""
        (espace / "__pycache__").mkdir()
        (espace / "__pycache__" / "bruit.pyc").write_bytes(b"\x00")
        assert not any("__pycache__" in chemin for chemin in snapshot(espace))


# ----------------------------------------------------------------------
# Les racines déclarées (constat n°2, seconde moitié)
#
# `confine()` empêche de sortir de l'espace de travail. Il n'empêchait pas d'en
# choisir un mauvais : `resolve_workspace()` acceptait n'importe quel dossier
# existant de l'hôte, y compris celui que l'en-tête du module promet de
# protéger.
# ----------------------------------------------------------------------


class TestRacinesDeclarees:
    """Où un moteur de codage a le droit de travailler, et qui le décide."""

    def _espace(self, racine, nom="projet"):
        espace = racine / nom
        espace.mkdir(parents=True)
        return espace

    def test_sans_declaration_rien_n_est_acceptable(self, monkeypatch, tmp_path):
        """Le cœur du constat : une variable absente n'est pas « tout l'hôte »."""
        monkeypatch.delenv("GALSEN_CODING_WORKSPACE_ROOTS", raising=False)
        espace = self._espace(tmp_path)
        with pytest.raises(WorkspaceError) as erreur:
            resolve_workspace(espace)
        assert "GALSEN_CODING_WORKSPACE_ROOTS" in str(erreur.value)

    def test_le_refus_dit_ce_qu_une_absence_ne_veut_pas_dire(
        self, monkeypatch, tmp_path,
    ):
        """Un exploitant doit lire pourquoi, pas seulement que."""
        monkeypatch.delenv("GALSEN_CODING_WORKSPACE_ROOTS", raising=False)
        espace = self._espace(tmp_path)
        with pytest.raises(WorkspaceError) as erreur:
            resolve_workspace(espace)
        assert "tout l'hôte" in str(erreur.value)

    def test_un_espace_sous_une_racine_declaree_passe(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GALSEN_CODING_WORKSPACE_ROOTS", str(tmp_path))
        espace = self._espace(tmp_path, "a/b/c")
        assert resolve_workspace(espace) == espace.resolve()

    def test_la_racine_elle_meme_est_un_espace_valide(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GALSEN_CODING_WORKSPACE_ROOTS", str(tmp_path))
        assert resolve_workspace(tmp_path) == tmp_path.resolve()

    def test_un_dossier_voisin_est_refuse(self, monkeypatch, tmp_path):
        """Le voisin d'une racine n'est pas dedans, et « dedans » est la règle."""
        autorise = tmp_path / "autorise"
        autorise.mkdir()
        interdit = tmp_path / "interdit"
        interdit.mkdir()
        monkeypatch.setenv("GALSEN_CODING_WORKSPACE_ROOTS", str(autorise))
        with pytest.raises(WorkspaceError) as erreur:
            resolve_workspace(interdit)
        assert "aucune racine déclarée" in str(erreur.value)

    def test_un_prefixe_commun_ne_suffit_pas(self, monkeypatch, tmp_path):
        """
        `/data/projet` ne contient pas `/data/projet-secret`.

        Une comparaison de chaînes aurait dit oui. La borne compare des
        composants de chemin, pas des préfixes.
        """
        racine = tmp_path / "projet"
        racine.mkdir()
        voisin = tmp_path / "projet-secret"
        voisin.mkdir()
        monkeypatch.setenv("GALSEN_CODING_WORKSPACE_ROOTS", str(racine))
        with pytest.raises(WorkspaceError):
            resolve_workspace(voisin)

    def test_un_lien_symbolique_qui_sort_est_refuse(self, monkeypatch, tmp_path):
        """
        Le chemin est résolu avant d'être confronté aux racines.

        Sans cela, un lien posé dans une racine autorisée désignerait n'importe
        quoi ailleurs, et la borne ne servirait à rien.
        """
        autorise = tmp_path / "autorise"
        autorise.mkdir()
        dehors = tmp_path / "dehors"
        dehors.mkdir()
        (autorise / "raccourci").symlink_to(dehors, target_is_directory=True)
        monkeypatch.setenv("GALSEN_CODING_WORKSPACE_ROOTS", str(autorise))
        with pytest.raises(WorkspaceError):
            resolve_workspace(autorise / "raccourci")

    def test_plusieurs_racines_se_declarent_comme_un_PATH(self, monkeypatch, tmp_path):
        premiere = tmp_path / "un"
        premiere.mkdir()
        seconde = tmp_path / "deux"
        seconde.mkdir()
        monkeypatch.setenv(
            "GALSEN_CODING_WORKSPACE_ROOTS",
            f"{premiere}{os.pathsep}{seconde}",
        )
        assert resolve_workspace(seconde) == seconde.resolve()

    def test_une_racine_fautive_est_nommee_et_non_avalee(self, monkeypatch, tmp_path):
        """
        Une faute de frappe qui rétrécit la politique doit se voir.

        Écarter l'entrée en silence produit un refus inexplicable trois
        semaines plus tard.
        """
        monkeypatch.setenv(
            "GALSEN_CODING_WORKSPACE_ROOTS", str(tmp_path / "n-existe-pas"),
        )
        racines, ecartees = declared_roots()
        assert racines == []
        assert any("n-existe-pas" in entree for entree in ecartees)

    def test_une_racine_fautive_n_annule_pas_les_bonnes(self, monkeypatch, tmp_path):
        bonne = tmp_path / "bonne"
        bonne.mkdir()
        monkeypatch.setenv(
            "GALSEN_CODING_WORKSPACE_ROOTS",
            f"{tmp_path / 'absente'}{os.pathsep}{bonne}",
        )
        assert resolve_workspace(bonne) == bonne.resolve()

    def test_la_declaration_est_relue_a_chaque_appel(self, monkeypatch, tmp_path):
        """
        Une politique figée à l'import ne se corrige plus sans redémarrage.

        C'est le même choix que `container_required()`, et pour la même raison.
        """
        espace = self._espace(tmp_path)
        monkeypatch.setenv("GALSEN_CODING_WORKSPACE_ROOTS", str(tmp_path))
        assert resolve_workspace(espace)
        monkeypatch.setenv("GALSEN_CODING_WORKSPACE_ROOTS", str(tmp_path / "ailleurs"))
        with pytest.raises(WorkspaceError):
            resolve_workspace(espace)

    def test_l_inexistence_est_signalee_avant_la_declaration(
        self, monkeypatch, tmp_path,
    ):
        """
        Une faute de frappe se répare mieux que « hors des racines ».

        Le contrôle d'accès a déjà eu lieu plus haut ; ici, la question est
        diagnostique.
        """
        monkeypatch.delenv("GALSEN_CODING_WORKSPACE_ROOTS", raising=False)
        with pytest.raises(WorkspaceError) as erreur:
            resolve_workspace(tmp_path / "absent")
        assert "n'existe pas" in str(erreur.value)

    def test_le_moteur_refuse_la_tache_et_ne_la_route_pas(self, monkeypatch, tmp_path):
        """
        Le refus arrive dans les préalables, avant tout choix de moteur.

        Un espace hors racines ne doit pas être signalé comme une panne de
        moteur : ce n'est pas le moteur qui manque.
        """
        monkeypatch.delenv("GALSEN_CODING_WORKSPACE_ROOTS", raising=False)
        espace = self._espace(tmp_path)
        gestionnaire = CodingEngineManager()
        resultat = gestionnaire.execute(
            CodingTask(instruction="corrige", workspace=str(espace))
        )
        assert resultat.status is CodingStatus.FAILURE
        assert "GALSEN_CODING_WORKSPACE_ROOTS" in resultat.summary
