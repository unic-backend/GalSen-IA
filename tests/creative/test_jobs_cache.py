"""
Tests for creative jobs and cache (C16 phase 16.2, directive V4 §53, §54, §55).

Three properties carry these tests.

**No second queue.** §53 says to reuse the existing job system, and one exists
(`RenderQueue`). State, progress and attempts are read from it, never mirrored
here — two truths about one job's progress means reading whichever drifted.

**A job names the references that conditioned it.** ADR-025 promises a person
can withdraw their reference. That promise only holds if the artefacts it
conditioned can be found, so a job claiming to use references without naming any
is refused.

**A stale cache entry is returned, and says so.** §54 forbids returning stale
artefacts *without metadata*, not returning them at all. Refusing outright would
make the cache useless on the day the provider is down — which is the day it
earns its keep. There is deliberately no method returning the value alone.
"""

import pytest

from src.creative.cache import (
    FRAIS,
    INDETERMINE,
    PERIME,
    CacheRefused,
    CreativeCache,
    cache_key,
)
from src.creative.jobs import (
    CreativeJobBook,
    CreativeJobRefused,
    fingerprint,
)
from src.media.queue.jobs import RenderQueue
from src.router.workflow_checkpoint import RunStatus


class TestTravaux:
    """La file existe : on s'y raccorde, on ne la refait pas."""

    def test_l_identite_est_celle_de_la_file(self):
        """Deux identités pour un travail feraient diverger les rapports."""
        file = RenderQueue()
        registre = CreativeJobBook(file)
        travail = registre.submit(user="awa", task="text_to_video",
                                  provider_id="p")
        assert file.get(travail.job_id) is not None

    def test_l_etat_est_lu_dans_la_file(self):
        registre = CreativeJobBook()
        travail = registre.submit(user="awa", task="text_to_video",
                                  provider_id="p")
        assert registre.status_of(travail.job_id) == RunStatus.RUNNING
        registre.queue.cancel(travail.job_id, by="awa")
        assert registre.status_of(travail.job_id) == RunStatus.CANCELLED

    def test_l_etat_n_est_pas_recopie_dans_le_volet_creatif(self):
        travail = CreativeJobBook().submit(user="awa", task="text_to_video",
                                           provider_id="p")
        assert "status" not in travail.as_dict()

    def test_un_travail_sans_demandeur_est_refuse(self):
        with pytest.raises(CreativeJobRefused) as erreur:
            CreativeJobBook().submit(user="  ", task="text_to_video",
                                     provider_id="p")
        assert "ni retiré" in str(erreur.value)

    def test_un_genre_non_declare_est_refuse(self):
        with pytest.raises(CreativeJobRefused):
            CreativeJobBook().submit(user="awa", task="text_to_video",
                                     provider_id="p", kind="hologramme")

    def test_un_total_inconnu_reste_none_jamais_zero(self):
        """Un travail à 0/0 paraîtrait terminé."""
        registre = CreativeJobBook()
        travail = registre.submit(user="awa", task="text_to_video",
                                  provider_id="p")
        assert registre.queue.get(travail.job_id).total_units is None


class TestRevocation:
    """ADR-025 : « retirez ma photo » doit pouvoir atteindre les artefacts."""

    def test_utiliser_des_references_sans_les_nommer_est_refuse(self):
        with pytest.raises(CreativeJobRefused) as erreur:
            CreativeJobBook().submit(user="awa", task="text_to_video",
                                     provider_id="p", uses_references=True)
        assert "ADR-025" in str(erreur.value)

    def test_les_travaux_d_une_reference_sont_retrouvables(self):
        registre = CreativeJobBook()
        avec = registre.submit(user="awa", task="text_to_video",
                               provider_id="p", references=("ref-1",),
                               uses_references=True)
        registre.submit(user="awa", task="text_to_video", provider_id="p",
                        references=("ref-2",), uses_references=True)
        assert registre.jobs_using("ref-1") == [avec.job_id]

    def test_aucune_reference_n_est_un_etat_normal(self):
        """« Aucune » et « champ non rempli » sont distingués."""
        travail = CreativeJobBook().submit(user="awa", task="text_to_video",
                                           provider_id="p")
        assert travail.provenance.references == ()


class TestProvenance:
    """§55 : un artefact dit d'où il sort."""

    def test_l_empreinte_depend_de_l_ordre(self):
        assert fingerprint("a", "b") != fingerprint("b", "a")

    def test_l_empreinte_ne_confond_pas_les_concatenations(self):
        # « ab »+« c » ne doit pas valoir « a »+« bc ».
        assert fingerprint("ab", "c") != fingerprint("a", "bc")

    def test_une_graine_absente_reste_none(self):
        """`0` serait une graine, pas une absence."""
        travail = CreativeJobBook().submit(user="awa", task="text_to_video",
                                           provider_id="p")
        assert travail.provenance.seed is None

    def test_un_artefact_scelle_son_empreinte(self):
        registre = CreativeJobBook()
        travail = registre.submit(user="awa", task="text_to_video",
                                  provider_id="p")
        scelle = registre.record_artifact(travail.job_id, "/out/a.webm",
                                          sha256=fingerprint("prompt"))
        assert scelle.artifacts == ["/out/a.webm"]
        assert scelle.provenance.inputs_sha256 == fingerprint("prompt")


class TestCache:
    """§54 : rendre du périmé est permis, le taire ne l'est pas."""

    def test_aucune_methode_ne_rend_la_valeur_seule(self):
        """Elle serait celle que tout le monde appellerait."""
        assert not hasattr(CreativeCache(), "get")

    def test_une_entree_fraiche_est_marquee_fraiche(self):
        cache = CreativeCache(stale_after_seconds=60)
        cache.put("k", "valeur", provider_id="p")
        assert cache.lookup("k")["freshness"] == FRAIS

    def test_une_entree_perimee_est_rendue_et_marquee(self):
        cache = CreativeCache(stale_after_seconds=10)
        entree = cache.put("k", "valeur", provider_id="p")
        vue = cache.lookup("k", now=entree.stored_at + 999)
        assert vue["hit"] is True
        assert vue["value"] == "valeur"
        assert vue["freshness"] == PERIME
        assert "à l'appelant de décider" in vue["reason"]

    def test_sans_seuil_la_fraicheur_est_inconnue_pas_fraiche(self):
        cache = CreativeCache()
        cache.put("k", "valeur")
        assert cache.lookup("k")["freshness"] == INDETERMINE

    def test_une_absence_se_distingue_d_une_valeur_nulle(self):
        cache = CreativeCache()
        cache.put("k", None)
        assert cache.lookup("k")["hit"] is True
        assert cache.lookup("autre")["hit"] is False

    def test_rien_ne_disparait_au_temps(self):
        """Avec une expiration automatique, l'entrée qui aurait sauvé
        l'exécution a déjà disparu."""
        cache = CreativeCache(stale_after_seconds=1)
        entree = cache.put("k", "valeur")
        assert cache.lookup("k", now=entree.stored_at + 10_000)["hit"] is True

    def test_l_invalidation_exige_un_auteur_et_un_motif(self):
        cache = CreativeCache()
        cache.put("k", "valeur")
        with pytest.raises(CacheRefused) as erreur:
            cache.invalidate("k", by="", reason="")
        assert "après un incident" in str(erreur.value)

    def test_invalider_une_entree_absente_est_refuse(self):
        with pytest.raises(CacheRefused):
            CreativeCache().invalidate("fantome", by="awa", reason="x")

    def test_invalider_un_fournisseur_retire_tout_ce_qu_il_a_produit(self):
        cache = CreativeCache()
        cache.put("a", 1, provider_id="vieux")
        cache.put("b", 2, provider_id="vieux")
        cache.put("c", 3, provider_id="autre")
        retirees = cache.invalidate_provider("vieux", by="awa",
                                             reason="licence incompatible")
        assert sorted(retirees) == ["a", "b"]
        assert cache.lookup("c")["hit"] is True

    def test_l_invalidation_laisse_une_trace(self):
        cache = CreativeCache()
        cache.put("k", 1)
        cache.invalidate("k", by="awa", reason="version changée")
        trace = cache.report()["invalidations"][0]
        assert trace["by"] == "awa" and "version" in trace["reason"]

    def test_un_seuil_nul_est_refuse(self):
        with pytest.raises(CacheRefused):
            CreativeCache(stale_after_seconds=0)


class TestCle:
    """Ce qui change le résultat change la clé."""

    def test_le_producteur_fait_partie_de_la_cle(self):
        """Sinon on rendrait le résultat d'un modèle sous le nom d'un autre."""
        assert cache_key("shot", "wan", "2.1", "prompt") != \
               cache_key("shot", "ltx", "2.1", "prompt")

    def test_la_version_fait_partie_de_la_cle(self):
        assert cache_key("shot", "wan", "2.1", "p") != \
               cache_key("shot", "wan", "2.2", "p")

    def test_une_cle_anonyme_est_refusee(self):
        with pytest.raises(CacheRefused) as erreur:
            cache_key("", "wan", "2.1", "p")
        assert "collisionnerait" in str(erreur.value)
