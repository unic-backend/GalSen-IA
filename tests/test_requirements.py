"""
Les dépendances déclarées doivent correspondre à celles que le code importe.

Deux défauts ont motivé ces tests, tous deux invisibles pour la suite existante
parce qu'elle tourne dans un environnement où tout est déjà installé :

- **Les versions n'étaient pas figées** (`>=`). La même étiquette git produisait
  deux images différentes à six mois d'écart, et le jour où l'une casse, plus
  moyen de dire laquelle a bougé. Une publication doit se reconstruire à
  l'identique.
- **L'image de production installait les outils de test.** `requirements.txt`
  portait pytest, ses greffons et le client HTTP de test ; ils partaient dans le
  conteneur exposé au réseau. Du code qui ne sert jamais en production reste du
  code à mettre à jour et à surveiller.

Le contrôle central est celui qui **dérive** la liste attendue du code lui-même :
séparer exécution et développement à la main se défait au premier import ajouté,
et l'erreur n'apparaîtrait qu'à la construction de l'image — c'est-à-dire nulle
part, puisque `docker` n'est pas disponible ici.
"""

import ast
import os
import re
import sys
from importlib.metadata import packages_distributions
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Répertoires dont les imports doivent être couverts par les dépendances
# d'exécution : ce sont ceux que l'image de production embarque.
SOURCES_EXECUTION = ("src", "agents", "tools")

# Modules du dépôt lui-même : ils ne se déclarent pas comme dépendances.
PREMIERE_PARTIE = {
    "src", "agents", "tools", "scripts", "config", "workflows", "tests",
    "prompts", "serveur_cerveau",
}

# Dépendances utilisées uniquement par la suite de tests.
DEVELOPPEMENT = {"pytest", "pytest-asyncio", "pytest-cov", "httpx2"}


def _lire(nom: str) -> str:
    """Retourne le contenu d'un fichier d'exigences."""
    return (RACINE / nom).read_text(encoding="utf-8")


def _declarees(nom: str) -> set:
    """Retourne les distributions déclarées dans un fichier d'exigences."""
    declarees = set()
    for ligne in _lire(nom).splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if not ligne or ligne.startswith("-"):
            continue
        declarees.add(re.split(r"[=<>!~\[]", ligne, maxsplit=1)[0].strip().lower())
    return declarees


def _modules_importes(racines) -> set:
    """
    Retourne les modules de premier niveau importés par le code.

    L'arbre syntaxique est lu plutôt que le texte : une chaîne contenant
    « import numpy » dans une docstring ne doit pas compter comme un import.
    """
    modules = set()
    for racine in racines:
        for chemin in (RACINE / racine).rglob("*.py"):
            try:
                arbre = ast.parse(chemin.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):  # pragma: no cover - fichier illisible
                continue
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Import):
                    modules.update(alias.name.split(".")[0] for alias in noeud.names)
                elif isinstance(noeud, ast.ImportFrom):
                    if noeud.level == 0 and noeud.module:
                        modules.add(noeud.module.split(".")[0])
    return modules


def _distributions(modules) -> set:
    """Traduit des noms de modules en noms de distributions installées."""
    table = packages_distributions()
    distributions = set()
    for module in modules:
        if module in sys.stdlib_module_names or module in PREMIERE_PARTIE:
            continue
        for distribution in table.get(module, []):
            distributions.add(distribution.lower())
    return distributions


# Modules dont le nom d'import diffère du nom de distribution. Sans cette table,
# un paquet déclaré passerait pour absent parce qu'on importe `docx` et qu'on
# installe `python-docx`.
NOM_DE_DISTRIBUTION = {
    "docx": "python-docx",
    "pptx": "python-pptx",
    "cv2": "opencv-python-headless",
    "PIL": "pillow",
    "yaml": "pyyaml",
    "sentence_transformers": "sentence-transformers",
    "faster_whisper": "faster-whisper",
}


def _toutes_declarations() -> set:
    """Retourne les distributions déclarées dans tous les fichiers d'exigences."""
    declarees = set()
    for fichier in RACINE.glob("requirements*.txt"):
        declarees |= _declarees(fichier.name)
    return declarees


def _modules_tiers_non_installes(modules) -> set:
    """
    Retourne les modules importés qui ne sont **ni installés ni déclarés**.

    C'est l'angle mort de `_distributions` : elle traduit un module en
    distribution **via ce qui est installé**, donc un paquet absent de
    l'environnement est aussi absent de la traduction, et passe inaperçu.

    Un paquet déclaré mais non installé ici n'est pas un problème : l'image
    l'installera. Ne regarder que l'installation ferait donc sonner l'alarme au
    moment même où le problème vient d'être corrigé.
    """
    table = packages_distributions()
    declarees = _toutes_declarations()
    orphelins = set()
    for module in modules:
        if module in sys.stdlib_module_names or module in PREMIERE_PARTIE:
            continue
        if module in table:
            continue
        distribution = NOM_DE_DISTRIBUTION.get(module, module).lower()
        if distribution in declarees or module.lower() in declarees:
            continue
        orphelins.add(module)
    return orphelins


def test_toute_dependance_importee_par_le_code_est_declaree():
    """
    Le contrôle qui rend la séparation sûre.

    Sans lui, déplacer un paquet vers `requirements-dev.txt` par erreur ne se
    verrait qu'au démarrage du conteneur, en production.
    """
    attendues = _distributions(_modules_importes(SOURCES_EXECUTION))
    manquantes = sorted(attendues - _declarees("requirements.txt"))

    assert manquantes == [], (
        f"importées par {'/'.join(SOURCES_EXECUTION)} mais absentes de "
        f"requirements.txt : {manquantes}"
    )


def test_aucun_import_ne_vise_un_paquet_ni_installe_ni_declare():
    """
    L'angle mort du contrôle précédent, trouvé pendant l'évaluation d'architecture.

    `_distributions` traduit un module en distribution **via ce qui est
    installé** : un paquet absent de l'environnement est donc absent de la
    traduction, et son import ne déclenche rien. C'est ainsi que
    `src/tools/embeddings/tool.py` importait `sentence_transformers` — déclaré
    actif dans `tools/tools.yaml`, absent de `requirements.txt`, absent de la
    machine — sans qu'aucun test ne le remarque. L'outil rapportait une erreur à
    l'exécution, ce qui est honnête, mais le catalogue annonçait une capacité
    que rien ne pouvait rendre.

    Un module toléré ici doit l'être **explicitement**, avec sa raison.
    """
    # Modules importés à dessein sans être installés. La liste a été **décidée**
    # le 2026-08-12, pas subie : chaque paquet a été pesé, et six des huit
    # trouvés à l'origine en sont sortis — cinq déclarés (`pypdf`,
    # `python-docx`, `openpyxl`, `python-pptx`, `markdown`), un remplacé par
    # NumPy (`scipy`), un désactivé pour raison de sécurité (`docker`).
    TOLERES = {
        # Client Docker : l'outil est **désactivé** dans `tools/tools.yaml` pour
        # une raison de sécurité, pas par manque de dépendance. Il sait lancer et
        # détruire des conteneurs ; depuis l'intérieur du conteneur de
        # production, cela suppose de monter /var/run/docker.sock, c'est-à-dire
        # de donner à un agent l'équivalent de root sur l'hôte.
        "docker",
        # `PyPDF2` est archivé ; le code accepte `pypdf`, son successeur
        # maintenu et déclaré. L'ancien nom reste dans un `except ImportError`
        # pour les installations existantes.
        "PyPDF2",
        # `whisper` est l'implémentation de référence ; `faster-whisper`, quatre
        # fois plus rapide sur CPU, est celle qui est déclarée. Le code accepte
        # les deux.
        "whisper",
        # `torch` et `playwright` ne sont importés que **dans une sonde de
        # capacité** (`src/media/core/capabilities.py`), à l'intérieur d'un
        # `try/except ImportError` dont l'échec est le résultat mesuré : leur
        # absence rend `gpu_compute` INDISPONIBLE et `browser_render` DEGRADE,
        # et `require()` refuse alors le travail au lieu de le simuler. Les
        # déclarer dans `requirements.txt` imposerait plusieurs gigaoctets de
        # poids CUDA à toute installation qui ne génère aucune vidéo.
        "torch",
        "playwright",
    }

    orphelins = _modules_tiers_non_installes(_modules_importes(SOURCES_EXECUTION))
    inattendus = sorted(orphelins - TOLERES)

    assert inattendus == [], (
        f"importés par le code, ni installés ni déclarés : {inattendus}. "
        f"Déclarez-les dans requirements.txt, ou ajoutez-les à TOLERES avec la "
        f"raison et la façon dont la capacité se désactive."
    )


def test_les_tolerances_sont_reellement_absentes():
    """
    Le contre-test : une tolérance qui ne sert plus doit se voir.

    Le jour où `sentence-transformers` est installé et déclaré, cette liste
    doit maigrir — sinon elle deviendrait un tapis sous lequel glisser les
    imports suivants.
    """
    installes = packages_distributions()

    assert "sentence_transformers" not in installes, (
        "sentence-transformers est désormais installé : retirez-le de TOLERES "
        "et déclarez-le dans requirements.txt (VOLET 27)."
    )

    # Les tolérances du moteur média suivent la même règle : elles ne valent que
    # tant que le paquet est réellement absent. Le jour où l'un est installé, sa
    # capacité cesse d'être « indisponible par construction » et doit être
    # déclarée comme les autres.
    for module, capacite in (("torch", "gpu_compute"),
                             ("playwright", "browser_render")):
        assert module not in installes, (
            f"{module} est désormais installé : retirez-le de TOLERES, "
            f"déclarez-le dans requirements.txt, et vérifiez que la sonde "
            f"« {capacite} » rapporte bien son nouvel état "
            f"(`src/media/core/capabilities.py`)."
        )


def test_les_outils_de_test_ne_sont_pas_dans_l_image():
    """pytest n'a rien à faire dans un conteneur exposé au réseau."""
    execution = _declarees("requirements.txt")

    assert not (execution & DEVELOPPEMENT), (
        f"outils de test dans les dépendances d'exécution : "
        f"{sorted(execution & DEVELOPPEMENT)}"
    )


def test_les_outils_de_test_restent_disponibles_pour_la_suite():
    """Le contre-test : les avoir sortis ne doit pas les avoir perdus."""
    developpement = _declarees("requirements-dev.txt")

    assert DEVELOPPEMENT <= developpement, (
        f"absents de requirements-dev.txt : {sorted(DEVELOPPEMENT - developpement)}"
    )


def test_les_versions_sont_figees():
    """
    Une publication doit se reconstruire à l'identique.

    `>=` laisse la construction choisir, donc deux images différentes pour la
    même étiquette git.
    """
    for fichier in ("requirements.txt", "requirements-dev.txt"):
        for ligne in _lire(fichier).splitlines():
            ligne = ligne.split("#", 1)[0].strip()
            if not ligne or ligne.startswith("-"):
                continue
            assert "==" in ligne, f"{fichier} : « {ligne} » n'est pas figée"


def test_le_dockerfile_n_installe_que_l_execution():
    """L'image ne doit pas installer le fichier de développement."""
    instructions = [
        ligne for ligne in _lire("Dockerfile").splitlines()
        if ligne.strip() and not ligne.lstrip().startswith("#")
    ]
    dockerfile = "\n".join(instructions)

    assert "requirements.txt" in dockerfile
    assert "requirements-dev.txt" not in dockerfile


def test_la_ci_installe_le_fichier_de_developpement():
    """Sans les outils de test, la suite ne peut pas tourner en CI."""
    for workflow in ("tests.yml", "release.yml"):
        contenu = _lire(os.path.join(".github", "workflows", workflow))
        assert "requirements-dev.txt" in contenu, f"{workflow} n'installe pas les outils de test"


def test_l_outil_docker_reste_desactive():
    """
    Décision de sécurité, pas d'un manque de dépendance (2026-08-12).

    `DockerTool` sait `run_container`, `stop_container` et `remove_container`.
    Depuis l'intérieur du conteneur de production, cela suppose de monter
    `/var/run/docker.sock` — c'est-à-dire de donner à un agent l'équivalent de
    root sur l'hôte : il lui suffirait de lancer un conteneur privilégié montant
    `/`. Le réactiver doit être une décision explicite, pas une régression.
    """
    import yaml

    with open(RACINE / "tools" / "tools.yaml", encoding="utf-8") as fichier:
        registre = yaml.safe_load(fichier)

    docker = next(outil for outil in registre["tools"] if outil["id"] == "docker")
    assert docker["enabled"] is False, (
        "L'outil Docker donne à un agent l'équivalent de root sur l'hôte. "
        "S'il doit être réactivé, que ce soit avec une décision écrite."
    )


def test_les_formats_du_corpus_sont_dans_l_image():
    """
    Le corpus sénégalais est fait de PDF, de DOCX et de tableaux.

    Sans ces paquets, l'ingestion refuse exactement les fichiers pour lesquels
    elle a été écrite — et le refus serait propre, donc silencieux.
    """
    execution = _declarees("requirements.txt")

    for paquet in ("pypdf", "python-docx", "openpyxl", "python-pptx", "markdown", "pytesseract"):
        assert paquet in execution, f"{paquet} manque aux dépendances d'exécution"


def test_le_binaire_ocr_accompagne_son_enveloppe():
    """
    `pytesseract` seul ne lit rien : c'est une enveloppe autour d'un binaire.

    Déclarer le paquet Python sans installer `tesseract-ocr` donnerait une
    capacité annoncée qui échoue à la première image — le contraire de ce que
    cette décision cherchait.
    """
    dockerfile = _lire("Dockerfile")

    assert "tesseract-ocr" in dockerfile
    # Les données françaises : reconnaître du français avec un modèle anglais
    # rend un texte lisible et faux, ce qui est pire qu'un échec.
    assert "tesseract-ocr-fra" in dockerfile


def test_scipy_n_est_plus_une_dependance():
    """
    ~40 Mo pour un lissage d'histogramme, remplacé par NumPy déjà présent.

    SciPy n'était d'ailleurs ni installé ni déclaré : la classification d'images
    tombait dans son `except` et rendait `[("unknown", 1.0)]`.
    """
    for fichier in ("requirements.txt", "requirements-dev.txt"):
        assert "scipy" not in _declarees(fichier)

    orphelins = _modules_tiers_non_installes(_modules_importes(SOURCES_EXECUTION))
    assert "scipy" not in orphelins, "scipy est encore importé quelque part"


def test_aucun_fichier_de_test_ne_partage_son_nom_de_base():
    """
    Deux fichiers de test homonymes cassent la collecte, pas un seul test.

    `tests/` n'a pas de `__init__.py`, donc pytest importe chaque fichier par
    son nom de base : deux `test_providers.py` dans deux répertoires produisent
    un `import file mismatch` qui **interrompt toute la suite**. Le défaut est
    déjà arrivé deux fois ici (`test_ingestion.py`, puis `test_providers.py`),
    et il ne se manifeste que lorsqu'on lance les deux répertoires ensemble —
    donc jamais pendant le développement d'un seul.
    """
    racine = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    vus = {}
    for dossier, _, fichiers in os.walk(racine):
        if "__pycache__" in dossier:
            continue
        for nom in fichiers:
            if not (nom.startswith("test_") and nom.endswith(".py")):
                continue
            chemin = os.path.relpath(os.path.join(dossier, nom), racine)
            assert nom not in vus, (
                f"« {nom} » existe deux fois : {vus.get(nom)} et {chemin}. "
                "Sans `__init__.py`, pytest les importe sous le même nom de "
                "module et interrompt la collecte de toute la suite."
            )
            vus[nom] = chemin
