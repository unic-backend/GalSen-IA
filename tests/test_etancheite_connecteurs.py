"""
Étanchéité : un courriel privé n'atteint aucun magasin partagé (phase 46.1).

Les phases précédentes ont fermé des portes une par une. Celle-ci fait
l'inverse : elle **cherche à faire fuiter**, en essayant chaque chemin
plausible qui mène d'un connecteur Google vers quelque chose que d'autres
peuvent lire.

Un trou réel a été trouvé en écrivant ces tests, et refermé :

`AgentContext.remember()` a pour défaut `agent_shared` — un magasin lu par tous
les agents — et posait `user_id=self.user_id`, qui vaut `None` quand personne ne
l'a renseigné. Un agent qui a lu une boîte et appelle `remember(corps)` y
déposait donc un contenu privé sans propriétaire, rendu par une recherche sans
filtre. Les trois autres chemins étaient fermés depuis le VOLET 40 ; celui-là ne
l'était pas, parce que la mémoire avait l'air isolée grâce à son `user_id` —
qui est un filtre facultatif, pas une frontière.

Ce que ces tests gardent : **quatre chemins essayés, quatre refusés**, et le
contenu introuvable après chaque tentative.
"""

import os
import sys

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.context import AgentContext  # noqa: E402
from src.connectors.google import CalendarConnector, DriveConnector, GmailConnector  # noqa: E402
from src.connectors.oauth import TokenStore, get_provider  # noqa: E402
from src.integration.engine_registry import EngineRegistry  # noqa: E402
from src.knowledge_engine.ingestion import DocumentIngestor  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.knowledge_engine.types import KnowledgeItem, KnowledgeSource, SourceCategory  # noqa: E402
from src.memory_engine.types import MemoryType  # noqa: E402
from src.security.isolation import IsolationError, Visibility, may_store  # noqa: E402
from src.storage import encryption  # noqa: E402
from src.tool.capabilities import DataScope  # noqa: E402

#: Un contenu privé reconnaissable. S'il apparaît dans un magasin partagé, la
#: chaîne a fui — et le chercher est plus sûr que de croire un booléen.
SECRET = "Rendez-vous vendredi 14h, dossier confidentiel n° 4471"
ACCES = "ya29.a0AfB-JETON-SECRET"


@pytest.fixture
def configure(monkeypatch):
    """Chiffrement et identifiants **factices**."""
    monkeypatch.setenv(encryption.KEY_VARIABLE, Fernet.generate_key().decode("ascii"))
    fournisseur = get_provider("google")
    monkeypatch.setenv(fournisseur.client_id_variable, "id-de-test")
    monkeypatch.setenv(fournisseur.client_secret_variable, "secret-de-test")
    monkeypatch.setenv(fournisseur.redirect_uri_variable, "https://exemple.test/retour")
    return fournisseur


@pytest.fixture
def connecteurs(configure):
    """Les trois connecteurs Google, un magasin partagé, « fatou » consentante."""
    magasin = TokenStore()
    trois = {}
    for classe in (GmailConnector, DriveConnector, CalendarConnector):
        connecteur = classe(configure, tokens=magasin)
        trois[connecteur.connector_id] = connecteur
    premier = trois["google_gmail"]
    depart = premier.begin("fatou")
    premier.complete(depart.pending.state, "code", {
        "access_token": ACCES, "expires_in": 3599,
        "scope": " ".join(configure.allowed_scopes),
    })
    return trois


@pytest.fixture
def base():
    """Une base de connaissance vide."""
    return KnowledgeManagerImpl()


@pytest.fixture
def contexte():
    """Un contexte d'agent sur des moteurs neufs."""
    return AgentContext(
        request="résume ma boîte", agent_id="organizer", registry=EngineRegistry()
    )


def _source_privee():
    """Une source de connaissance issue d'un connecteur privé."""
    return KnowledgeSource(
        id="s", type="connector", location="google_gmail",
        data_scope=DataScope.USER_PRIVATE, subject="fatou",
    )


# ----------------------------------------------------------------------
# Les quatre chemins, essayés puis refusés
# ----------------------------------------------------------------------

def test_chemin_1_la_base_de_connaissance_directement(base):
    """`KnowledgeManager.add_knowledge` — fermé au VOLET 40."""
    with pytest.raises(IsolationError, match="magasin partagé"):
        base.add_knowledge(KnowledgeItem(content=SECRET, source=_source_privee()))

    assert base.search_knowledge("4471", limit=50) == []


def test_chemin_2_la_base_par_un_agent(contexte):
    """`AgentContext.add_knowledge` — fermé au VOLET 40."""
    with pytest.raises(IsolationError):
        contexte.add_knowledge(
            SECRET, data_scope=DataScope.USER_PRIVATE, subject="fatou"
        )

    assert contexte.search_knowledge("4471") == []


def test_chemin_3_la_base_par_l_ingestion_de_fichier(base, tmp_path):
    """`DocumentIngestor.ingest_file` — fermé au VOLET 40, avant l'ouverture."""
    fichier = tmp_path / "drive.txt"
    fichier.write_text(SECRET * 20, encoding="utf-8")

    with pytest.raises(IsolationError):
        DocumentIngestor(base).ingest_file(
            str(fichier), title="Fichier du Drive",
            source_category=SourceCategory.UNKNOWN,
            data_scope=DataScope.USER_PRIVATE, owner="fatou",
        )

    assert base.search_knowledge("4471", limit=50) == []


@pytest.mark.parametrize("type_partage", ["agent_shared", "knowledge"])
def test_chemin_4_la_memoire_partagee_par_un_agent(contexte, type_partage):
    """
    **Le trou trouvé en écrivant ce fichier.** Le défaut de `remember` est
    `agent_shared`, et le `user_id` posé valait `None` : le contenu privé
    devenait commun et sans propriétaire.
    """
    with pytest.raises(IsolationError, match="magasin partagé"):
        contexte.remember(
            SECRET, memory_type=type_partage,
            data_scope=DataScope.USER_PRIVATE, subject="fatou",
        )

    assert contexte.recall("4471") == []


def test_chemin_4bis_la_memoire_sans_proprietaire_nomme(contexte):
    """
    Une donnée privée sans sujet n'est protégeable par personne. La refuser
    vaut mieux que de l'attribuer à « quelqu'un ».
    """
    with pytest.raises(IsolationError, match="obligatoire"):
        contexte.remember(
            SECRET, memory_type="long_term", data_scope=DataScope.USER_PRIVATE
        )

    assert contexte.recall("4471") == []


# ----------------------------------------------------------------------
# Ce qui reste possible : isoler n'est pas interdire
# ----------------------------------------------------------------------

def test_la_memoire_privee_d_une_personne_reste_possible(contexte):
    """La donnée a un endroit où aller, et il porte son nom."""
    identifiant = contexte.remember(
        SECRET, memory_type="long_term",
        data_scope=DataScope.USER_PRIVATE, subject="fatou",
    )

    assert identifiant
    item = contexte.registry.get("memory").get_memory(identifiant)
    assert item.user_id == "fatou"


def test_le_proprietaire_vient_de_la_source_pas_du_contexte():
    """
    `self.user_id` peut être `None`, ou être quelqu'un d'autre que le titulaire
    de la boîte. Le sujet de la source prime.
    """
    contexte = AgentContext(
        request="x", agent_id="organizer", registry=EngineRegistry(), user_id="moussa"
    )

    identifiant = contexte.remember(
        SECRET, memory_type="long_term",
        data_scope=DataScope.USER_PRIVATE, subject="fatou",
    )

    item = contexte.registry.get("memory").get_memory(identifiant)
    assert item.user_id == "fatou"


def test_une_memorisation_publique_ne_change_pas(contexte):
    """Aucune régression : le chemin existant reste ouvert, défaut compris."""
    identifiant = contexte.remember("Le mil est cultivé au Sénégal.")

    assert identifiant
    assert contexte.recall("mil")


def test_les_types_partages_sont_nommes_et_non_devines():
    """
    Deux le sont par définition. Les deviner par convention de nom aurait
    manqué le prochain type ajouté.
    """
    assert MemoryType.AGENT_SHARED.shared is True
    assert MemoryType.KNOWLEDGE.shared is True
    for autre in (MemoryType.SHORT_TERM, MemoryType.LONG_TERM,
                  MemoryType.SESSION, MemoryType.WORKSPACE):
        assert autre.shared is False, autre


# ----------------------------------------------------------------------
# La chaîne réelle : d'un connecteur jusqu'au refus
# ----------------------------------------------------------------------

def test_ce_qu_un_connecteur_rend_ne_passe_aucune_frontiere(connecteurs):
    """
    Vérifié sur les trois connecteurs réels, par leur contrat — l'appelant ne
    choisit pas la propriété de ce qu'ils rendent.
    """
    for identifiant, connecteur in connecteurs.items():
        proprietaire = connecteur.data_contract.owner_of("fatou")
        autorise, _ = may_store(proprietaire, Visibility.SHARED)
        assert autorise is False, identifiant


def test_un_corps_de_courriel_lu_puis_verse_est_refuse(connecteurs, base):
    """
    Le scénario complet et hostile : lire un message, puis tenter de le mettre
    dans la base commune. C'est le chemin qu'un agent mal écrit prendrait.
    """
    import base64

    gmail = connecteurs["google_gmail"]
    lien = gmail.binding("fatou")
    lu = gmail.read_message(lien, {
        "id": "m1", "payload": {
            "mimeType": "text/plain",
            "body": {"data": base64.urlsafe_b64encode(SECRET.encode()).decode()},
            "headers": [],
        },
    })

    with pytest.raises(IsolationError):
        base.add_knowledge(KnowledgeItem(content=lu["body"], source=_source_privee()))

    assert base.search_knowledge("4471", limit=50) == []


def test_le_secret_reste_introuvable_apres_toutes_les_tentatives(contexte, base):
    """
    La vérification qui compte : après chaque refus, chercher le contenu ne
    doit rien rendre. Croire un booléen ne suffit pas.
    """
    tentatives = [
        lambda: base.add_knowledge(
            KnowledgeItem(content=SECRET, source=_source_privee())
        ),
        lambda: contexte.add_knowledge(
            SECRET, data_scope=DataScope.USER_PRIVATE, subject="fatou"
        ),
        lambda: contexte.remember(
            SECRET, memory_type="agent_shared",
            data_scope=DataScope.USER_PRIVATE, subject="fatou",
        ),
        lambda: contexte.remember(
            SECRET, memory_type="knowledge",
            data_scope=DataScope.USER_PRIVATE, subject="fatou",
        ),
    ]

    for tentative in tentatives:
        with pytest.raises(IsolationError):
            tentative()

    assert base.search_knowledge("4471", limit=50) == []
    assert base.search_knowledge("confidentiel", limit=50) == []
    assert contexte.recall("4471") == []
    assert contexte.search_knowledge("confidentiel") == []


def test_le_refus_d_isolation_ne_se_confond_pas_avec_une_panne(contexte):
    """
    `remember` rend `None` quand le moteur est absent. Rendre `None` ici aussi
    ferait passer une fuite pour un incident passager, et l'appelant
    réessaierait — c'est la même règle que pour la connaissance.
    """
    with pytest.raises(IsolationError):
        contexte.remember(
            SECRET, memory_type="agent_shared",
            data_scope=DataScope.USER_PRIVATE, subject="fatou",
        )
