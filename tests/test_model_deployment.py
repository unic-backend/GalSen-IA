"""
Le modèle local visé, les préférences de rôle, et l'infrastructure serveur.

Ce fichier éprouve trois choses que la phase 3 a ajoutées, et une quatrième qui
compte autant : **que rien ne prétende avoir tourné.** Aucun modèle n'a été
téléchargé sur cette machine, aucun n'a été chargé, aucun n'a répondu. Les tests
ci-dessous vérifient donc surtout des **refus** — c'est la forme que prend
l'honnêteté quand le matériel manque.
"""

import glob
import os
import subprocess
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model_engine.benchmark import (  # noqa: E402
    EXECUTE,
    NON_EXECUTE,
    REAL,
    SCRIPTED,
    TACHES,
    BancRefuse,
    RapportBanc,
    ResultatTache,
    comparer,
    executer,
)
from src.model_engine.local_catalogue import CatalogueLocal  # noqa: E402
from src.model_engine.provider_selector import ProviderSelector  # noqa: E402
from src.model_engine.providers.base import (  # noqa: E402
    ProviderInfo,
    ProviderStatus,
    UnavailabilityReason,
)
from src.model_engine.providers.local_provider import LocalProvider  # noqa: E402
from src.model_engine.providers.provider_registry import ProviderRegistry  # noqa: E402

#: Le parc que la mission décrit : le nouveau modèle, la ligne de base
#: conservée, et de quoi éprouver les autres rôles.
PARC = [
    "qwen3.5:9b", "qwen2.5:14b", "qwen2.5-coder:14b",
    "deepseek-r1:8b", "llava:7b", "qwen2.5:3b",
]


@pytest.fixture
def selecteur():
    """Un sélecteur servi par un parc local figé."""
    fournisseur = LocalProvider()
    descripteurs = [fournisseur._build_descriptor(n, 8192, 4096) for n in PARC]

    class FournisseurFige(LocalProvider):
        """Un fournisseur dont le parc ne dépend d'aucun serveur."""

        def list_models(self):
            return descripteurs

        def check_availability(self):
            return ProviderInfo(
                provider_id="local", display_name="Local (Ollama)",
                status=ProviderStatus.READY, model_count=len(descripteurs),
                requires_credentials=False,
            )

    registre = ProviderRegistry(register_defaults=False)
    registre.register(FournisseurFige())
    return ProviderSelector(provider_registry=registre)


class TestQwen35EstReconnu:
    """Le modèle local visé par la mission, et le piège de son nom."""

    def test_qwen3_5_porte_son_contexte_long(self):
        """
        262 144 jetons, `OBSERVED` : c'est la première fois qu'un modèle local
        dépasse le seuil de `document_analysis` (100 000).
        """
        profil = CatalogueLocal().profil("qwen3.5:9b")
        assert profil.context_window == 262144
        assert "long_context" in profil.features

    def test_qwen3_5_n_est_pas_avale_par_le_motif_generaliste(self):
        """
        « qwen3.5 » contient « qwen3 ». Sans priorité à l'ordre du fichier, le
        modèle hériterait du profil généraliste et de ses 32 768 jetons.
        """
        assert CatalogueLocal().profil("qwen3.5:9b").context_window != 32768

    def test_la_vision_n_est_pas_declaree_depuis_une_recherche(self):
        """
        La multimodalité de Qwen3.5 est annoncée par des sources secondaires.
        La déclarer ici enverrait des images à un modèle qui ne les lit
        peut-être pas ; `/api/show` tranchera sur la machine de l'exploitant.
        """
        assert CatalogueLocal().profil("qwen3.5:9b").supports_vision is None

    def test_la_ligne_de_base_reste_reconnue(self):
        """`qwen2.5:14b` n'est pas supprimé : la mission demande de le garder."""
        profil = CatalogueLocal().profil("qwen2.5:14b")
        assert "reasoning" in profil.features


class TestLesPreferencesDeRole:
    """
    Ce qui départage des modèles également capables.

    Mesuré : une tâche `reasoning` trouve trois modèles portant l'atout
    `reasoning`. Tous gratuits, donc le coût ne tranche pas — le choix retombait
    sur l'ordre d'installation.
    """

    @pytest.mark.parametrize(
        "role, attendu",
        [
            ("reasoning", "deepseek-r1:8b"),
            ("planning", "deepseek-r1:8b"),
            ("security", "deepseek-r1:8b"),
            ("document_analysis", "qwen3.5:9b"),
            ("summarization", "qwen3.5:9b"),
            ("research", "qwen3.5:9b"),
            ("implementation", "qwen2.5-coder:14b"),
            ("conversation", "qwen2.5:3b"),
            ("vision", "llava:7b"),
        ],
    )
    def test_chaque_role_atteint_le_modele_prefere(self, selecteur, role, attendu):
        selection = selecteur.select({"task_type": role})
        assert selection.descriptor is not None, f"« {role} » ne route vers rien"
        assert selection.descriptor.model_name == attendu

    def test_une_preference_ne_remonte_pas_un_modele_moins_capable(self, selecteur):
        """
        La préférence n'agit **qu'à égalité**. Un modèle nommé pour un rôle mais
        dépourvu de l'atout attendu ne gagne rien — sinon la préférence
        deviendrait un routage en dur, ce que le fichier existe pour éviter.
        """
        # `code_generation` préfère « coder » ; seul le modèle de code porte
        # l'atout, donc il gagne — mais pour la compétence, pas la préférence.
        selection = selecteur.select({"task_type": "code_generation"})
        assert "code_generation" in selection.descriptor.special_features

    def test_un_role_sans_preference_garde_le_comportement_precedent(self, selecteur):
        """Aucune préférence déclarée pour `code_review` au-delà du code."""
        assert selecteur.select({"task_type": "code_review"}).descriptor is not None


class TestLesConfigurationsDeDeploiement:
    """
    Les grands modèles préparés. Aucun n'est téléchargé, et chaque fichier doit
    le dire — un fichier de configuration qui n'annonce pas son état se lit
    comme une installation.
    """

    @staticmethod
    def _configurations():
        racine = os.path.join(os.path.dirname(__file__), "..", "config", "models")
        for chemin in sorted(glob.glob(os.path.join(racine, "*.yaml"))):
            with open(chemin, encoding="utf-8") as fichier:
                yield os.path.basename(chemin), yaml.safe_load(fichier)

    def test_il_y_a_des_configurations(self):
        assert list(self._configurations()), "aucun grand modèle préparé"

    def test_chacune_declare_qu_elle_n_est_pas_telechargee(self):
        for nom, configuration in self._configurations():
            assert "NOT DOWNLOADED" in configuration["state"], (
                f"{nom} ne dit pas qu'aucun poids n'a été récupéré"
            )

    def test_aucune_ne_pretend_tourner_sur_douze_giga(self):
        """
        Le refus qui protège l'exploitant d'une heure perdue : ces modèles ne
        tiennent pas sur la carte de développement, et ce n'est pas une question
        de patience.
        """
        for nom, configuration in self._configurations():
            assert configuration["hardware"]["runs_on_12gb_vram"] is False, nom

    def test_chacune_porte_une_commande_de_service(self):
        for nom, configuration in self._configurations():
            commande = configuration.get("serve_command")
            assert commande and commande[0] in ("vllm", "docker"), nom

    def test_chacune_nomme_les_roles_qu_elle_servira(self):
        for nom, configuration in self._configurations():
            assert configuration.get("roles"), f"{nom} ne dit pas à quoi il servira"


class TestLesScriptsSontHonnetes:
    """
    Chaque script doit **échouer proprement** ici, avec le motif. C'est la seule
    sortie honnête sur une machine sans GPU et sans serveur.
    """

    @staticmethod
    def _lancer(*arguments):
        racine = os.path.join(os.path.dirname(__file__), "..")
        return subprocess.run(
            [sys.executable, *arguments], cwd=racine, capture_output=True,
            text=True, timeout=120,
        )

    def test_le_preflight_dit_que_le_serveur_manque(self):
        sortie = self._lancer("scripts/models/preflight.py")
        assert sortie.returncode == 1
        assert "INJOIGNABLE" in sortie.stdout
        assert "ollama serve" in sortie.stdout

    def test_le_preflight_n_invente_aucun_modele(self):
        """
        `LocalProvider` possède un catalogue de repli. L'afficher serveur éteint
        donnerait l'illusion d'une installation.
        """
        sortie = self._lancer("scripts/models/preflight.py")
        assert "llama3" not in sortie.stdout and "mistral" not in sortie.stdout

    def test_serve_large_liste_les_modeles_sans_rien_lancer(self):
        sortie = self._lancer("scripts/models/serve_large.py")
        assert sortie.returncode == 0
        assert "kimi-k2.5" in sortie.stdout
        assert "NOT DOWNLOADED" in sortie.stdout

    def test_serve_large_refuse_de_lancer_sans_gpu(self):
        sortie = self._lancer("scripts/models/serve_large.py", "kimi-k2.5", "--execute")
        assert sortie.returncode == 1
        assert "refusé" in sortie.stdout.lower()

    def test_connect_dit_qu_aucun_serveur_n_est_configure(self, monkeypatch):
        sortie = self._lancer("scripts/models/connect.py")
        assert sortie.returncode == 1
        assert "NON CONFIGURÉ" in sortie.stdout or "INJOIGNABLE" in sortie.stdout

    def test_le_banc_ne_rend_aucun_chiffre_sans_modele(self):
        """
        La sortie la plus importante de toute la phase : sans modèle, **aucun
        taux**. Un banc qui rend `0.0` quand rien n'a tourné est pire qu'un banc
        absent — son chiffre se compare.
        """
        sortie = self._lancer(
            "scripts/models/bench.py", "--modele", "qwen3.5:9b", "--contre", "qwen2.5:14b",
        )
        assert sortie.returncode == 1
        assert "NON EXÉCUTÉ" in sortie.stdout
        assert "Comparaison refusée" in sortie.stdout


class TestLeBancDeModeles:
    """Le harnais lui-même, éprouvé sans modèle."""

    class FournisseurAbsent(LocalProvider):
        """Un fournisseur qui ne répond jamais."""

        def check_availability(self):
            return ProviderInfo(
                provider_id="local", display_name="Local", status=ProviderStatus.UNAVAILABLE,
                model_count=0, requires_credentials=False,
                reason=UnavailabilityReason.UNREACHABLE, detail="Aucun serveur",
            )

    def test_sans_fournisseur_le_rapport_est_non_execute(self):
        rapport = executer(self.FournisseurAbsent(), "qwen3.5:9b")
        assert rapport.status == NON_EXECUTE
        assert rapport.raison
        assert rapport.resultats == []

    def test_un_taux_sur_zero_execution_n_est_pas_nul(self):
        """`None`, jamais `0.0` : un chiffre nul se compare, une absence non."""
        assert executer(self.FournisseurAbsent(), "qwen3.5:9b").taux is None

    def test_le_banc_couvre_les_categories_annoncees(self):
        categories = {t.categorie for t in TACHES}
        for attendue in ("math", "reasoning", "coding", "french",
                         "instruction", "hallucination", "long_context"):
            assert attendue in categories

    def test_les_controles_sont_deterministes(self):
        """
        Deux passages sur le même texte donnent le même verdict. Un jury-modèle
        n'offrirait pas cette garantie, et jugerait avec la même faiblesse que
        ce qu'il juge.
        """
        tache = next(t for t in TACHES if t.identifiant == "math-01")
        assert tache.controle("Le résultat est 391.") is True
        assert tache.controle("Le résultat est 391.") is True
        assert tache.controle("Le résultat est 390.") is False


class TestLaComparaisonRefuseDeMelanger:
    """
    La règle qui structure le module : un chiffre simulé et un chiffre réel ne
    se comparent jamais.
    """

    @staticmethod
    def _rapport(mode: str, modele: str, reussites: int, total: int = 4) -> RapportBanc:
        rapport = RapportBanc(mode=mode, modele=modele, status=EXECUTE)
        for i in range(total):
            rapport.resultats.append(ResultatTache(
                identifiant=f"t{i}", categorie="math",
                reussi=i < reussites, latence_secondes=0.1,
            ))
        return rapport

    def test_deux_modes_differents_sont_refuses(self):
        with pytest.raises(BancRefuse, match="Modes différents"):
            comparer(self._rapport(SCRIPTED, "faux", 4), self._rapport(REAL, "vrai", 4))

    def test_un_rapport_non_execute_est_refuse(self):
        absent = RapportBanc(mode=REAL, modele="absent", status=NON_EXECUTE,
                             raison="aucun serveur")
        with pytest.raises(BancRefuse, match="n'a pas été exécuté"):
            comparer(absent, self._rapport(REAL, "present", 4))

    def test_des_taches_differentes_sont_refusees(self):
        gauche = self._rapport(REAL, "a", 2, total=4)
        droite = self._rapport(REAL, "b", 2, total=3)
        with pytest.raises(BancRefuse, match="mêmes tâches"):
            comparer(gauche, droite)

    def test_un_ecart_d_une_tache_est_du_bruit_pas_une_victoire(self):
        """
        Le garde-fou contre « le plus récent est meilleur ». Une tâche sur douze
        n'est pas un écart, et le présenter comme une victoire est exactement ce
        que la mission interdit.
        """
        gauche = self._rapport(REAL, "qwen2.5:14b", 8, total=12)
        droite = self._rapport(REAL, "qwen3.5:9b", 9, total=12)
        assert "ÉGALITÉ" in comparer(gauche, droite)["verdict"]

    def test_un_ecart_net_nomme_le_gagnant(self):
        gauche = self._rapport(REAL, "ancien", 4, total=12)
        droite = self._rapport(REAL, "nouveau", 11, total=12)
        assert "nouveau l'emporte" in comparer(gauche, droite)["verdict"]

    def test_le_rapport_porte_de_quoi_se_comparer_plus_tard(self):
        """
        Deux scores obtenus avec des quantisations ou des fenêtres différentes
        ne se comparent pas, et sans ces champs rien ne le signalerait.
        """
        charge = self._rapport(REAL, "m", 2).to_dict()
        for champ in ("mode", "model", "backend", "quantization", "context_window",
                      "temperature", "hardware", "pass_rate", "errors"):
            assert champ in charge
