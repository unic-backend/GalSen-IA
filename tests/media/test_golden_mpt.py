"""
The §38 golden tests that were not already covered (M08.2).

M08.1 mapped all twenty-two of §38's tests against existing coverage
(`docs/providers/golden-mapping.md`). Nineteen were already run by
`src/creative/golden.py`, `tests/media/test_moneyprinterturbo.py` or
`tests/creative/test_routing_mpt.py`. Writing them again would have inflated the
count without adding coverage, which is why the mapping came first.

Three were genuinely missing, and they are here:

- **MPT-06** — failure and fallback. The honest form: no second provider serves
  `stock_assembly`, so a failure yields `NO_PROVIDER` rather than a substitute.
  The test asserts the *refusal to substitute*, not a fallback that works.
- **MPT-07 / MPT-08** — the 9:16 and 16:9 workflows. Writing them found a real
  defect: the adapter declared 1920×1080, and since the bounds are compared
  axis by axis, a 1080×1920 portrait request was refused — MoneyPrinterTurbo's
  primary use case.
"""

import pytest

from src.creative.providers import (
    AUCUN,
    CreativeRequest,
    ProviderRegistry,
    adapt_declared,
)
from src.creative.research import load_research
from src.creative.routing import route
from src.media.providers.base import GenerationRequest, evaluate
from src.media.providers.moneyprinterturbo import CAPACITE_ATTENDUE


def _demande(width: int, height: int, duration: float = 30.0):
    """Une demande d'assemblage aux dimensions données."""
    return GenerationRequest(task="stock_assembly", width=width,
                             height=height, duration_s=duration)


class TestMPT07Vertical:
    """9:16 — le format social, et l'usage principal de MoneyPrinterTurbo."""

    def test_le_9_16_n_est_pas_refuse_sur_ses_dimensions(self):
        """Le défaut que ce test a trouvé.

        Les bornes sont comparées axe par axe (`base.py:199`). Déclarer
        1920×1080 refusait donc un 1080×1920 — le cas d'usage central du
        fournisseur, écarté par une déclaration en cadrage paysage.
        """
        verdict = evaluate(CAPACITE_ATTENDUE, _demande(1080, 1920))
        assert verdict["eligible"] is True, verdict["blockers"]

    def test_le_9_16_reste_borne_au_dela_de_la_limite(self):
        """La correction est étroite : elle n'ouvre pas les dimensions."""
        verdict = evaluate(CAPACITE_ATTENDUE, _demande(2160, 3840))
        assert verdict["eligible"] is False
        assert any("largeur" in b or "hauteur" in b for b in verdict["blockers"])


class TestMPT08Paysage:
    """16:9 — l'autre orientation, qui ne devait pas être cassée en réparant."""

    def test_le_16_9_passe(self):
        assert evaluate(CAPACITE_ATTENDUE, _demande(1920, 1080))["eligible"]

    def test_la_duree_reste_bornee(self):
        """Une borne relâchée par distraction se voit ici."""
        verdict = evaluate(CAPACITE_ATTENDUE, _demande(1920, 1080, 9999.0))
        assert verdict["eligible"] is False
        assert any("durée" in b for b in verdict["blockers"])


class TestMPT06Repli:
    """§29, dit tel qu'il est : il n'y a pas de second candidat."""

    @pytest.fixture(scope="class")
    def registre(self):
        inscrit = ProviderRegistry()
        for fournisseur in adapt_declared(load_research()["candidates"]):
            inscrit.register(fournisseur)
        return inscrit

    def test_un_seul_fournisseur_sert_l_assemblage(self, registre):
        servants = [p.provider_id for p in registre.providers()
                    if p.serves("stock_assembly")]
        assert servants == ["moneyprinterturbo"], (
            "S'il y en a deux un jour, le repli devient testable pour de vrai "
            "— et ce test est l'endroit où on s'en apercevra."
        )

    def test_desactive_il_n_est_pas_remplace(self):
        """Un repli silencieux servirait autre chose que ce qui est demandé.

        Le registre est reconstruit ici plutôt que muté : un test qui laisse un
        fournisseur désactivé casse ses voisins, et la panne se cherche loin de
        sa cause.
        """
        prive = ProviderRegistry()
        for fournisseur in adapt_declared(load_research()["candidates"]):
            prive.register(
                fournisseur,
                state="DISABLED"
                if fournisseur.provider_id == "moneyprinterturbo" else "",
            )
        resultat = route(prive, CreativeRequest(task="stock_assembly"))
        assert resultat["status"] == AUCUN
        assert "substitution silencieuse" in resultat["reason"]

    def test_le_registre_partage_reste_intact(self, registre):
        """La désactivation ci-dessus ne doit pas avoir fui."""
        resultat = route(registre, CreativeRequest(task="stock_assembly"))
        assert resultat["provider_id"] == "moneyprinterturbo"
