"""
La boucle de délibération : générer, critiquer, reprendre, s'arrêter.

Ce qui est éprouvé ici n'est pas qu'un drapeau `reasoning` existe — c'est que
**le procédé change**. Une réponse fausse détectée est reprise ; une réponse
correcte n'est pas reprise ; et quand la reprise ne suffit pas, la réponse est
rendue **avec ses constats** au lieu d'être servie comme vérifiée.

Le budget est testé aussi durement que la correction : une boucle qui améliore
les réponses mais peut tourner sans fin n'est pas utilisable.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.reasoning import (  # noqa: E402
    BLOQUANT,
    BUDGET_EPUISE,
    GENERATION_IMPOSSIBLE,
    SIGNAL,
    VERIFIEE,
    consigne_de_reprise,
    critiquer,
    deliberer,
)


class Generateur:
    """
    Un générateur scripté : il rend les textes prévus, dans l'ordre.

    Il compte ses appels et retient les consignes reçues — c'est ce qui permet
    de vérifier qu'une reprise a **vraiment** eu lieu, et pas seulement qu'un
    champ a changé de valeur.
    """

    def __init__(self, *textes: str, modele: str = "modele-de-test"):
        self._textes = list(textes)
        self._modele = modele
        self.appels = 0
        self.consignes = []

    def __call__(self, consigne: str):
        self.consignes.append(consigne)
        texte = self._textes[min(self.appels, len(self._textes) - 1)]
        self.appels += 1
        return texte, self._modele


class TestLesControles:
    """Chaque contrôle, sur le cas qu'il existe pour attraper."""

    def test_un_calcul_faux_est_prouve_faux(self):
        constats = critiquer("Le total est 2 + 2 = 5 francs.")
        assert [c.code for c in constats] == ["arithmetic_error"]
        assert constats[0].gravite == BLOQUANT
        assert constats[0].details["computed"] == "4"

    def test_un_calcul_juste_ne_declenche_rien(self):
        assert critiquer("Le total est 2 + 2 = 4 francs.") == []

    def test_les_decimales_ne_produisent_pas_de_faux_positif(self):
        """
        `0.1 + 0.2` vaut `0.3` pour un lecteur. Le signaler comme faux serait
        l'erreur de virgule flottante que `Decimal` existe pour éviter — et le
        faux positif que personne ne pardonnerait à un vérificateur.
        """
        assert critiquer("On obtient 0.1 + 0.2 = 0.3 au total.") == []

    def test_une_division_par_zero_est_ignoree_et_non_signalee(self):
        """Un contrôle qui plante sur une entrée absurde bloquerait la réponse."""
        assert critiquer("La formule 4 / 0 = 0 est écrite ainsi.") == []

    def test_une_reponse_vide_est_bloquante(self):
        assert [c.code for c in critiquer("  ")] == ["empty_answer"]

    @pytest.mark.parametrize("breve", ["42", "Oui.", "Non, à Dakar."])
    def test_une_reponse_breve_n_est_pas_un_defaut(self, breve):
        """
        La première version de ce contrôle exigeait trois mots et relançait une
        génération sur « 42 ». Un vérificateur qui pénalise la concision coûte
        un appel de modèle et n'améliore rien : « vide » veut dire vide.
        """
        assert critiquer(breve) == []

    def test_une_certitude_sans_ancrage_est_bloquante(self):
        constats = critiquer(
            "Il est certain que la population dépasse vingt millions.",
            grounding_status="UNGROUNDED",
        )
        assert "unsupported_certainty" in [c.code for c in constats]

    def test_la_meme_certitude_ancree_passe(self):
        """
        Le contrôle juge **l'écart** entre le ton et l'ancrage, jamais le fond.
        Ancré, le même texte n'a plus rien à se reprocher.
        """
        constats = critiquer(
            "Il est certain que la population dépasse vingt millions.",
            grounding_status="GROUNDED",
        )
        assert "unsupported_certainty" not in [c.code for c in constats]

    def test_un_constat_verifie_suffit_a_soutenir_la_certitude(self):
        constats = critiquer(
            "Il est établi que le Sénégal compte quatorze régions.",
            evidence=[{"content": "Le Sénégal compte quatorze régions.", "verified": True}],
            grounding_status="NOT_CHECKED",
        )
        assert "unsupported_certainty" not in [c.code for c in constats]

    def test_une_affirmation_contredite_par_un_constat_est_bloquante(self):
        constats = critiquer(
            "Le Sénégal compte quatorze régions administratives.",
            evidence=[{
                "content": "Le Sénégal ne compte pas quatorze régions administratives.",
                "source": "corpus",
                "verified": True,
            }],
        )
        assert "contradicted_by_evidence" in [c.code for c in constats]

    def test_nommer_un_rouage_interne_est_un_signal_pas_un_blocage(self):
        """
        Relancer une génération entière pour un mot mal choisi coûte plus cher
        que le défaut. Le constat existe, il ne déclenche pas de reprise.
        """
        constats = critiquer("Le planner a décidé de chercher, puis j'ai répondu.")
        interne = next(c for c in constats if c.code == "internals_exposed")
        assert interne.gravite == SIGNAL
        assert interne.bloquant is False


class TestLaBoucle:
    """Le procédé, et le fait qu'il change quelque chose."""

    def test_une_bonne_reponse_n_est_pas_reprise(self):
        """Le cas majoritaire, et celui dont le coût compte le plus."""
        generateur = Generateur("Deux plus deux font quatre.")
        resultat = deliberer(generateur)
        assert generateur.appels == 1
        assert resultat.arret == VERIFIEE
        assert resultat.reprises == 0
        assert resultat.corrigee is False

    def test_une_reponse_fausse_est_reprise_et_corrigee(self):
        """Le cœur : la première réponse est fausse, la seconde est servie."""
        generateur = Generateur("Le total est 2 + 2 = 5.", "Le total est 2 + 2 = 4.")
        resultat = deliberer(generateur)
        assert generateur.appels == 2
        assert resultat.texte == "Le total est 2 + 2 = 4."
        assert resultat.arret == VERIFIEE
        assert resultat.corrigee is True
        assert resultat.constats_restants == []

    def test_la_reprise_dit_quoi_corriger_sans_renvoyer_le_texte(self):
        """
        Renvoyer au modèle son propre texte l'invite à le reformuler plutôt
        qu'à le refaire — et c'est ainsi qu'une erreur survit à sa correction.
        """
        generateur = Generateur("Le total est 2 + 2 = 5.", "Le total est 2 + 2 = 4.")
        deliberer(generateur)
        consigne = generateur.consignes[1]
        assert "2 + 2" in consigne and "4" in consigne
        assert "Le total est 2 + 2 = 5." not in consigne

    def test_une_erreur_qui_persiste_est_rendue_avec_ses_constats(self):
        """
        Le point d'honnêteté de toute la boucle : quand la reprise échoue, la
        réponse est servie **avec** ce qu'on lui reproche. Une boucle qui rend
        en silence une réponse qu'elle sait douteuse vaut moins que pas de
        boucle — elle ajoute une garantie qui n'existe pas.
        """
        generateur = Generateur("Le total est 2 + 2 = 5.")
        resultat = deliberer(generateur)
        assert generateur.appels == 2, "la reprise doit bien avoir été tentée"
        assert resultat.arret == BUDGET_EPUISE
        assert [c.code for c in resultat.constats_restants] == ["arithmetic_error"]
        assert resultat.corrigee is False

    def test_chaque_tentative_est_conservee_dans_la_trace(self):
        generateur = Generateur("Le total est 2 + 2 = 5.", "Le total est 2 + 2 = 4.")
        trace = deliberer(generateur).to_dict()
        assert len(trace["attempts"]) == 2
        assert trace["attempts"][0]["findings"][0]["code"] == "arithmetic_error"
        assert trace["attempts"][1]["findings"] == []
        assert trace["stop_reason"] == VERIFIEE


class TestLeBudget:
    """
    Une boucle qui améliore les réponses mais peut tourner sans fin n'est pas
    utilisable. Ces tests valent autant que ceux de la correction.
    """

    def test_le_nombre_de_generations_est_borne(self):
        generateur = Generateur("Le total est 2 + 2 = 5.")
        deliberer(generateur, reprises_max=3)
        assert generateur.appels == 4, "reprises_max + 1 générations au plus"

    def test_zero_reprise_n_eteint_pas_la_critique(self):
        """
        Un exploitant qui veut la latence minimale garde l'information : la
        réponse est rendue telle quelle, mais ce qu'on lui reproche est dit.
        """
        generateur = Generateur("Le total est 2 + 2 = 5.")
        resultat = deliberer(generateur, reprises_max=0)
        assert generateur.appels == 1
        assert [c.code for c in resultat.constats_restants] == ["arithmetic_error"]

    def test_un_delai_depasse_arrete_la_boucle(self, monkeypatch):
        """
        Le délai est vérifié **avant** une reprise, jamais au milieu d'une
        génération : interrompre un modèle en cours rendrait un texte tronqué.
        """
        from src.reasoning import deliberation as module

        horloge = iter([0.0, 0.0, 1.0, 500.0, 500.0, 500.0, 500.0])
        monkeypatch.setattr(module.time, "perf_counter", lambda: next(horloge, 500.0))

        generateur = Generateur("Le total est 2 + 2 = 5.")
        resultat = deliberer(generateur, reprises_max=5, delai_secondes=10.0)
        assert resultat.arret == module.DELAI_DEPASSE
        assert generateur.appels == 1, "aucune reprise après le dépassement"

    def test_une_panne_a_la_premiere_passe_remonte(self):
        """Il n'y a alors aucune réponse à rendre : c'est l'affaire de l'appelant."""
        def tombe(_consigne):
            raise RuntimeError("aucun fournisseur")

        with pytest.raises(RuntimeError):
            deliberer(tombe)

    def test_une_panne_en_reprise_conserve_la_tentative_precedente(self):
        """
        Perdre une réponse obtenue en essayant de l'améliorer serait une
        régression provoquée par le correcteur lui-même.
        """
        appels = {"n": 0}

        def instable(_consigne):
            appels["n"] += 1
            if appels["n"] == 1:
                return "Le total est 2 + 2 = 5.", "m"
            raise RuntimeError("le serveur a disparu")

        resultat = deliberer(instable)
        assert resultat.texte == "Le total est 2 + 2 = 5."
        assert resultat.arret == GENERATION_IMPOSSIBLE
        assert resultat.constats_restants


class TestLaConsigneDeReprise:
    """Ce qu'on dit au modèle pour qu'il fasse autrement."""

    def test_sans_consigne_utile_la_reprise_ne_dit_rien(self):
        constats = critiquer("Le planner a tout fait.")
        assert consigne_de_reprise(constats) == ""

    def test_la_consigne_interdit_de_parler_de_la_correction(self):
        """L'utilisateur a posé une question, pas demandé un journal de bord."""
        consigne = consigne_de_reprise(critiquer("Le total est 2 + 2 = 5."))
        assert "Do not mention this correction" in consigne


class TestLeChatDelibere:
    """
    Le point d'intégration. Une boucle qu'aucun chemin n'emprunte ne change
    rien pour personne — c'est le défaut exact corrigé au commit précédent
    sur le routage des modèles.
    """

    @staticmethod
    def _redacteur(*textes: str, reprises_max: int = 1):
        """Un rédacteur branché sur un moteur scripté."""
        from src.chat.response import RedacteurConversation

        sortie = list(textes)
        appels = {"n": 0}

        class MoteurScripte:
            """Un moteur qui rend les textes prévus, dans l'ordre."""

            async def generate_text_with_source(self, prompt, task_requirements, **_):
                texte = sortie[min(appels["n"], len(sortie) - 1)]
                appels["n"] += 1
                return texte, "modele-de-test"

        return RedacteurConversation(MoteurScripte(), reprises_max=reprises_max), appels

    def test_le_chat_reprend_une_reponse_fausse(self):
        from src.chat.response import ContexteReponse

        redacteur, appels = self._redacteur(
            "Le total est 2 + 2 = 5.", "Le total est 2 + 2 = 4."
        )
        finale = redacteur.rediger(ContexteReponse(message="Combien font deux et deux ?"))

        assert appels["n"] == 2
        assert finale.answer == "Le total est 2 + 2 = 4."
        assert finale.generated is True
        assert finale.deliberation["corrected"] is True
        assert finale.deliberation["stop_reason"] == VERIFIEE

    def test_le_chat_ne_reprend_pas_une_bonne_reponse(self):
        from src.chat.response import ContexteReponse

        redacteur, appels = self._redacteur("Deux et deux font quatre.")
        finale = redacteur.rediger(ContexteReponse(message="Combien font deux et deux ?"))

        assert appels["n"] == 1
        assert finale.deliberation["retries"] == 0

    def test_le_chat_rend_les_constats_qui_subsistent(self):
        """Servie quand même, mais jamais présentée comme vérifiée."""
        from src.chat.response import ContexteReponse

        redacteur, _ = self._redacteur("Le total est 2 + 2 = 5.")
        finale = redacteur.rediger(ContexteReponse(message="Combien font deux et deux ?"))

        assert finale.generated is True
        assert finale.deliberation["stop_reason"] == BUDGET_EPUISE
        assert finale.deliberation["remaining_findings"][0]["code"] == "arithmetic_error"

    def test_une_reponse_sans_generation_ne_porte_aucune_deliberation(self):
        """
        `None` et « délibération sans constat » ne disent pas la même chose. Une
        salutation ne passe par aucun modèle : elle ne doit pas se lire comme
        une réponse qui a traversé la critique sans encombre.
        """
        from src.chat.response import ContexteReponse

        redacteur, appels = self._redacteur("jamais appelé")
        finale = redacteur.rediger(ContexteReponse(
            message="bonjour",
            axes={"task_type": {"value": ["conversation"]}},
        ))

        assert appels["n"] == 0
        assert finale.generated is False
        assert finale.deliberation is None


class TestLeBanc:
    """
    Le banc d'essai des critiques — reproductible, et honnête sur ses trous.

    Il tourne ici, sans modèle et sans réseau. Ce qui est éprouvé n'est pas
    qu'il donne un bon score : c'est qu'il en donne un **vrai**.
    """

    def test_le_banc_tourne_et_rend_les_deux_taux(self):
        from src.reasoning.benchmark import executer

        mesure = executer()
        assert mesure["cases"] > 0
        assert mesure["detection_rate"] is not None
        assert mesure["false_alarm_rate"] is not None

    def test_aucune_fausse_alerte(self):
        """
        Le taux le plus important, et celui qu'on oublie de mesurer. Un critique
        qui signale tout atteint 100 % de détection et rend la boucle
        inutilisable : chaque réponse coûterait une reprise.
        """
        from src.reasoning.benchmark import executer

        mesure = executer()
        assert mesure["false_alarm_rate"] == 0.0, (
            f"des cas sains sont signalés à tort : {mesure['failures']}"
        )

    def test_le_banc_contient_des_cas_que_les_controles_ratent(self):
        """
        Un banc dont le score ne peut que monter n'est pas un banc. Ces cas
        portent de vraies erreurs qu'aucun contrôle n'attrape, et les retirer
        pour embellir le chiffre serait une fabrication.
        """
        from src.reasoning.benchmark import CAS

        assert [c for c in CAS if c.get("connu_rate")], (
            "le banc ne contient plus aucun cas connu comme raté"
        )

    def test_le_taux_de_detection_n_est_pas_parfait(self):
        """
        Conséquence du test précédent, mesurée plutôt que supposée. Si ce test
        tombe parce que la détection atteint 100 %, c'est que les contrôles se
        sont améliorés — ajoutez alors un cas plus dur au lieu de le supprimer.
        """
        from src.reasoning.benchmark import executer

        assert executer()["detection_rate"] < 1.0

    def test_un_taux_sur_zero_cas_n_est_pas_nul(self):
        """
        `None`, jamais `0`. Un taux sur zéro cas n'est pas nul : il n'est pas
        mesurable, et la plateforme applique déjà cette règle ailleurs.
        """
        from src.reasoning.benchmark import executer

        mesure = executer([{"id": "seul", "texte": "Tout va bien.", "attendu": None}])
        assert mesure["detection_rate"] is None
        assert mesure["false_alarm_rate"] == 0.0

    def test_le_rapport_montre_les_deux_taux_ensemble(self):
        """Publier la détection seule laisserait croire à un contrôle sans coût."""
        from src.reasoning.benchmark import rapport

        texte = rapport()
        assert "détection" in texte and "fausses alertes" in texte


class TestLeBudgetEstConfigurable:
    """L'exploitant règle le coût, il n'a pas à modifier le code."""

    def test_la_variable_d_environnement_est_lue(self, monkeypatch):
        from src.chat.response import _reprises_configurees

        monkeypatch.setenv("GALSEN_CHAT_MAX_RETRIES", "3")
        assert _reprises_configurees() == 3

    @pytest.mark.parametrize("valeur", ["", "beaucoup", "-1"])
    def test_une_valeur_invalide_retombe_sur_le_defaut(self, monkeypatch, valeur):
        """
        Une variable mal écrite qui désactiverait les reprises en silence serait
        découverte le jour où une réponse fausse est servie.
        """
        from src.chat.response import REPRISES_PAR_DEFAUT, _reprises_configurees

        monkeypatch.setenv("GALSEN_CHAT_MAX_RETRIES", valeur)
        assert _reprises_configurees() == REPRISES_PAR_DEFAUT
