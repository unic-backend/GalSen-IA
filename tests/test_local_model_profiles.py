"""
Ce qu'un modèle local sait faire, et d'où on le sait.

## Le défaut mesuré le 2026-08-24

`LocalProvider` construisait **le même descripteur pour tous les modèles** : pas
de vision, pas d'outils, 8192 jetons, et trois atouts (`local`, `no_cost`,
`offline`) absents du vocabulaire de routage. La couche de sélection existait et
comparait des descripteurs identiques : sur cinq modèles spécialisés,
`conversation`, `reasoning` et `code_generation` retournaient tous **le premier
de la liste**, et `vision`, `summarization`, `document_analysis` ne retournaient
rien.

Ces tests éprouvent les deux moitiés du correctif : le profil (ce que le modèle
sait faire) et le routage (qui est retenu pour quelle tâche). La seconde est la
seule qui compte pour un utilisateur — un profil juste qui ne change aucun choix
n'aurait rien réparé.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model_engine.local_catalogue import (  # noqa: E402
    DECLARE,
    DEFAUT,
    MESURE,
    CatalogueLocal,
    ProfilLocal,
    profil_mesure,
)
from src.model_engine.provider_selector import ProviderSelector  # noqa: E402
from src.model_engine.providers.base import (  # noqa: E402
    ProviderInfo,
    ProviderStatus,
    UnavailabilityReason,
)
from src.model_engine.providers.local_provider import LocalProvider  # noqa: E402
from src.model_engine.providers.provider_registry import ProviderRegistry  # noqa: E402

#: Un parc local réaliste : un modèle de code, un de raisonnement, un de vision,
#: un petit rapide, un à long contexte.
PARC = ["qwen2.5-coder:14b", "deepseek-r1:14b", "llava:13b", "phi3:mini", "llama3.1:8b"]


@pytest.fixture
def selecteur():
    """Un sélecteur servi par un fournisseur local au parc figé."""
    fournisseur = LocalProvider()
    descripteurs = [fournisseur._build_descriptor(n, 8192, 4096) for n in PARC]

    class FournisseurFige(LocalProvider):
        """Un fournisseur local dont le parc ne dépend d'aucun serveur."""

        def list_models(self):
            return descripteurs

        def check_availability(self):
            return ProviderInfo(
                provider_id="local",
                display_name="Local (Ollama)",
                status=ProviderStatus.READY,
                model_count=len(descripteurs),
                requires_credentials=False,
            )

    registre = ProviderRegistry(register_defaults=False)
    registre.register(FournisseurFige())
    return ProviderSelector(provider_registry=registre)


class TestLeProfilDeclare:
    """Ce que `config/model_routing.yaml` dit d'un modèle."""

    @pytest.mark.parametrize(
        "nom, atout_attendu",
        [
            ("qwen2.5-coder:14b", "code_generation"),
            ("deepseek-r1:14b", "reasoning"),
            ("phi3:mini", "fast_response"),
            ("llama3.1:8b", "long_context"),
        ],
    )
    def test_chaque_famille_porte_son_atout(self, nom, atout_attendu):
        assert atout_attendu in CatalogueLocal().profil(nom).features

    def test_un_modele_de_vision_est_reconnu_comme_tel(self):
        """C'est le cas qui rendait `llava` introuvable pour une tâche `vision`."""
        assert CatalogueLocal().profil("llava:13b").supports_vision is True

    def test_le_motif_le_plus_specifique_gagne(self):
        """
        « qwen2.5-coder » contient « qwen2.5 ». Sans priorité à l'ordre du
        fichier, le modèle de code hériterait du profil généraliste.
        """
        profil = CatalogueLocal().profil("qwen2.5-coder:14b")
        assert profil.features == ["code_generation"]

    def test_un_modele_inconnu_ne_recoit_aucune_capacite_inventee(self):
        """
        Un profil vide est une **absence de connaissance**, pas une absence de
        capacités. Rien ne doit être supposé d'un modèle jamais déclaré.
        """
        profil = CatalogueLocal().profil("un-modele-que-personne-na-declare:7b")
        assert profil.features == []
        assert profil.supports_vision is None
        assert profil.context_window is None


class TestCeQueLaMesureDit:
    """
    La traduction d'une réponse `/api/show`.

    Forme vérifiée sur la documentation officielle d'Ollama
    (`ollama/ollama`, `docs/api.md`) : la réponse porte un tableau
    `capabilities` et un objet `model_info` dont une clé se termine par
    `.context_length`, préfixée par l'architecture.
    """

    def test_la_vision_annoncee_est_mesuree(self):
        profil = profil_mesure({"capabilities": ["completion", "vision"]})
        assert profil.supports_vision is True
        assert profil.origines["supports_vision"] == MESURE

    def test_une_capacite_absente_du_tableau_est_un_non_mesure(self):
        """
        Le tableau est la liste **complète** de ce que le serveur reconnaît :
        l'absence de `vision` y est une mesure négative, pas une ignorance.
        """
        profil = profil_mesure({"capabilities": ["completion", "tools"]})
        assert profil.supports_vision is False
        assert profil.supports_tools is True

    def test_sans_tableau_de_capacites_rien_n_est_suppose(self):
        """
        Un serveur plus ancien ne renvoie pas `capabilities`. Répondre `False`
        à sa place inventerait une mesure qui n'a pas eu lieu.
        """
        profil = profil_mesure({"model_info": {"llama.context_length": 8192}})
        assert profil.supports_vision is None
        assert profil.supports_tools is None

    @pytest.mark.parametrize(
        "cle", ["llama.context_length", "qwen2.context_length", "gemma3.context_length"]
    )
    def test_la_cle_de_contexte_est_cherchee_et_non_devinee(self, cle):
        """Le préfixe dépend de l'architecture : le deviner échouerait ailleurs."""
        profil = profil_mesure({"model_info": {cle: 131072}})
        assert profil.context_window == 131072
        assert profil.origines["context_window"] == MESURE

    def test_un_contexte_absurde_est_ignore(self):
        assert profil_mesure({"model_info": {"llama.context_length": 0}}).context_window is None


class TestLeDelaiDeGeneration:
    """
    Le délai, et ce que coûte de le régler trop court.

    Mesuré le 2026-08-24 sur une RTX A2000 12 Go, premier passage réel des dix
    épreuves : `qwen3.5:9b` a dépassé 120 s **deux fois sur dix**. Le coût n'a
    pas été la lenteur — le repli a envoyé une question d'arithmétique au modèle
    de code, qui a mal répondu. Un délai trop court fait changer de modèle en
    silence.
    """

    def test_le_defaut_laisse_un_modele_qui_raisonne_finir(self):
        """300 s : au-delà des deux dépassements mesurés, avec de la marge."""
        assert LocalProvider().GENERATION_TIMEOUT_SECONDS == 300

    def test_l_exploitant_peut_le_regler(self, monkeypatch):
        monkeypatch.setenv(LocalProvider.TIMEOUT_VARIABLE, "600")
        assert LocalProvider().GENERATION_TIMEOUT_SECONDS == 600

    @pytest.mark.parametrize("valeur", ["", "beaucoup", "0", "-30"])
    def test_une_valeur_inutilisable_retombe_sur_le_defaut(self, monkeypatch, valeur):
        """
        Et le journalise. Un délai mal écrit qui ferait basculer silencieusement
        vers un autre modèle serait découvert le jour où une réponse vient du
        mauvais — c'est-à-dire trop tard.
        """
        monkeypatch.setenv(LocalProvider.TIMEOUT_VARIABLE, valeur)
        assert LocalProvider().GENERATION_TIMEOUT_SECONDS == 300

    def test_le_delai_de_sonde_reste_court(self):
        """
        Sonder et générer sont deux choses. Allonger la sonde ferait attendre
        une seconde entière par tour pour découvrir qu'aucun serveur n'écoute.
        """
        assert LocalProvider.PROBE_TIMEOUT_SECONDS <= 2.0


class TestLaPrioriteDesOrigines:
    """Mesure > déclaration > défaut, et le descripteur dit laquelle a servi."""

    def test_une_mesure_ecrase_une_declaration(self):
        descripteur = LocalProvider()._build_descriptor(
            "qwen2.5-coder:14b", 8192, 4096,
            mesure=profil_mesure({"model_info": {"qwen2.context_length": 131072}}),
        )
        assert descripteur.context_window == 131072
        assert descripteur.capability_sources["context_window"] == MESURE

    def test_une_mesure_muette_n_efface_pas_la_declaration(self):
        """
        Une mesure qui ne dit rien de la vision ne doit pas effacer ce que la
        configuration en disait. « Non mesuré » n'est pas « mesuré faux ».
        """
        descripteur = LocalProvider()._build_descriptor(
            "llava:13b", 8192, 4096,
            mesure=profil_mesure({"model_info": {"llama.context_length": 4096}}),
        )
        assert descripteur.supports_vision is True
        assert descripteur.capability_sources["supports_vision"] == DECLARE

    def test_un_modele_inconnu_garde_le_contexte_par_defaut_et_le_dit(self):
        descripteur = LocalProvider()._build_descriptor("inconnu:7b", 8192, 4096)
        assert descripteur.context_window == 8192
        assert descripteur.capability_sources["context_window"] == DEFAUT

    def test_le_mode_de_service_reste_annonce(self):
        """
        `local`, `no_cost` et `offline` décrivent le mode de service et sont lus
        ailleurs : les remplacer par les atouts casserait ces lecteurs.
        """
        atouts = LocalProvider()._build_descriptor("phi3:mini", 8192, 4096).special_features
        assert atouts[:3] == ["local", "no_cost", "offline"]
        assert "fast_response" in atouts

    def test_un_profil_fusionne_ne_modifie_aucun_des_deux(self):
        faible = ProfilLocal(context_window=8192, origines={"context_window": DEFAUT})
        fort = ProfilLocal(context_window=32768, origines={"context_window": MESURE})
        faible.fusionner(fort)
        assert faible.context_window == 8192
        assert fort.context_window == 32768


class TestLeRoutageChoisitVraiment:
    """
    La moitié qui compte. Chaque cas ci-dessous retournait, avant le correctif,
    soit `qwen2.5-coder:14b` — le premier de la liste — soit rien du tout.
    """

    @pytest.mark.parametrize(
        "tache, attendu",
        [
            ("conversation", "phi3:mini"),
            ("translation", "phi3:mini"),
            ("code_generation", "qwen2.5-coder:14b"),
            ("code_review", "qwen2.5-coder:14b"),
            ("reasoning", "deepseek-r1:14b"),
            ("planning", "deepseek-r1:14b"),
            ("analysis", "deepseek-r1:14b"),
            ("vision", "llava:13b"),
            ("document_analysis", "llama3.1:8b"),
            ("summarization", "llama3.1:8b"),
        ],
    )
    def test_chaque_tache_va_au_modele_qui_lui_correspond(self, selecteur, tache, attendu):
        selection = selecteur.select({"task_type": tache})
        assert selection.descriptor is not None, f"« {tache} » ne route vers rien"
        assert selection.descriptor.model_name == attendu

    def test_les_taches_ne_convergent_pas_vers_un_seul_modele(self, selecteur, ):
        """
        Le symptôme d'origine, éprouvé directement : dix tâches, un seul modèle.
        Un correctif qui rétablirait deux modèles sur dix passerait les cas
        ci-dessus un par un sans réparer le problème.
        """
        taches = ["conversation", "code_generation", "reasoning", "vision",
                  "document_analysis", "translation", "analysis", "planning"]
        retenus = {selecteur.select({"task_type": t}).descriptor.model_name for t in taches}
        assert len(retenus) >= 4, f"le routage converge encore : {retenus}"

    def test_une_complexite_non_annoncee_n_impose_aucun_plancher(self, selecteur):
        """
        Une complexité absente était traitée comme `medium`, donc 8192 jetons
        exigés — le plancher qui écartait le seul modèle de vision servi. Une
        complexité inconnue ne doit rien exiger.
        """
        assert selecteur.select({"task_type": "vision"}).descriptor is not None

    def test_une_complexite_annoncee_releve_toujours_le_plancher(self, selecteur):
        """
        Le correctif ne doit pas désarmer la complexité quand elle est dite :
        `very_high` exige 100 000 jetons, et seul le modèle à long contexte
        les offre.
        """
        selection = selecteur.select({"task_type": "conversation", "complexity": "very_high"})
        assert selection.descriptor.model_name == "llama3.1:8b"

    def test_une_vision_exigee_explicitement_est_respectee(self, selecteur):
        selection = selecteur.select({"task_type": "conversation", "requires_vision": True})
        assert selection.descriptor.model_name == "llava:13b"


@pytest.fixture
def gestionnaire():
    """Un `ModelManagerImpl` servi par le même parc local figé."""
    from src.model_engine.model_manager import ModelManagerImpl

    fournisseur = LocalProvider()
    descripteurs = [fournisseur._build_descriptor(n, 8192, 4096) for n in PARC]

    class FournisseurFige(LocalProvider):
        """Un fournisseur local dont le parc ne dépend d'aucun serveur."""

        def list_models(self):
            return descripteurs

        def check_availability(self):
            return ProviderInfo(
                provider_id="local",
                display_name="Local (Ollama)",
                status=ProviderStatus.READY,
                model_count=len(descripteurs),
                requires_credentials=False,
            )

    registre = ProviderRegistry(register_defaults=False)
    registre.register(FournisseurFige())
    return ModelManagerImpl(provider_registry=registre)


class TestLaGenerationEmprunteLeRoutage:
    """
    Le point d'intégration, et le seul qui atteigne un utilisateur.

    Tout le travail de sélection vivait dans `ProviderSelector`. Le chemin de
    génération — `generate_text_with_fallback`, celui que le chat appelle —
    ne l'appelait pas : il essayait les modèles du catalogue **dans l'ordre du
    fournisseur** et gardait le premier qui répondait. Un profil juste qui ne
    change aucun choix n'aurait rien réparé.
    """

    @pytest.mark.parametrize(
        "tache, attendu",
        [
            ("conversation", "phi3:mini"),
            ("code_generation", "qwen2.5-coder:14b"),
            ("reasoning", "deepseek-r1:14b"),
            ("vision", "llava:13b"),
            ("document_analysis", "llama3.1:8b"),
        ],
    )
    def test_le_modele_essaye_en_premier_correspond_a_la_tache(
        self, gestionnaire, tache, attendu
    ):
        candidats = gestionnaire._fallback_candidates({"task_type": tache})
        assert candidats[0].name == attendu

    def test_le_repli_garde_toute_sa_portee(self, gestionnaire):
        """
        Le tri **réordonne**, il n'élague pas. Si le premier modèle ne répond
        pas, les quatre autres doivent rester essayables — sinon la correction
        aurait échangé un mauvais choix contre une panne.
        """
        candidats = gestionnaire._fallback_candidates({"task_type": "vision"})
        assert len(candidats) == len(PARC)
        assert {c.name for c in candidats} == set(PARC)

    def test_sans_exigence_l_ordre_du_catalogue_est_conserve(self, gestionnaire):
        """Aucune tâche déclarée : rien à trier, et rien qui échoue."""
        candidats = gestionnaire._fallback_candidates({})
        assert [c.name for c in candidats] == PARC


class TestLesIntentionsDuPlannerSontRoutees:
    """
    Le chat transmet l'axe `task_type` du planner tel quel. Sept de ses huit
    intentions n'existaient pas dans la politique de routage : elles tombaient
    sur la règle par défaut — `general_conversation` et « le moins cher » — ce
    qui faisait écrire le code par le plus petit modèle installé.
    """

    @pytest.mark.parametrize(
        "intention, attendu",
        [
            ("conversation", "phi3:mini"),
            ("implementation", "qwen2.5-coder:14b"),
            ("quality", "qwen2.5-coder:14b"),
            ("research", "llama3.1:8b"),
            ("documentation", "llama3.1:8b"),
            ("security", "deepseek-r1:14b"),
        ],
    )
    def test_chaque_intention_atteint_un_modele_adapte(
        self, gestionnaire, intention, attendu
    ):
        assert gestionnaire._fallback_candidates(
            {"task_type": intention}
        )[0].name == attendu

    def test_aucune_intention_du_planner_n_est_orpheline(self):
        """
        Le test qui empêche la dérive : ajouter une intention au planner sans
        lui donner de règle de routage la ferait retomber en silence sur la
        règle par défaut. Un silence est exactement ce qui a caché ce défaut.
        """
        import re

        import yaml

        source = open("agents/planner/agent.py", encoding="utf-8").read()
        bloc = source.split("INTENT_RULES = {", 1)[1]
        intentions = re.findall(r'^\s{8}"([a-z_]+)":\s*\{', bloc, re.M)
        assert intentions, "les intentions du planner n'ont pas pu être lues"

        with open("config/model_routing.yaml", encoding="utf-8") as fichier:
            politique = yaml.safe_load(fichier)

        orphelines = [i for i in intentions if i not in politique["tasks"]]
        assert orphelines == [], (
            f"intentions sans règle de routage : {orphelines}. "
            "Ajoutez-les à `tasks:` dans config/model_routing.yaml."
        )


class TestLAutreCheminDeSelection:
    """
    `SimpleModelSelector`, emprunté quand des modèles sont **enregistrés**.

    Deux chemins mènent au même choix, et un seul avait été corrigé. Celui-ci
    classait par `_default_priorities` — une table qui ne connaît que GPT-4,
    Claude et Gemini, retirés par ADR-014. Tous les modèles locaux y valent 50 :
    le choix se faisait sur l'ordre de la liste, comme ailleurs.
    """

    @pytest.fixture
    def modeles(self):
        """Le même parc, au format que lit `SimpleModelSelector`."""
        from src.model_engine.model_registry import ModelRegistry

        fournisseur = LocalProvider()
        catalogue = ModelRegistry(ProviderRegistry(register_defaults=False))
        return [
            catalogue.descriptor_to_model_item(
                fournisseur._build_descriptor(nom, 8192, 4096)
            )
            for nom in PARC
        ]

    @pytest.mark.parametrize(
        "tache, attendu",
        [
            ("conversation", "phi3:mini"),
            ("code_generation", "qwen2.5-coder:14b"),
            ("implementation", "qwen2.5-coder:14b"),
            ("reasoning", "deepseek-r1:14b"),
            ("document_analysis", "llama3.1:8b"),
            ("research", "llama3.1:8b"),
        ],
    )
    def test_les_deux_chemins_choisissent_pareil(self, modeles, tache, attendu):
        from src.model_engine.model_selector import SimpleModelSelector

        retenu = SimpleModelSelector().select_model(modeles, {"task_type": tache})
        assert retenu is not None and retenu.name == attendu

    def test_la_priorite_ne_decide_pas_a_la_place_de_la_tache(self, modeles):
        """
        Un modèle portant `reasoning` est `HIGH` par construction
        (`ModelRegistry._PRIORITY_BY_FEATURE`), et le classement final ajoute
        `priority * 10`. Sur une tâche de code, ces dix points faisaient gagner
        le modèle de raisonnement contre le modèle de code. La priorité doit
        départager les modèles **également adaptés**, pas trancher à leur place.
        """
        from src.model_engine.model_selector import SimpleModelSelector

        raisonneur = next(m for m in modeles if m.name == "deepseek-r1:14b")
        codeur = next(m for m in modeles if m.name == "qwen2.5-coder:14b")
        assert raisonneur.priority.value > codeur.priority.value, (
            "le préalable de ce test a disparu : le raisonneur n'est plus prioritaire"
        )

        retenu = SimpleModelSelector().select_model(modeles, {"task_type": "code_generation"})
        assert retenu.name == "qwen2.5-coder:14b"


class TestLeModeleQuiARepondEstNomme:
    """
    `_modele_utilise()` rendait `None` en disant, dans sa docstring, ce qui
    trancherait : *« que le moteur rende le modèle retenu avec le texte »*.
    `generate_text_with_source` le fait. Un nom deviné valait moins que pas de
    nom ; un nom **rendu par le moteur** vaut mieux que les deux.
    """

    @pytest.fixture
    def gestionnaire_qui_repond(self):
        """Un moteur dont un seul modèle répond — celui qui n'est pas premier."""
        from src.model_engine.model_manager import ModelManagerImpl
        from src.model_engine.providers.base import GenerationResponse

        fournisseur = LocalProvider()
        descripteurs = [fournisseur._build_descriptor(n, 8192, 4096) for n in PARC]

        class FournisseurPartiel(LocalProvider):
            """Seul `llama3.1:8b` répond ; les autres sont indisponibles."""

            def list_models(self):
                return descripteurs

            def check_availability(self):
                return ProviderInfo(
                    provider_id="local",
                    display_name="Local (Ollama)",
                    status=ProviderStatus.READY,
                    model_count=len(descripteurs),
                    requires_credentials=False,
                )

            def generate(self, request):
                if request.model_name != "llama3.1:8b":
                    return GenerationResponse.unavailable(
                        provider_id="local",
                        model_name=request.model_name,
                        reason=UnavailabilityReason.UNREACHABLE,
                        detail="Ce modèle ne répond pas",
                    )
                return GenerationResponse(
                    status=ProviderStatus.READY,
                    text="une réponse",
                    provider_id="local",
                    model_name=request.model_name,
                )

        registre = ProviderRegistry(register_defaults=False)
        registre.register(FournisseurPartiel())
        return ModelManagerImpl(provider_registry=registre)

    def test_le_moteur_nomme_le_modele_qui_a_abouti(self, gestionnaire_qui_repond):
        """
        Et pas le premier essayé. C'est le seul cas où la question est
        intéressante : `code_generation` vise le modèle de code, qui ne répond
        pas ici, donc le repli sert — et c'est le repli qu'il faut nommer.
        """
        from src.agent.context import executer_coroutine

        texte, modele = executer_coroutine(
            gestionnaire_qui_repond.generate_text_with_source(
                "peu importe", {"task_type": "code_generation"}
            )
        )
        assert texte == "une réponse"
        assert modele == "llama3.1:8b"

    def test_l_ancienne_methode_rend_toujours_le_meme_texte(self, gestionnaire_qui_repond):
        """
        `generate_text_with_fallback` délègue désormais. Son contrat — une
        chaîne — ne change pas : c'est ce qui permet à ses appelants existants
        de ne rien savoir de ce changement.
        """
        from src.agent.context import executer_coroutine

        assert executer_coroutine(
            gestionnaire_qui_repond.generate_text_with_fallback(
                "peu importe", {"task_type": "code_generation"}
            )
        ) == "une réponse"

    def test_le_chat_rend_le_nom_du_modele(self, gestionnaire_qui_repond):
        """Le bout de la chaîne : ce que `/chat` peut enfin dire à l'exploitant."""
        from src.chat.response import ContexteReponse, RedacteurConversation

        finale = RedacteurConversation(gestionnaire_qui_repond).rediger(
            ContexteReponse(message="Explique-moi les grandes lignes de Linux.")
        )
        assert finale.generated is True
        assert finale.model_used == "llama3.1:8b"
