"""
Style de travail et amélioration continue (VOLET 34, ch. 12).

Le VOLET 33 capturait le signal ; l'état des lieux du chapitre 01 a mesuré ce
qu'il en restait : *« feedback is captured, nothing turns it into preferences »*.
Ces tests portent sur les deux moitiés du pas manquant, et surtout sur ce que
chacune **refuse** de faire :

1. **`working_style`** — dériver une préférence de deux observations, la deviner
   pour quelqu'un qui n'a rien dit, ou lire un retour non consenti.
2. **`improvement`** — appeler « tendance » un écart calculé sur trois retours,
   ou comparer une période à une période vide.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.context import AgentContext  # noqa: E402
from src.training.feedback import Feedback, FeedbackKind, SQLiteFeedbackStore  # noqa: E402
from src.training.improvement import MINIMUM_PAR_FENETRE, measure  # noqa: E402
from src.training.working_style import (  # noqa: E402
    MINIMUM_OBSERVATIONS,
    derive,
)

JOUR = 86400


@pytest.fixture
def magasin(tmp_path):
    """Un magasin de retours vide, propre à chaque test."""
    return SQLiteFeedbackStore(str(tmp_path / "feedback.sqlite"))


def correction(
    magasin,
    reponse: str,
    corrige: str,
    subject: str = "awa",
    consent: bool = True,
    created_at=None,
) -> str:
    """Enregistre une réécriture d'utilisateur."""
    retour = Feedback(
        prompt="une question", response=reponse, correction=corrige,
        kind=FeedbackKind.CORRECTION, subject=subject, consent_to_train=consent,
    )
    if created_at is not None:
        retour.created_at = created_at
    return magasin.record(retour)


LONGUE = "Voici une réponse assez longue qui développe beaucoup le sujet. " * 5
COURTE = "Réponse brève et directe."


# ----------------------------------------------------------------------
# 1. Une préférence se dérive, elle ne s'invente pas
# ----------------------------------------------------------------------


def test_sans_retour_aucun_style_n_est_produit(magasin):
    """
    Le défaut est l'absence, pas une valeur par défaut : un style inventé
    ferait répondre la plateforme à une personne qui n'existe pas.
    """
    style = derive("awa", store=magasin)

    assert style.known is False
    assert style.preferences == []
    assert "Aucun retour consenti" in style.to_dict()["reason"]


def test_deux_observations_ne_font_pas_une_preference(magasin):
    """Le seuil est le cœur du module : en dessous, rien n'est affirmé."""
    for _ in range(MINIMUM_OBSERVATIONS - 1):
        correction(magasin, LONGUE, COURTE)

    style = derive("awa", store=magasin)

    assert style.preference("length") is None
    assert style.known is False


def test_trois_observations_concordantes_font_une_preference(magasin):
    for _ in range(MINIMUM_OBSERVATIONS):
        correction(magasin, LONGUE, COURTE)

    preference = derive("awa", store=magasin).preference("length")

    assert preference is not None
    assert preference.value == "shorter"
    assert preference.observations == MINIMUM_OBSERVATIONS


def test_une_preference_porte_les_retours_qui_la_soutiennent(magasin):
    """Une préférence doit pouvoir être remontée jusqu'aux textes qui l'ont produite."""
    identifiants = {correction(magasin, LONGUE, COURTE) for _ in range(3)}

    preference = derive("awa", store=magasin).preference("length")

    assert set(preference.evidence) == identifiants


def test_des_signaux_contradictoires_ne_donnent_pas_de_preference(magasin):
    """Ce n'est pas une préférence, c'est une hésitation."""
    for _ in range(3):
        correction(magasin, LONGUE, COURTE)
    for _ in range(3):
        correction(magasin, COURTE, LONGUE)

    assert derive("awa", store=magasin).preference("length") is None


def test_une_reecriture_de_longueur_voisine_ne_compte_pas(magasin):
    """Réécrire une phrase change le nombre de caractères sans exprimer un avis."""
    for _ in range(5):
        correction(magasin, "Une réponse de taille moyenne ici.",
                   "Une réponse de taille moyenne là.")

    assert derive("awa", store=magasin).preference("length") is None


def test_le_style_ne_lit_que_les_retours_consentis(magasin):
    """
    `feedback.py` pose la règle : sans consentement, un retour corrige *cette*
    réponse et rien d'autre. Un profil durable est « autre chose ».
    """
    for _ in range(5):
        correction(magasin, LONGUE, COURTE, consent=False)

    style = derive("awa", store=magasin)

    assert style.known is False
    assert style.feedback_considered == 0


def test_le_style_d_une_personne_ne_fuit_pas_vers_une_autre(magasin):
    """Fondre les retours produirait un « style moyen » que personne n'a demandé."""
    for _ in range(4):
        correction(magasin, LONGUE, COURTE, subject="awa")

    assert derive("awa", store=magasin).known is True
    assert derive("moussa", store=magasin).known is False


def test_une_mise_en_forme_ajoutee_par_la_personne_est_relevee(magasin):
    for _ in range(3):
        correction(magasin, "Voici la réponse en prose.",
                   "Voici la réponse :\n```py\nx = 1\n```")

    preference = derive("awa", store=magasin).preference("format")

    assert preference.value == "code_blocks"


def test_une_mise_en_forme_deja_presente_n_est_pas_comptee(magasin):
    """
    Sinon la mesure porterait sur ce que la plateforme fait déjà, et non sur ce
    que la personne veut.
    """
    for _ in range(4):
        correction(magasin, "Réponse :\n```py\nx = 1\n```",
                   "Réponse corrigée :\n```py\nx = 2\n```")

    assert derive("awa", store=magasin).preference("format") is None


def test_la_langue_des_corrections_est_relevee(magasin):
    for _ in range(3):
        correction(magasin, "Une réponse.",
                   "The answer is that you should not do this with that.")

    assert derive("awa", store=magasin).preference("language").value == "en"


def test_un_texte_trop_court_ne_tranche_aucune_langue(magasin):
    """Ce n'est pas un détecteur de langue, et il ne prétend pas l'être."""
    for _ in range(4):
        correction(magasin, "Une réponse plutôt longue à corriger ici.", "Non.")

    assert derive("awa", store=magasin).preference("language") is None


def test_les_indications_d_invite_sont_vides_sans_preference(magasin):
    assert derive("awa", store=magasin).prompt_hints() == ""


def test_les_indications_d_invite_reprennent_les_preferences(magasin):
    for _ in range(3):
        correction(magasin, LONGUE, COURTE)

    indications = derive("awa", store=magasin).prompt_hints()

    assert "plus brièvement" in indications


def test_un_magasin_en_panne_ne_produit_pas_de_style():
    """Une préférence dérivée d'une exception serait une préférence inventée."""
    class MagasinCasse:
        def list_feedback(self, **_):
            raise RuntimeError("base indisponible")

    style = derive("awa", store=MagasinCasse())

    assert style.known is False


# ----------------------------------------------------------------------
# 2. Le style atteint réellement les invites
# ----------------------------------------------------------------------


def test_le_contexte_applique_le_style_du_sujet(magasin, monkeypatch):
    """
    Sans cette intégration, le chapitre produirait un rapport de plus : le style
    doit modifier ce qui part vers le modèle.
    """
    for _ in range(3):
        correction(magasin, LONGUE, COURTE, subject="awa")
    monkeypatch.setattr("src.training.working_style.shared_feedback_store", lambda: magasin)

    contexte = AgentContext(request="question", agent_id="test", user_id="awa")

    assert "plus brièvement" in contexte.style_hints()


def test_sans_sujet_identifie_aucune_indication_n_est_ajoutee(magasin, monkeypatch):
    monkeypatch.setattr("src.training.working_style.shared_feedback_store", lambda: magasin)

    contexte = AgentContext(request="question", agent_id="test")

    assert contexte.style_hints() == ""


def test_le_style_n_est_derive_qu_une_fois_par_contexte(magasin, monkeypatch):
    """Le dériver à chaque invite lirait la base pour un résultat identique."""
    appels = []

    def compter(sujet, *args, **kwargs):
        appels.append(sujet)
        return derive(sujet, store=magasin)

    monkeypatch.setattr("src.training.working_style.derive", compter)
    contexte = AgentContext(request="question", agent_id="test", user_id="awa")

    contexte.style_hints()
    contexte.style_hints()

    assert appels == ["awa"]


def test_une_erreur_de_style_n_empeche_pas_de_repondre(monkeypatch):
    """Une panne du profil ne doit jamais coûter une génération."""
    def casse(*args, **kwargs):
        raise RuntimeError("magasin absent")

    monkeypatch.setattr("src.training.working_style.derive", casse)
    contexte = AgentContext(request="question", agent_id="test", user_id="awa")

    assert contexte.style_hints() == ""


# ----------------------------------------------------------------------
# 3. L'amélioration se mesure, ou ne se dit pas
# ----------------------------------------------------------------------


def _remplir(magasin, nombre: int, instant: float, kind=FeedbackKind.RATING, rating=3):
    """Enregistre des retours datés."""
    for _ in range(nombre):
        retour = Feedback(
            prompt="q", response="r", kind=kind, rating=rating,
            subject="awa", consent_to_train=True,
        )
        retour.created_at = instant
        magasin.record(retour)


def test_sans_periode_anterieure_il_n_y_a_pas_de_reference(magasin):
    """Il n'y a pas d'amélioration : il y a un premier point."""
    maintenant = time.time()
    _remplir(magasin, 40, maintenant - JOUR)

    rapport = measure(store=magasin, now=maintenant)

    assert rapport["status"] == "no_baseline"
    assert "pas de référence" in rapport["reason"]


def test_un_ecart_sur_trois_retours_n_est_pas_une_tendance(magasin):
    """Ni « stable », ni « en progrès » : les deux seraient tirés de rien."""
    maintenant = time.time()
    _remplir(magasin, 3, maintenant - 40 * JOUR)
    _remplir(magasin, 3, maintenant - JOUR)

    rapport = measure(store=magasin, now=maintenant)

    assert rapport["status"] == "insufficient_data"
    assert "deltas" not in rapport
    assert str(MINIMUM_PAR_FENETRE) in rapport["reason"]


def test_une_baisse_des_corrections_est_rapportee_comme_une_amelioration(magasin):
    maintenant = time.time()
    _remplir(magasin, 30, maintenant - 40 * JOUR, kind=FeedbackKind.CORRECTION)
    _remplir(magasin, 10, maintenant - 40 * JOUR)
    _remplir(magasin, 5, maintenant - JOUR, kind=FeedbackKind.CORRECTION)
    _remplir(magasin, 35, maintenant - JOUR)

    rapport = measure(store=magasin, now=maintenant)

    assert rapport["status"] == "measured"
    assert rapport["deltas"]["correction_rate"]["direction"] == "better"


def test_une_hausse_des_signalements_est_rapportee_comme_une_degradation(magasin):
    maintenant = time.time()
    _remplir(magasin, 40, maintenant - 40 * JOUR)
    _remplir(magasin, 20, maintenant - JOUR, kind=FeedbackKind.REPORT)
    _remplir(magasin, 20, maintenant - JOUR)

    rapport = measure(store=magasin, now=maintenant)

    assert rapport["deltas"]["report_rate"]["direction"] == "worse"


def test_un_ecart_sous_le_bruit_est_dit_inchange(magasin):
    """Sans cela, « 12,0 % contre 12,1 % » serait rapporté comme une dégradation."""
    maintenant = time.time()
    _remplir(magasin, 4, maintenant - 40 * JOUR, kind=FeedbackKind.CORRECTION)
    _remplir(magasin, 36, maintenant - 40 * JOUR)
    _remplir(magasin, 4, maintenant - JOUR, kind=FeedbackKind.CORRECTION)
    _remplir(magasin, 36, maintenant - JOUR)

    rapport = measure(store=magasin, now=maintenant)

    assert rapport["deltas"]["correction_rate"]["direction"] == "unchanged"


def test_la_note_moyenne_porte_sur_les_retours_notes(magasin):
    """
    Diviser par le total ferait baisser la moyenne à chaque retour sans note —
    une dégradation qui ne mesurerait que le silence.
    """
    maintenant = time.time()
    _remplir(magasin, 40, maintenant - 40 * JOUR, rating=4)
    _remplir(magasin, 30, maintenant - JOUR, rating=4)
    _remplir(magasin, 10, maintenant - JOUR, kind=FeedbackKind.REPORT, rating=None)

    rapport = measure(store=magasin, now=maintenant)

    assert rapport["current"]["mean_rating"] == 4.0
    assert rapport["current"]["rated"] == 30
    assert rapport["deltas"]["mean_rating"]["direction"] == "unchanged"


def test_un_magasin_en_panne_rend_indisponible_et_non_une_courbe():
    class MagasinCasse:
        def list_feedback(self, **_):
            raise RuntimeError("base indisponible")

    rapport = measure(store=MagasinCasse())

    assert rapport["status"] == "unavailable"


def test_l_invite_envoyee_au_modele_porte_les_preferences(magasin, monkeypatch):
    """
    La vérification qui compte : ce n'est pas `style_hints()` qui doit changer,
    c'est le texte qui part vers le modèle.
    """
    for _ in range(3):
        correction(magasin, LONGUE, COURTE, subject="awa")
    monkeypatch.setattr("src.training.working_style.shared_feedback_store", lambda: magasin)

    envoyees = []

    class ModeleFactice:
        """Moteur de modèles qui retient l'invite reçue."""

        def select_model_for_task(self, requirements):
            return type("Item", (), {"model_id": "modele-test"})()

        async def generate_text(self, item, prompt):
            envoyees.append(prompt)
            return "réponse"

    class RegistreFactice:
        """Registre ne portant que le moteur de modèles."""

        def try_get(self, nom):
            return ModeleFactice() if nom == "model" else None

    contexte = AgentContext(
        request="question", agent_id="test", user_id="awa", registry=RegistreFactice(),
    )

    resultat = contexte.generate("Explique la rotation des cultures.")

    assert resultat["status"] == "success"
    assert "plus brièvement" in envoyees[0]
    assert envoyees[0].endswith("Explique la rotation des cultures.")


def test_sans_preference_l_invite_part_inchangee(magasin, monkeypatch):
    """Une consigne de style inventée ajusterait la réponse à personne."""
    monkeypatch.setattr("src.training.working_style.shared_feedback_store", lambda: magasin)
    envoyees = []

    class ModeleFactice:
        def select_model_for_task(self, requirements):
            return type("Item", (), {"model_id": "modele-test"})()

        async def generate_text(self, item, prompt):
            envoyees.append(prompt)
            return "réponse"

    class RegistreFactice:
        def try_get(self, nom):
            return ModeleFactice() if nom == "model" else None

    contexte = AgentContext(
        request="question", agent_id="test", user_id="awa", registry=RegistreFactice(),
    )

    contexte.generate("Explique la rotation des cultures.")

    assert envoyees[0] == "Explique la rotation des cultures."
