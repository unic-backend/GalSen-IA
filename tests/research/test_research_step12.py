"""
Les cas de STEP 12 que les autres fichiers ne couvraient pas (R09.1).

STEP 12 nomme dix-huit cas. **Quatorze étaient déjà couverts** par les tests
écrits au fil des phases — la cartographie complète est dans
`docs/research/test-mapping.md`. Ce fichier écrit les quatre qui manquaient, et
un seul reste **non couvert**, pour une raison qui est dite plutôt que
contournée.

Les repli d'Agent-Reach et de web-search-mcp (cas 4 et 5) demandent qu'un
fournisseur soit disponible, ce qu'aucun n'est ici. Ils sont donc testés en
rendant un fournisseur disponible **explicitement**, ce qui est une simulation
assumée : ce n'est pas une mesure du fournisseur réel, et le nom du test le dit.
"""

import pytest

import src.research.providers as fournisseurs
import src.research.routing as routage
from src.research.providers import BLOQUE, DISPONIBLE, provider
from src.research.routing import (
    CHOISI,
    INCONNU,
    TOUS_BLOQUES,
    ResearchNeed,
    execute_with_fallback,
    route,
)


@pytest.fixture
def sante_forcee(monkeypatch):
    """
    Rend disponibles les fournisseurs nommés, sans rien installer.

    C'est une **simulation assumée** : elle mesure le comportement du routeur,
    jamais celui d'Agent-Reach ni de web-search-mcp, dont aucun n'a été exécuté.
    """
    def forcer(*disponibles: str):
        vrai_health = fournisseurs.health

        def faux_health(p):
            if p.provider_id in disponibles:
                return {"provider_id": p.provider_id, "state": DISPONIBLE,
                        "missing": [],
                        "trust_level": p.trust_level.value,
                        "commercially_cleared":
                            p.licence.usable_commercially}
            return vrai_health(p)

        monkeypatch.setattr(routage, "health", faux_health)
    return forcer


class TestCas04ReplD_AgentReach:
    """STEP 12 cas 4 — le repli vers Agent-Reach, et son état réel."""

    def test_agent_reach_ne_peut_pas_servir_ici(self):
        """L'état mesuré, avant toute simulation."""
        etat = fournisseurs.health(provider("agent_reach"))

        assert etat["state"] == BLOQUE
        assert etat["missing"]

    def test_ses_conditions_manquantes_sont_nommees(self):
        etat = fournisseurs.health(provider("agent_reach"))
        conditions = " ".join(m["condition"] for m in etat["missing"])

        assert "agent-reach" in conditions or "npm" in conditions

    def test_rendu_disponible_il_entre_dans_le_plan(self, sante_forcee):
        sante_forcee("agent_reach")

        decision = route(ResearchNeed("youtube_transcript"))

        assert decision["decision"] == CHOISI
        assert decision["provider_id"] == "agent_reach"

    def test_il_sert_de_repli_quand_le_premier_tombe(self, sante_forcee):
        sante_forcee("existing_galsen_research", "agent_reach")
        appels = []

        def premier_tombe(f):
            appels.append(f.provider_id)
            if f.provider_id == "existing_galsen_research":
                raise RuntimeError("panne")
            return "servi"

        resultat = execute_with_fallback(ResearchNeed("page_fetch"),
                                         premier_tombe)

        assert resultat["status"] == CHOISI
        assert resultat["served_by"] == "agent_reach"
        assert appels[0] == "existing_galsen_research"


class TestCas05ReplWebSearchMcp:
    """STEP 12 cas 5 — le repli vers web-search-mcp."""

    def test_web_search_mcp_ne_peut_pas_servir_ici(self):
        etat = fournisseurs.health(provider("web_search_mcp"))

        assert etat["state"] == BLOQUE

    def test_il_est_le_seul_a_servir_la_recherche_academique(self):
        decision = route(ResearchNeed("academic_search"))

        assert decision["decision"] == TOUS_BLOQUES
        assert [e["provider_id"] for e in decision["considered"]] == \
            ["web_search_mcp"]

    def test_rendu_disponible_il_sert_la_recherche_academique(self, sante_forcee):
        sante_forcee("web_search_mcp")

        decision = route(ResearchNeed("academic_search"))

        assert decision["decision"] == CHOISI
        assert decision["provider_id"] == "web_search_mcp"

    def test_il_sert_de_repli_apres_la_plateforme(self, sante_forcee):
        sante_forcee("existing_galsen_research", "web_search_mcp")

        def premier_tombe(f):
            if f.provider_id == "existing_galsen_research":
                raise RuntimeError("panne")
            return "servi"

        resultat = execute_with_fallback(ResearchNeed("web_search"),
                                         premier_tombe)

        assert resultat["served_by"] == "web_search_mcp"
        assert resultat["attempts"][0]["ok"] is False


class TestCas06CapaciteEnDouble:
    """STEP 12 cas 6 — une capacité servie par plusieurs fournisseurs."""

    def test_la_recherche_web_est_servie_trois_fois(self):
        servants = fournisseurs.providers_serving("web_search")

        assert len(servants) == 3

    def test_le_double_devient_un_repli_et_non_une_duplication(self, sante_forcee):
        """STEP 3 : ne pas installer deux fois la même capacité — mais le
        second sert de repli, ce qui n'est pas la même chose."""
        sante_forcee("existing_galsen_research", "web_search_mcp",
                     "agent_reach")

        plan = route(ResearchNeed("web_search"))["plan"]

        assert plan == ["existing_galsen_research", "web_search_mcp",
                        "agent_reach"]

    def test_une_capacite_unique_n_a_pas_de_repli(self, sante_forcee):
        sante_forcee("web_search_mcp")

        plan = route(ResearchNeed("wikipedia_search"))["plan"]

        assert plan == ["web_search_mcp"]

    def test_le_plan_ne_classe_pas_les_doublons(self, sante_forcee):
        """L'ordre est celui de la déclaration, pas un ordre de qualité."""
        sante_forcee("existing_galsen_research", "web_search_mcp")

        assert route(ResearchNeed("web_search"))["ordering"] == "declaration"


class TestCas13DelaiDAttente:
    """STEP 12 cas 13 — et la raison pour laquelle il n'est pas couvert."""

    def test_aucun_fournisseur_n_execute_donc_aucun_delai_ne_s_ecoule(self):
        """
        Rien dans cette couche n'exécute une requête : la recherche est
        **injectée**, et le délai d'attente appartient au client HTTP de
        l'appelant. Écrire un test qui minuterait une fonction factice
        mesurerait la fonction factice.

        Ce test épingle donc l'état réel plutôt qu'un délai inventé : les trois
        fournisseurs sont soit bloqués, soit servis par des outils dont le
        délai est déjà couvert ailleurs (`tests/test_browser_tool.py`).
        """
        etats = {f.provider_id: fournisseurs.health(f)["state"]
                 for f in fournisseurs.declared_providers()}

        assert etats["web_search_mcp"] == BLOQUE
        assert etats["agent_reach"] == BLOQUE

    def test_une_recherche_qui_leve_est_traitee_comme_un_echec(self):
        """Un délai dépassé arrive ici comme n'importe quelle exception."""
        def expire(_):
            raise TimeoutError("délai dépassé")

        resultat = execute_with_fallback(ResearchNeed("web_search"), expire)

        assert resultat["status"] == INCONNU
        assert "TimeoutError" in resultat["attempts"][0]["error"]
