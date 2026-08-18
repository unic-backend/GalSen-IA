"""
Tests for the benchmark harness (§33).

What is pinned is the refusal: an absent capability produces `NOT_MEASURED`
with the capability named, never `0` and never an estimate — and every number
carries the machine it was taken on.
"""

import pytest

from src.media.benchmarks.harness import (
    MESURE,
    MESURES,
    NON_MESURE,
    BenchmarkRefused,
    bench_queue_throughput,
    bench_render,
    bench_transcription,
    benchmark_report,
    hardware,
    measure,
    run_all,
)


# --------------------------------------------------------------------------
# La mesure elle-même
# --------------------------------------------------------------------------


def test_une_operation_reelle_est_mesuree():
    resultat = measure("addition", lambda: sum(range(1000)), samples=3)
    assert resultat["status"] == MESURE
    assert resultat["samples"] == 3
    assert resultat["median_ms"] >= 0
    assert resultat["min_ms"] <= resultat["median_ms"] <= resultat["max_ms"]


def test_une_capacite_absente_donne_non_mesure_pas_zero():
    resultat = bench_transcription(samples=2)
    assert resultat["status"] == NON_MESURE
    assert resultat["missing"] == "transcription"
    # Zéro décrirait une transcription instantanée.
    assert resultat["median_ms"] is None
    assert resultat["samples"] == 0


def test_une_operation_qui_echoue_rend_son_erreur_pas_une_duree():
    def casse():
        raise RuntimeError("encodeur absent")

    resultat = measure("casse", casse, samples=3)
    assert resultat["status"] == NON_MESURE
    assert "encodeur absent" in resultat["reason"]
    assert resultat["median_ms"] is None


def test_zero_echantillon_est_refuse():
    with pytest.raises(BenchmarkRefused) as erreur:
        measure("rien", lambda: None, samples=0)
    assert "absence de mesure" in str(erreur.value)


def test_la_mediane_est_rendue_pas_la_moyenne():
    # Un échantillon très lent parmi des rapides : la médiane reste basse,
    # une moyenne aurait décrit la pause comme le cas normal.
    durees = iter([0, 0, 0.05, 0, 0])
    resultat = measure("pause", lambda: _dormir(next(durees)), samples=5)
    assert resultat["status"] == MESURE
    assert resultat["median_ms"] < resultat["max_ms"] / 2


def _dormir(secondes: float) -> None:
    """Attend, pour fabriquer un échantillon lent reproductible."""
    import time

    if secondes:
        time.sleep(secondes)


# --------------------------------------------------------------------------
# La machine
# --------------------------------------------------------------------------


def test_la_machine_est_lue_pas_supposee():
    machine = hardware()
    assert machine["cpu_count"] and machine["cpu_count"] > 0
    assert machine["python"]
    assert machine["platform"]
    # Ce qui n'est pas lisible vaut `None`, jamais une valeur plausible.
    assert machine["gpu_vram_gb"] is None or machine["gpu_vram_gb"] > 0
    assert "opencv" in machine["libraries"]


def test_toutes_les_mesures_du_registre_acceptent_le_meme_appel():
    # Le registre les appelle avec un seul argument positionnel. Une signature
    # divergente mesurait trois travaux en croyant en mesurer deux cents.
    for nom, fonction in MESURES.items():
        resultat = fonction(1)
        assert resultat["benchmark"] == nom
        assert resultat["status"] in (MESURE, NON_MESURE)


def test_la_file_est_mesuree_sur_le_nombre_annonce():
    resultat = bench_queue_throughput(2, jobs=50)
    assert resultat["status"] == MESURE
    assert resultat["samples"] == 2


# --------------------------------------------------------------------------
# Le relevé
# --------------------------------------------------------------------------


def test_le_releve_porte_toujours_sa_machine():
    releve = run_all(samples=1)
    assert releve["hardware"]["cpu_count"]
    # « détection de plans : 3 ms » n'est pas un résultat, c'est la moitié d'un.
    assert releve["counts"]["measured"] >= 1
    assert set(releve["results"]) >= set(MESURES)


def test_un_encodage_sans_repertoire_est_declare_non_mesure():
    releve = run_all(samples=1)
    rendu = releve["results"]["render"]
    assert rendu["status"] == NON_MESURE
    # Déclaré, pas sauté : une mesure absente d'un tableau se lit comme une
    # mesure qui n'existe pas.
    assert "n'écrit rien" in rendu["reason"]
    assert "render" in releve["not_measured"]


def test_un_encodage_reel_est_mesure_sur_cette_machine(tmp_path):
    # `frame_encode` est disponible ici : la mesure est faite en écrivant un
    # vrai fichier, pas en simulant un encodeur.
    resultat = bench_render(str(tmp_path), samples=1)
    if resultat["status"] == MESURE:
        assert resultat["median_ms"] > 0
        assert list(tmp_path.iterdir())
    else:
        assert resultat["missing"] == "frame_encode"


def test_ce_qui_n_a_pas_ete_mesure_est_nomme():
    releve = run_all(samples=1)
    assert "transcription" in releve["not_measured"]
    assert releve["not_measured"]["transcription"] == "transcription"


def test_le_rapport_nomme_ce_que_les_mesures_refusent():
    rapport = benchmark_report()
    refus = " ".join(rapport["does_not"]).lower()
    assert "estimer" in refus
    assert "moyenne" in refus
    assert "machine" in refus
