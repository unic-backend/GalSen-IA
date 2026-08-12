"""
Le linter fait partie de « terminé », pas seulement de la CI.

`.claude/rules/coding-conventions.md` énonce des règles que **rien** ne
vérifiait : elles tenaient parce qu'un seul auteur les appliquait. Le jour où un
deuxième contributeur arrive, une convention non vérifiée est une convention
qu'il faut deviner.

Ce que la mise en place a trouvé, avant même d'être configurée — et aucun de ces
défauts n'était visible dans la suite de tests :

- `SimpleStreamHandler.collect_stream_response_async` levait `NameError: chrunk`,
  une faute de frappe qu'un commentaire signalait sans la corriger ;
- `WeightedResponseRanker.rank_responses` levait `NameError: weights` ;
- `InMemoryModelStore.cleanup_expired` levait `NameError: ModelStatus` **dès
  qu'un modèle existait** — sur un magasin vide, la boucle ne s'exécutait pas et
  le test passait ;
- un dictionnaire de poids déclarait `"accuracy"` deux fois, la première valeur
  était silencieusement perdue ;
- `ObjectDetector` lisait un `min_area` par appel, documenté comme surchargeable,
  puis utilisait `self.min_area` ;
- deux tests **ne pouvaient pas échouer** : `assert False` y levait une
  `AssertionError` que le `except Exception` juste en dessous rattrapait.

Le test dure quelques millisecondes ; le lancer ici évite de découvrir en CI ce
qui se corrige en une seconde en local.
"""

import os
import shutil
import subprocess
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def ruff():
    """Chemin de `ruff`, ou saut explicite s'il n'est pas installé."""
    chemin = shutil.which("ruff")
    if chemin is None:
        pytest.skip(
            "ruff n'est pas installé — `pip install -r requirements-dev.txt`. "
            "Le saut est explicite : un linter absent ne doit pas se lire "
            "comme un dépôt propre."
        )
    return chemin


def test_le_depot_passe_son_propre_linter(ruff):
    """
    L'ensemble de règles est choisi pour être **tenu**, pas pour impressionner :
    un linter qui signale trois mille écarts est un linter que personne ne lit,
    et le silence qui suit vaut moins que pas de linter du tout. Périmètre et
    exclusions → `pyproject.toml`.
    """
    resultat = subprocess.run(
        [ruff, "check", "--no-cache", "."],
        cwd=RACINE, capture_output=True, text=True,
    )

    assert resultat.returncode == 0, (
        "ruff signale des écarts :\n" + resultat.stdout + resultat.stderr
    )


def test_la_configuration_du_linter_existe_et_garde_l_essentiel():
    """
    `F` (pyflakes) est le cœur : noms indéfinis, imports morts, clés dupliquées.
    Le retirer désactiverait précisément ce qui a trouvé les trois `NameError`
    ci-dessus, et le dépôt resterait vert.
    """
    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover - le projet cible 3.11
        pytest.skip("tomllib requiert Python 3.11")

    with open(os.path.join(RACINE, "pyproject.toml"), "rb") as fichier:
        configuration = tomllib.load(fichier)

    selection = configuration["tool"]["ruff"]["lint"]["select"]

    assert "F" in selection
    assert "E9" in selection


def test_ruff_est_declare_comme_dependance_de_developpement():
    """
    Un outil que la CI lance doit être déclaré, et figé : un linter qui change
    tout seul fait échouer la CI sur un commit qui n'a rien changé.
    """
    with open(os.path.join(RACINE, "requirements-dev.txt"), encoding="utf-8") as fichier:
        contenu = fichier.read()

    assert "ruff==" in contenu


# ----------------------------------------------------------------------
# Les défauts trouvés par le linter, épinglés un par un
# ----------------------------------------------------------------------

def test_un_flux_se_collecte_sans_faute_de_frappe():
    """`chunks.append(chrunk)` — la faute était signalée par un commentaire."""
    import asyncio

    sys.path.insert(0, RACINE)
    from src.model_engine.stream_handler import SimpleStreamHandler

    async def flux():
        yield "bon"
        yield "jour"

    assert asyncio.run(SimpleStreamHandler().collect_stream_response_async(flux())) == "bonjour"


def test_le_classement_des_reponses_calcule_ses_poids():
    """`weights` était lu dans `_compute_score`, qui ne le définissait pas."""
    sys.path.insert(0, RACINE)
    from src.model_engine.response_ranker import WeightedResponseRanker
    from src.model_engine.types import ModelItem, ModelType

    modele = ModelItem(model_id="m1", name="t", version="1",
                       model_type=ModelType.LOCAL_OLLAMA, provider="ollama")

    classement = WeightedResponseRanker().rank_responses([modele], ["une réponse claire"])

    assert len(classement) == 1
    assert 0.0 <= classement[0][2] <= 1.0


def test_un_critere_n_est_pondere_qu_une_fois():
    """
    `"accuracy"` était déclaré deux fois dans le même littéral : Python garde la
    dernière valeur et jette la première, sans rien dire.
    """
    sys.path.insert(0, RACINE)
    from src.model_engine.response_ranker import WeightedResponseRanker

    poids = WeightedResponseRanker()._default_weights

    assert poids["accuracy"] == 0.25
    assert len(poids) == 5


def test_le_nettoyage_des_modeles_expires_ne_leve_pas():
    """
    `ModelStatus` n'était pas importé. Sur un magasin vide la boucle ne
    s'exécutait pas : le défaut n'apparaissait qu'avec au moins un modèle, ce
    qu'aucun test ne faisait.
    """
    sys.path.insert(0, RACINE)
    from src.model_engine.model_store import InMemoryModelStore
    from src.model_engine.types import ModelItem, ModelType

    magasin = InMemoryModelStore()
    magasin.save(ModelItem(model_id="m1", name="t", version="1",
                           model_type=ModelType.LOCAL_OLLAMA, provider="ollama"))

    assert magasin.cleanup_expired() == 0


def test_la_surface_minimale_de_detection_est_surchargeable_par_appel():
    """
    `min_area` était lu depuis les arguments — et documenté comme surchargeable
    — puis la comparaison utilisait `self.min_area`. La surcharge ne faisait rien.
    """
    import inspect

    sys.path.insert(0, RACINE)
    from src.vision_intelligence_engine import object_detector

    source = inspect.getsource(object_detector)

    assert "min_area = kwargs.get(" in source
    assert "if area < min_area:" in source, "la surcharge par appel est de nouveau ignorée"
