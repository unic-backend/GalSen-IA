"""
Tests for capability routing (C15 phase 15.1, directive V4 §36).

Two properties carry these tests, and both are about refusing to know.

**`UNKNOWN` is not `UNMET`.** A provider that declares it cannot control the
camera is rejected; a provider that declares nothing is not. Folding the two
makes opposite mistakes depending on which way it folds — discarding what works,
or keeping what does not.

**A ranking with a missing value is not a ranking.** Ordering candidates on a
dimension half of them never declared puts them last without measuring them,
and the order then reads as a result. `UNRANKED` is the honest answer, and the
tests assert it is returned rather than worked around.
"""

import pytest

from src.creative.providers import (
    AUCUN,
    CHOISI,
    CreativeProvider,
    CreativeRequest,
    LicenceRecord,
    ProviderRegistry,
)
from src.creative.routing import (
    INDETERMINE,
    NON_CLASSE,
    SATISFAIT,
    MatchResult,
    RoutingNeed,
    RoutingRefused,
    match,
    rank,
    route,
    routing_report,
)


def _fournisseur(identifiant, **champs):
    """Un fournisseur servant `text_to_video`, commercialement autorisé."""
    base = {
        "provider_id": identifiant,
        "tasks": frozenset({"text_to_video"}),
        "input_modalities": ("text",),
        "output_modalities": ("video",),
        "licence": LicenceRecord(
            repository="MIT", weights="MIT", commercial="ALLOWED",
            # Le garde de C04 exige une source : une licence de dépôt
            # permissive n'est pas une permission d'usage des poids (§40).
            verified_from="https://example.invalid/LICENSE"),
        "runs_locally": True,
    }
    base.update(champs)
    return CreativeProvider(**base)


def _registre(*fournisseurs):
    """Un registre portant les fournisseurs donnés."""
    registre = ProviderRegistry()
    for fournisseur in fournisseurs:
        registre.register(fournisseur)
    return registre


class TestAppariement:
    """Chaque dimension rend son verdict, séparément."""

    def test_une_capacite_declaree_est_satisfaite(self):
        resultat = match(
            _fournisseur("a", capability_status={"camera_control": "SUPPORTED"}),
            RoutingNeed(capabilities=("camera_control",)))
        assert resultat.eligible is True
        assert resultat.dimensions[0].verdict == SATISFAIT

    def test_un_refus_declare_ecarte(self):
        resultat = match(
            _fournisseur("a", capability_status={"camera_control": "UNSUPPORTED"}),
            RoutingNeed(capabilities=("camera_control",)))
        assert resultat.eligible is False
        assert resultat.unmet == ["camera_control"]

    def test_une_absence_de_declaration_n_ecarte_pas(self):
        """« Personne n'a regardé » n'est pas « il ne sait pas faire »."""
        resultat = match(_fournisseur("a"),
                         RoutingNeed(capabilities=("camera_control",)))
        assert resultat.eligible is True
        assert resultat.unknown == ["camera_control"]
        assert "absence d'information" in resultat.dimensions[0].reason

    def test_le_demandeur_decide_de_sa_tolerance(self):
        """`strict` transforme l'inconnu en refus — c'est son choix, pas le nôtre."""
        besoin = RoutingNeed(capabilities=("camera_control",),
                             strict=("camera_control",))
        resultat = match(_fournisseur("a"), besoin)
        assert resultat.eligible is False
        assert resultat.unmet == ["camera_control"]

    def test_un_partiel_ne_tranche_pas(self):
        resultat = match(
            _fournisseur("a", capability_status={"lip_sync": "PARTIAL"}),
            RoutingNeed(capabilities=("lip_sync",)))
        assert resultat.dimensions[0].verdict == INDETERMINE
        assert "n'est pas tranchée" in resultat.dimensions[0].reason

    def test_la_vram_se_compare_quand_les_deux_chiffres_existent(self):
        besoin = RoutingNeed(available_vram_gb=8.0)
        assert match(_fournisseur("petit", min_vram_gb=6.0), besoin).eligible
        gros = match(_fournisseur("gros", min_vram_gb=24.0), besoin)
        assert gros.eligible is False
        assert "24.0 Gio requis" in gros.dimensions[0].reason

    def test_une_vram_non_mesuree_reste_indeterminee(self):
        """Un besoin confronté à une mesure absente n'est pas satisfait."""
        resultat = match(_fournisseur("a", min_vram_gb=24.0), RoutingNeed())
        assert resultat.dimensions[0].verdict == INDETERMINE
        assert resultat.eligible is True

    def test_aucun_score_global_n_est_produit(self):
        """Additionner licence et latence ferait un nombre qui a l'air mesuré."""
        resultat = match(_fournisseur("a"), RoutingNeed(capabilities=CAPACITES_TEST))
        assert not hasattr(resultat, "score")
        assert isinstance(resultat, MatchResult)

    def test_une_capacite_inconnue_du_vocabulaire_est_refusee(self):
        with pytest.raises(RoutingRefused) as erreur:
            RoutingNeed(capabilities=("telepathie",))
        assert "au hasard" in str(erreur.value)

    def test_une_capacite_stricte_doit_etre_demandee(self):
        with pytest.raises(RoutingRefused):
            RoutingNeed(capabilities=("lip_sync",), strict=("camera_control",))

    def test_une_duree_nulle_n_est_pas_une_duree(self):
        with pytest.raises(RoutingRefused):
            RoutingNeed(duration_s=0)


CAPACITES_TEST = ("audio_output", "lip_sync")


class TestClassement:
    """Classer sur un chiffre absent range sans mesurer."""

    def test_un_classement_complet_ordonne(self):
        resultat = rank([_fournisseur("cher", cost_per_second=0.9),
                         _fournisseur("bon", cost_per_second=0.1)],
                        by="cost_per_second")
        assert resultat["status"] == "RANKED"
        assert resultat["order"] == ["bon", "cher"]

    def test_un_seul_chiffre_manquant_annule_le_classement(self):
        resultat = rank([_fournisseur("chiffre", cost_per_second=0.1),
                         _fournisseur("muet")],
                        by="cost_per_second")
        assert resultat["status"] == NON_CLASSE
        assert resultat["missing"] == ["muet"]
        assert "sans les avoir mesurés" in resultat["reason"]

    def test_la_qualite_ne_se_classe_pas(self):
        """Lui inventer une échelle en ferait une mesure."""
        with pytest.raises(RoutingRefused) as erreur:
            rank([_fournisseur("a")], by="quality")
        assert "inventer une échelle" in str(erreur.value)

    def test_sans_candidat_il_n_y_a_rien_a_classer(self):
        with pytest.raises(RoutingRefused):
            rank([], by="cost_per_second")


class TestRoutage:
    """Le choix sort de l'appariement, jamais d'une association codée en dur."""

    def _demande(self):
        return CreativeRequest(task="text_to_video")

    def test_un_fournisseur_apparie_est_retenu(self):
        registre = _registre(
            _fournisseur("a", capability_status={"audio_output": "SUPPORTED"}))
        resultat = route(registre, self._demande(),
                         RoutingNeed(capabilities=("audio_output",)))
        assert resultat["status"] == CHOISI
        assert resultat["provider_id"] == "a"

    def test_aucun_repli_sur_le_plus_proche(self):
        registre = _registre(
            _fournisseur("a", capability_status={"audio_output": "UNSUPPORTED"}))
        resultat = route(registre, self._demande(),
                         RoutingNeed(capabilities=("audio_output",)))
        assert resultat["status"] == AUCUN
        assert "substitution silencieuse" in resultat["reason"]

    def test_la_matrice_dit_ce_qui_a_ecarte_chacun(self):
        registre = _registre(
            _fournisseur("refuse", capability_status={"lip_sync": "UNSUPPORTED"}),
            _fournisseur("muet"))
        resultat = route(registre, self._demande(),
                         RoutingNeed(capabilities=("lip_sync",)))
        par_id = {e["provider_id"]: e for e in resultat["matrix"]}
        assert par_id["refuse"]["unmet"] == ["lip_sync"]
        assert par_id["muet"]["unknown"] == ["lip_sync"]

    def test_le_depart_par_cout_ordonne_quand_les_chiffres_existent(self):
        registre = _registre(_fournisseur("cher", cost_per_second=0.9),
                             _fournisseur("bon", cost_per_second=0.1))
        resultat = route(registre, self._demande(), prefer="cost_per_second")
        assert resultat["provider_id"] == "bon"
        assert resultat["ranking"]["status"] == "RANKED"

    def test_sans_depart_le_retour_dit_que_ce_n_est_pas_un_classement(self):
        """Sinon l'ordre d'inscription se lirait comme une décision."""
        registre = _registre(_fournisseur("a"), _fournisseur("b"))
        resultat = route(registre, self._demande())
        assert resultat["ranking"]["status"] == NON_CLASSE
        assert "n'est pas un classement" in resultat["ranking"]["reason"]

    def test_un_depart_impossible_reste_visible_dans_le_retour(self):
        registre = _registre(_fournisseur("chiffre", cost_per_second=0.1),
                             _fournisseur("muet"))
        resultat = route(registre, self._demande(), prefer="cost_per_second")
        assert resultat["ranking"]["status"] == NON_CLASSE
        assert resultat["provider_id"] == "chiffre"

    def test_un_depart_non_classable_est_refuse(self):
        with pytest.raises(RoutingRefused):
            route(_registre(_fournisseur("a")), self._demande(), prefer="quality")

    def test_les_contraintes_de_licence_ne_sont_pas_redoublees(self):
        """`evaluate()` les applique déjà ; les refaire ici créerait une
        seconde vérité."""
        registre = _registre(_fournisseur(
            "inconnu",
            licence=LicenceRecord(repository="MIT", weights="UNKNOWN",
                                  commercial="UNKNOWN")))
        resultat = route(registre, CreativeRequest(task="text_to_video",
                                                   commercial=True))
        assert resultat["status"] == AUCUN


class TestRapport:
    """Les règles se lisent sans lire le code."""

    def test_la_qualite_est_nommee_comme_non_classable(self):
        rapport = routing_report()
        assert "quality" in rapport["not_rankable"]
        assert "identity_consistency" in rapport["not_rankable"]
        assert "inventerait" in rapport["why_quality_is_not_rankable"]

    def test_les_dimensions_classables_ont_toutes_un_chiffre(self):
        for dimension in routing_report()["rankable"]:
            assert dimension in {"cost_per_second", "typical_latency_s",
                                 "min_vram_gb"}
