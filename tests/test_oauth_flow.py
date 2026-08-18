"""
Le flux OAuth 2.0 : ce qu'il construit, et ce qu'il refuse (phase 43.1).

**Aucun identifiant Google n'existe dans cet environnement, et aucun n'est
fabriqué.** C'est pourquoi ces tests posent eux-mêmes des variables factices :
ils vérifient la mécanique, pas un accès. Le verdict réel de la plateforme reste
`NOT_CONFIGURED`, et un test le vérifie explicitement.

Ce que ces tests gardent :

1. **PKCE, et seulement `S256`.** `plain` ne protège de rien qu'un lecteur de la
   requête ne voie déjà.
2. **Un `state` sert une fois et périme.** Le rejouer ne retrouve rien.
3. **L'URI de retour vient de l'environnement**, jamais d'une requête : sinon
   c'est une redirection ouverte, et le code part chez qui l'a demandée.
4. **Une portée non déclarée est refusée** avant qu'aucune URL ne soit
   construite — demander trop se fait une fois, au moment où l'on clique oui.
5. **Aucun mot de passe nulle part.** Le flux existe pour que la plateforme n'en
   voie jamais ; une garde lit le source du paquet pour le tenir.
"""

import ast
import base64
import hashlib
import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.connectors.oauth import (  # noqa: E402
    FlowRefused,
    OAuthNotConfigured,
    PendingStore,
    ProviderUnknown,
    ScopeRefused,
    challenge_for,
    configuration_report,
    flow_report,
    generate_state,
    generate_verifier,
    get_provider,
    load_providers,
    start_authorization,
    token_request,
)
from src.connectors.oauth.flow import DUREE_DE_VIE_SECONDES, METHODE_DE_DEFI  # noqa: E402

PAQUET = pathlib.Path(__file__).resolve().parent.parent / "src" / "connectors" / "oauth"
LECTURE_GMAIL = "https://www.googleapis.com/auth/gmail.readonly"


@pytest.fixture
def google():
    """Le fournisseur Google, tel que la configuration du dépôt le déclare."""
    return get_provider("google")


@pytest.fixture
def configure(monkeypatch, google):
    """
    Des identifiants **factices**, posés par le test.

    Ils ne valent rien et n'ouvrent rien : ils permettent de vérifier que l'URL
    est bien formée, ce qui serait invérifiable autrement.
    """
    monkeypatch.setenv(google.client_id_variable, "id-client-de-test")
    monkeypatch.setenv(google.client_secret_variable, "secret-de-test")
    monkeypatch.setenv(google.redirect_uri_variable, "https://exemple.test/retour")
    return google


# ----------------------------------------------------------------------
# 1. L'état réel de cet environnement
# ----------------------------------------------------------------------

def test_aucun_fournisseur_n_est_configure_ici(monkeypatch, google):
    """
    Le verdict honnête, et il est publié : `IMPLEMENTED` + `NOT_CONFIGURED`.
    Les variables manquantes sont nommées ; aucune valeur n'est inventée.
    """
    for variable in (
        google.client_id_variable, google.client_secret_variable,
        google.redirect_uri_variable,
    ):
        monkeypatch.delenv(variable, raising=False)

    rapport = configuration_report()

    assert "google" in rapport["not_configured"]
    assert rapport["configured"] == []
    detail = next(f for f in rapport["providers"] if f["id"] == "google")
    assert detail["missing_variables"] == [
        google.client_id_variable, google.client_secret_variable,
        google.redirect_uri_variable,
    ]


def test_sans_identifiants_aucune_url_n_est_construite(monkeypatch, google):
    """
    Mieux vaut ne rien construire qu'une URL incomplète : une personne la
    suivrait quand même.
    """
    monkeypatch.delenv(google.client_id_variable, raising=False)

    with pytest.raises(OAuthNotConfigured, match=google.client_id_variable):
        start_authorization(google, "fatou", [LECTURE_GMAIL], PendingStore())


def test_le_rapport_ne_publie_aucune_valeur_de_secret(configure):
    """Un rapport de configuration finit dans une réponse d'API."""
    rapport = configuration_report()

    assert "secret-de-test" not in str(rapport)
    assert "id-client-de-test" not in str(rapport)
    detail = next(f for f in rapport["providers"] if f["id"] == "google")
    assert detail["configured"] is True


def test_un_fournisseur_inconnu_n_est_pas_devine():
    """Un point d'accès inventé enverrait une personne consentir ailleurs."""
    with pytest.raises(ProviderUnknown, match="absent du registre"):
        get_provider("microsoft")


def test_un_registre_absent_rend_la_couche_muette(tmp_path):
    """Perdre le fichier ne doit pas ouvrir de chemin par défaut."""
    assert load_providers(str(tmp_path / "absent.yaml")) == {}


def test_le_registre_nomme_la_source_qui_fait_autorite(google):
    """
    Les points d'accès sont une **copie** de ce que le fournisseur publie.
    Nommer le document d'origine est ce qui permet de la confronter.
    """
    assert google.discovery_url.startswith("https://")
    assert "well-known" in google.discovery_url


# ----------------------------------------------------------------------
# 2. PKCE
# ----------------------------------------------------------------------

def test_le_defi_est_bien_le_sha256_du_verificateur():
    """Vérifié par le calcul, pas par la confiance dans le nom de la fonction."""
    verificateur = generate_verifier()

    attendu = base64.urlsafe_b64encode(
        hashlib.sha256(verificateur.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")

    assert challenge_for(verificateur) == attendu


def test_le_verificateur_respecte_la_longueur_de_la_rfc():
    """Entre 43 et 128 caractères — plus court, le défi se force."""
    for _ in range(20):
        verificateur = generate_verifier()
        assert 43 <= len(verificateur) <= 128


def test_deux_verificateurs_ne_se_ressemblent_jamais():
    """Un vérificateur prévisible annule PKCE."""
    tires = {generate_verifier() for _ in range(200)}

    assert len(tires) == 200


def test_un_verificateur_trop_court_est_refuse():
    """La RFC fixe un plancher ; l'accepter quand même serait le vider."""
    with pytest.raises(FlowRefused, match="43"):
        challenge_for("court")


def test_seule_la_methode_s256_est_utilisee(configure):
    """`plain` est dans la RFC et ne protège de rien."""
    depart = start_authorization(configure, "fatou", [LECTURE_GMAIL], PendingStore())

    assert f"code_challenge_method={METHODE_DE_DEFI}" in depart.url
    assert "plain" not in depart.url


def test_le_verificateur_ne_part_jamais_dans_l_url(configure):
    """Seul son défi part. C'est tout le mécanisme."""
    store = PendingStore()

    depart = start_authorization(configure, "fatou", [LECTURE_GMAIL], store)

    assert depart.pending.verifier not in depart.url
    assert challenge_for(depart.pending.verifier) in depart.url


def test_le_verificateur_n_apparait_pas_dans_la_serialisation(configure):
    """Le publier reviendrait à annuler PKCE."""
    depart = start_authorization(configure, "fatou", [LECTURE_GMAIL], PendingStore())

    serialise = str(depart.pending.as_dict())

    assert depart.pending.verifier not in serialise
    assert "verifier" not in serialise


# ----------------------------------------------------------------------
# 3. L'état anti-rejeu
# ----------------------------------------------------------------------

def test_un_etat_ne_sert_qu_une_fois(configure):
    """Le rejouer ne doit rien retrouver."""
    store = PendingStore()
    depart = start_authorization(configure, "fatou", [LECTURE_GMAIL], store)

    store.consume(depart.pending.state)

    with pytest.raises(FlowRefused):
        store.consume(depart.pending.state)


def test_un_etat_perime_est_refuse(configure):
    """Un code intercepté hier ne doit rien valoir demain."""
    store = PendingStore()
    depart = start_authorization(configure, "fatou", [LECTURE_GMAIL], store)

    plus_tard = depart.pending.created_at + DUREE_DE_VIE_SECONDES + 1

    with pytest.raises(FlowRefused):
        store.consume(depart.pending.state, now=plus_tard)


def test_un_etat_inconnu_et_un_etat_perime_rendent_le_meme_message(configure):
    """Les distinguer renseignerait qui essaie."""
    store = PendingStore()
    depart = start_authorization(configure, "fatou", [LECTURE_GMAIL], store)
    plus_tard = depart.pending.created_at + DUREE_DE_VIE_SECONDES + 1

    with pytest.raises(FlowRefused) as perime:
        store.consume(depart.pending.state, now=plus_tard)
    with pytest.raises(FlowRefused) as inconnu:
        store.consume("jamais-vu")

    assert str(perime.value) == str(inconnu.value)


def test_deux_etats_ne_se_ressemblent_jamais():
    """Un `state` devinable est un `state` inutile."""
    assert len({generate_state() for _ in range(200)}) == 200


def test_les_demandes_perimees_se_purgent(configure):
    """Une demande de dix minutes ne doit pas s'accumuler indéfiniment."""
    store = PendingStore()
    depart = start_authorization(configure, "fatou", [LECTURE_GMAIL], store)

    retires = store.purge(now=depart.pending.created_at + DUREE_DE_VIE_SECONDES + 1)

    assert retires == 1
    assert len(store) == 0


# ----------------------------------------------------------------------
# 4. Les portées et le sujet
# ----------------------------------------------------------------------

def test_une_portee_non_declaree_est_refusee(configure):
    """
    Le mode d'échec propre à OAuth : demander trop, une fois, au moment où la
    personne est le plus susceptible de cliquer oui.
    """
    with pytest.raises(ScopeRefused, match="non déclarée"):
        start_authorization(
            configure, "fatou",
            ["https://www.googleapis.com/auth/gmail.modify"],
            PendingStore(),
        )


def test_le_refus_de_portee_arrive_avant_toute_construction_d_url(configure):
    """Rien ne doit être enregistré ni construit pour une demande refusée."""
    store = PendingStore()

    with pytest.raises(ScopeRefused):
        start_authorization(configure, "fatou", ["portee.inventee"], store)

    assert len(store) == 0


def test_une_demande_sans_portee_est_refusee(configure):
    """Un écran de consentement sans objet ne s'interprète pas."""
    with pytest.raises(ScopeRefused, match="aucune portée"):
        start_authorization(configure, "fatou", [], PendingStore())


def test_une_demande_sans_sujet_est_refusee(configure):
    """Un consentement appartient à quelqu'un."""
    with pytest.raises(FlowRefused, match="sans sujet"):
        start_authorization(configure, "  ", [LECTURE_GMAIL], PendingStore())


def test_les_portees_declarees_sont_toutes_en_lecture_seule():
    """
    Moindre privilège, mesuré sur la configuration réelle : la vague II lit,
    elle n'écrit pas. Le jour où une portée d'écriture entrera, ce test le dira.
    """
    google = get_provider("google")

    ecritures = [p for p in google.allowed_scopes if not p.endswith(".readonly")]

    assert ecritures == [], f"Portées non lecture seule : {ecritures}"


# ----------------------------------------------------------------------
# 5. L'échange du code
# ----------------------------------------------------------------------

def test_la_requete_d_echange_porte_le_verificateur(configure):
    """C'est lui qui prouve que celui qui échange est celui qui a demandé."""
    store = PendingStore()
    depart = start_authorization(configure, "fatou", [LECTURE_GMAIL], store)

    requete = token_request(configure, "code-retourne", depart.pending)

    assert requete["data"]["code_verifier"] == depart.pending.verifier
    assert requete["data"]["grant_type"] == "authorization_code"
    assert requete["url"] == configure.token_endpoint


def test_l_uri_de_retour_vient_de_l_environnement(configure):
    """Une URI choisie par l'appelant est une redirection ouverte."""
    store = PendingStore()
    depart = start_authorization(configure, "fatou", [LECTURE_GMAIL], store)
    requete = token_request(configure, "code", depart.pending)

    assert requete["data"]["redirect_uri"] == "https://exemple.test/retour"
    assert "exemple.test" in depart.url


def test_un_code_vide_n_est_pas_echange(configure):
    """Rien à échanger n'est pas une requête à faire."""
    store = PendingStore()
    depart = start_authorization(configure, "fatou", [LECTURE_GMAIL], store)

    with pytest.raises(FlowRefused, match="vide"):
        token_request(configure, "   ", depart.pending)


def test_aucun_appel_reseau_n_est_fait(configure):
    """
    La requête est **construite, pas envoyée**. Aucun module réseau n'est
    importé par ce paquet — vérifié sur les imports, pas sur l'intention.
    """
    interdits = {"requests", "httpx", "urllib.request", "http.client", "aiohttp"}
    trouves = set()

    for chemin in sorted(PAQUET.glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                trouves |= {alias.name for alias in noeud.names}
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                trouves.add(noeud.module)

    assert trouves & interdits == set(), f"Modules réseau importés : {trouves & interdits}"


# ----------------------------------------------------------------------
# 6. Aucun mot de passe
# ----------------------------------------------------------------------

def _identifiants_du_code(chemin):
    """
    Retourne les noms que le **code** manipule : variables, attributs,
    arguments, et clés de dictionnaire littérales.

    Les commentaires et les docstrings sont ignorés à dessein. Une première
    version de cette garde comparait le texte brut et exemptait tout fichier
    contenant la phrase « n'en voie jamais » — ce qui la rendait vide pour
    `flow.py`, dont la docstring porte cette phrase. Une garde exemptée par sa
    propre explication ne garde rien.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    docstrings = {
        noeud.body[0].value
        for noeud in ast.walk(arbre)
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef))
        and noeud.body
        and isinstance(noeud.body[0], ast.Expr)
        and isinstance(noeud.body[0].value, ast.Constant)
    }

    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name):
            yield noeud.id
        elif isinstance(noeud, ast.Attribute):
            yield noeud.attr
        elif isinstance(noeud, ast.arg):
            yield noeud.arg
        elif isinstance(noeud, (ast.FunctionDef, ast.ClassDef)):
            yield noeud.name
        elif (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                and noeud not in docstrings):
            yield noeud.value


def test_le_paquet_ne_connait_aucun_mot_de_passe():
    """
    Tout l'objet de ce flux est que la plateforme n'en voie jamais. Vérifié sur
    l'arbre syntaxique : ni champ, ni paramètre, ni clé de dictionnaire.
    """
    interdits = ("password", "passwd", "mot_de_passe")
    fautes = []

    for chemin in sorted(PAQUET.glob("*.py")):
        for nom in _identifiants_du_code(chemin):
            minuscule = str(nom).lower()
            for mot in interdits:
                if mot in minuscule:
                    fautes.append(f"{chemin.name} → {nom}")

    assert fautes == [], f"Mot de passe manipulé par le code : {fautes}"


def test_la_garde_du_mot_de_passe_attrape_une_vraie_faute(tmp_path):
    """
    Une garde qu'on n'a jamais vue échouer ne prouve rien — d'autant que la
    première version de celle-ci s'exemptait elle-même.
    """
    fautif = tmp_path / "fautif.py"
    fautif.write_text(
        '"""Ce flux ne demande jamais de mot de passe."""\n'
        "def echanger(password):\n"
        "    return {'password': password}\n",
        encoding="utf-8",
    )

    noms = [
        nom for nom in _identifiants_du_code(fautif)
        if "password" in str(nom).lower()
    ]

    assert noms, "La garde ne détecte pas un mot de passe manipulé"


def test_le_flux_publie_ce_qu_il_refuse():
    """Ce qu'un lecteur doit pouvoir vérifier sans lire le code."""
    rapport = flow_report()

    assert rapport["pkce"] == "S256"
    assert rapport["state_ttl_seconds"] == DUREE_DE_VIE_SECONDES
    refus = " ".join(rapport["refuses"] + rapport["never"])
    assert "plain" in refus
    assert "redirection ouverte" in refus
    assert "mot de passe" in refus


def test_les_variables_attendues_sont_documentees():
    """
    Le garde-fou de `.env.example` cherche des littéraux dans `src/` ; ces
    noms-là viennent de la configuration, donc il ne peut pas les voir. Sans ce
    test, le propriétaire ne saurait pas quoi renseigner.
    """
    racine = pathlib.Path(__file__).resolve().parent.parent
    exemple = (racine / ".env.example").read_text(encoding="utf-8")

    for fournisseur in load_providers().values():
        for variable in (
            fournisseur.client_id_variable,
            fournisseur.client_secret_variable,
            fournisseur.redirect_uri_variable,
        ):
            assert f"{variable}=" in exemple, f"{variable} absente de .env.example"


def test_env_example_ne_porte_aucune_valeur_d_identifiant():
    """Un fichier d'exemple commité ne doit jamais contenir de vraie valeur."""
    racine = pathlib.Path(__file__).resolve().parent.parent
    exemple = (racine / ".env.example").read_text(encoding="utf-8")

    for ligne in exemple.splitlines():
        if ligne.startswith("GALSEN_OAUTH_"):
            assert ligne.endswith("="), f"Valeur renseignée : {ligne}"
