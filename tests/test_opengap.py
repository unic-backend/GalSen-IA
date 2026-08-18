"""
Tests de l'interopérabilité OpenGAP (ADR-023).

Trois choses sont vérifiées ici, et elles répondent à trois questions
différentes.

1. **La spécification est respectée.** Un manifeste que nous produisons doit
   être lisible par un autre outil, donc les contraintes du format sont
   contrôlées, pas supposées.
2. **Lire un agent étranger est sans effet.** C'est la raison d'être de cette
   couche : intégrer du travail publié par d'autres sans leur donner la main
   sur la plateforme. Un dossier hostile ne doit rien exécuter, rien
   télécharger, et rien écrire hors de sa destination.
3. **L'export livré ne dérive pas.** Les dossiers de `interop/opengap/` sont
   versionnés. Si le registre change et que l'export n'est pas refait, les
   fichiers publiés décrivent des agents qui n'existent plus — le test
   l'attrape ici plutôt qu'un utilisateur plus tard.
"""

import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.interop.opengap import (  # noqa: E402
    FICHIER_AME,
    FICHIER_MANIFESTE,
    SPEC_VERSION,
    TAILLE_MAX_FICHIER,
    OpenGAPAgent,
    OpenGAPError,
    depuis_entree_registre,
    ecrire_agent,
    exporter_registre,
    lire_agent,
    nom_opengap,
    valider_manifeste,
)
from src.version import __version__  # noqa: E402

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REGISTRE = os.path.join(RACINE, "agents", "registry.yaml")
EXPORT_LIVRE = os.path.join(RACINE, "interop", "opengap")


def _agent(**remplacements) -> OpenGAPAgent:
    """Construit un agent valide, modifiable champ par champ."""
    base = {
        "name": "agent-essai",
        "version": "1.2.3",
        "description": "Un agent d'essai.",
        "soul": "# Essai\n\nIdentité de l'agent d'essai.\n",
    }
    base.update(remplacements)
    return OpenGAPAgent(**base)


class TestValidation:
    """Les contraintes du format sont contrôlées, jamais supposées."""

    def test_un_manifeste_correct_ne_produit_aucune_faute(self):
        """Le cas nominal doit passer, sinon tout le reste est du bruit."""
        assert valider_manifeste(_agent().to_manifest()) == []

    @pytest.mark.parametrize("nom", ["Reviewer", "code_reviewer", "1er", "", "agent!"])
    def test_un_nom_hors_kebab_case_est_refuse(self, nom):
        """Le nom sert d'identifiant partagé entre outils : il ne se négocie pas."""
        fautes = valider_manifeste({"name": nom, "version": "1.0.0", "description": "x"})
        assert any("name" in faute for faute in fautes), fautes

    @pytest.mark.parametrize("version", ["1.0", "v1.0.0", "latest", "1.0.0.0"])
    def test_une_version_non_semantique_est_refusee(self, version):
        """Sans version comparable, aucune dépendance entre agents n'est possible."""
        fautes = valider_manifeste({"name": "a", "version": version, "description": "x"})
        assert any("version" in faute for faute in fautes), fautes

    @pytest.mark.parametrize("version", ["0.1.0", "1.2.3", "1.0.0-rc.1", "1.0.0+build.5"])
    def test_les_versions_semantiques_valides_passent(self, version):
        """Préversions et métadonnées de compilation font partie du format."""
        assert valider_manifeste({"name": "a", "version": version, "description": "x"}) == []

    def test_une_description_vide_est_refusee(self):
        """Un agent sans description n'est pas choisissable par un humain."""
        fautes = valider_manifeste({"name": "a", "version": "1.0.0", "description": "   "})
        assert any("description" in faute for faute in fautes), fautes

    def test_toutes_les_fautes_sont_rendues_ensemble(self):
        """Rendre une faute à la fois ferait corriger un fichier en dix passes."""
        fautes = valider_manifeste({"name": "Mauvais", "version": "1.0", "description": ""})
        assert len(fautes) == 3, fautes

    def test_un_manifeste_qui_n_est_pas_un_objet_est_refuse(self):
        """Un YAML valide n'est pas forcément un manifeste."""
        assert valider_manifeste(["une", "liste"])

    def test_metadata_refuse_les_valeurs_composees(self):
        """La spécification limite `metadata` aux valeurs simples."""
        fautes = valider_manifeste({
            "name": "a", "version": "1.0.0", "description": "x",
            "metadata": {"bon": 1, "mauvais": {"imbrique": True}},
        })
        assert any("metadata" in faute and "mauvais" in faute for faute in fautes), fautes

    def test_une_temperature_hors_bornes_est_refusee(self):
        """0.0–2.0 : au-delà, le service refuserait la requête à l'exécution."""
        fautes = valider_manifeste({
            "name": "a", "version": "1.0.0", "description": "x",
            "model": {"constraints": {"temperature": 3.5}},
        })
        assert any("temperature" in faute for faute in fautes), fautes

    def test_un_booleen_ne_passe_pas_pour_un_nombre(self):
        """`True` est un `int` en Python : sans garde, il passerait pour 1.0."""
        fautes = valider_manifeste({
            "name": "a", "version": "1.0.0", "description": "x",
            "model": {"constraints": {"temperature": True, "max_tokens": False}},
        })
        assert len(fautes) == 2, fautes

    def test_les_listes_de_chaines_sont_controlees(self):
        """`skills: reviewer` au lieu d'une liste est une faute fréquente."""
        fautes = valider_manifeste({
            "name": "a", "version": "1.0.0", "description": "x", "skills": "revue",
        })
        assert any("skills" in faute for faute in fautes), fautes


class TestAllerRetour:
    """Écrire puis relire doit rendre exactement le même agent."""

    def test_l_agent_relu_est_identique(self, tmp_path):
        """C'est la garantie qui rend le format utile : rien ne se perd."""
        origine = _agent(
            author="GalSen IA", license="MIT",
            model_preferred="qwen2.5-coder:14b", model_fallback=("llama3.1",),
            skills=("revue-de-code",), tools=("lecteur",), tags=("galsen-ia",),
            metadata={"galsen_priority": 85},
        )
        ecrire_agent(origine, tmp_path)
        assert lire_agent(tmp_path / origine.name) == origine

    def test_les_deux_fichiers_obligatoires_sont_ecrits(self, tmp_path):
        """La spécification en impose deux : en écrire un seul ne suffit pas."""
        dossier = ecrire_agent(_agent(), tmp_path)
        assert (dossier / FICHIER_MANIFESTE).is_file()
        assert (dossier / FICHIER_AME).is_file()

    def test_les_sections_non_interpretees_sont_conservees(self, tmp_path):
        """Un agent écrit ailleurs ne doit rien perdre en passant par ici.

        Nous n'interprétons ni `compliance` ni `a2a` ; les effacer à la
        relecture reviendrait à corrompre le travail de leur auteur.
        """
        conformite = {"risk_tier": "high", "recordkeeping": {"retention_period": "7y"}}
        origine = _agent(extensions={"compliance": conformite, "extends": "git://ailleurs"})
        ecrire_agent(origine, tmp_path)

        relu = lire_agent(tmp_path / origine.name)
        assert relu.extensions["compliance"] == conformite
        assert relu.extensions["extends"] == "git://ailleurs"

    def test_les_champs_absents_ne_sont_pas_ecrits(self, tmp_path):
        """Un `model.preferred: null` se lirait comme un choix, pas comme une absence."""
        ecrire_agent(_agent(), tmp_path)
        manifeste = yaml.safe_load(
            (tmp_path / "agent-essai" / FICHIER_MANIFESTE).read_text(encoding="utf-8")
        )
        assert set(manifeste) == {"spec_version", "name", "version", "description"}

    def test_la_version_de_specification_est_declaree(self, tmp_path):
        """Sans elle, un lecteur ne sait pas contre quel format il valide."""
        ecrire_agent(_agent(), tmp_path)
        manifeste = yaml.safe_load(
            (tmp_path / "agent-essai" / FICHIER_MANIFESTE).read_text(encoding="utf-8")
        )
        assert manifeste["spec_version"] == SPEC_VERSION


class TestLectureSansEffet:
    """Lire un dossier publié par un inconnu ne doit rien déclencher."""

    def _ecrire(self, dossier, manifeste: str, ame: str = "Identité.\n"):
        """Écrit un dossier d'agent brut, sans passer par l'écrivain."""
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / FICHIER_MANIFESTE).write_text(manifeste, encoding="utf-8")
        (dossier / FICHIER_AME).write_text(ame, encoding="utf-8")
        return dossier

    def test_le_yaml_n_est_jamais_construit_en_objets(self, tmp_path):
        """`yaml.load` exécuterait ceci ; `safe_load` refuse de le construire.

        C'est la garantie centrale de la couche : un manifeste est du texte,
        pas un programme.
        """
        piege = tmp_path / "piege"
        self._ecrire(piege, "!!python/object/apply:os.system ['echo compromis']\n")
        # Le motif compte : l'échec doit venir du refus de construire l'objet,
        # pas d'une validation qui aurait trouvé le manifeste mal formé après coup.
        with pytest.raises(OpenGAPError, match="YAML illisible"):
            lire_agent(piege)

    def test_un_manifeste_absent_est_signale(self, tmp_path):
        """Un dossier incomplet doit dire lequel des deux fichiers manque."""
        (tmp_path / "vide").mkdir()
        with pytest.raises(OpenGAPError, match=FICHIER_MANIFESTE):
            lire_agent(tmp_path / "vide")

    def test_une_ame_vide_est_refusee(self, tmp_path):
        """Un `SOUL.md` blanc rend l'agent indiscernable de n'importe quel autre."""
        agent = self._ecrire(
            tmp_path / "sans-ame",
            "name: sans-ame\nversion: 1.0.0\ndescription: x\n",
            ame="   \n\n",
        )
        with pytest.raises(OpenGAPError, match=FICHIER_AME):
            lire_agent(agent)

    def test_un_fichier_demesure_est_refuse(self, tmp_path):
        """Un manifeste est une description : la borne évite de charger un disque."""
        agent = self._ecrire(
            tmp_path / "enorme",
            "name: enorme\nversion: 1.0.0\ndescription: "
            + "x" * (TAILLE_MAX_FICHIER + 1) + "\n",
        )
        with pytest.raises(OpenGAPError, match="borne"):
            lire_agent(agent)

    def test_un_manifeste_invalide_est_refuse_avant_tout_usage(self, tmp_path):
        """Les fautes remontent dans l'exception, pas dans un journal muet."""
        agent = self._ecrire(tmp_path / "faux", "name: Majuscule\nversion: 1.0\n")
        with pytest.raises(OpenGAPError) as capture:
            lire_agent(agent)
        assert "name" in str(capture.value) and "version" in str(capture.value)

    @pytest.mark.parametrize("nom", ["../evasion", "/absolu", "avec espace"])
    def test_un_nom_force_ne_peut_pas_ecrire_ailleurs(self, tmp_path, nom):
        """Le nom est validé **avant** de servir à construire un chemin."""
        with pytest.raises(OpenGAPError):
            ecrire_agent(_agent(name=nom), tmp_path / "destination")
        assert not (tmp_path / "destination").exists()

    def test_ecrire_un_agent_sans_ame_est_refuse(self, tmp_path):
        """Nous ne publions pas un dossier que nous refuserions de relire."""
        with pytest.raises(OpenGAPError, match=FICHIER_AME):
            ecrire_agent(_agent(soul="\n"), tmp_path)


class TestConversionDepuisLeRegistre:
    """Le manifeste ne porte que ce que le registre déclare réellement."""

    ENTREE = {
        "id": "reviewer",
        "enabled": True,
        "priority": 85,
        "role": "Code Reviewer",
        "description": "Vérifie la qualité du code.",
        "module": "agents.reviewer.agent",
    }

    def test_les_champs_du_registre_sont_repris(self):
        """L'identifiant et la description viennent du registre, pas d'ailleurs."""
        agent = depuis_entree_registre(self.ENTREE, "0.1.0")
        assert agent.name == "reviewer"
        assert agent.description == "Vérifie la qualité du code."

    def test_le_registre_reste_retrouvable_dans_les_metadonnees(self):
        """Sans le module, l'export ne permettrait pas de revenir au code."""
        metadata = depuis_entree_registre(self.ENTREE, "0.1.0").metadata
        assert metadata["galsen_module"] == "agents.reviewer.agent"
        assert metadata["galsen_priority"] == 85

    def test_aucun_modele_n_est_invente(self):
        """GalSen IA choisit son modèle à l'exécution, selon ce qui répond.

        Inscrire un modèle préféré ici ferait croire à un choix qui n'existe
        pas, et le figerait pour les outils qui lisent le manifeste.
        """
        agent = depuis_entree_registre(self.ENTREE, "0.1.0")
        assert agent.model_preferred is None
        assert agent.model_fallback == ()

    def test_une_entree_sans_identifiant_est_refusee(self):
        """Un agent sans nom ne peut être ni écrit ni référencé."""
        with pytest.raises(OpenGAPError):
            depuis_entree_registre({"role": "Sans identifiant"}, "0.1.0")

    @pytest.mark.parametrize("registre,attendu", [
        ("project_manager", "project-manager"),
        ("reviewer", "reviewer"),
        ("Data_Engineer", "data-engineer"),
    ])
    def test_le_snake_case_du_registre_devient_du_kebab_case(self, registre, attendu):
        """Le format n'admet que le kebab-case ; le registre admet les deux."""
        assert nom_opengap(registre) == attendu

    def test_l_identifiant_d_origine_est_conserve(self):
        """Sans lui, un manifeste exporté ne ramènerait pas à son agent."""
        agent = depuis_entree_registre(
            {"id": "project_manager", "role": "Chef de projet"}, "0.1.0"
        )
        assert agent.name == "project-manager"
        assert agent.metadata["galsen_id"] == "project_manager"

    def test_un_identifiant_intraduisible_est_refuse(self):
        """Inventer un nom vaudrait mieux que rien — non : ce serait une invention."""
        with pytest.raises(OpenGAPError):
            depuis_entree_registre({"id": "___", "role": "x"}, "0.1.0")

    def test_l_ame_generee_est_conforme(self):
        """Elle doit tenir la contrainte minimale : un paragraphe non vide."""
        agent = depuis_entree_registre(self.ENTREE, "0.1.0")
        assert "Code Reviewer" in agent.soul
        assert "Core Identity" in agent.soul


class TestExportLivre:
    """Les dossiers versionnés doivent décrire les agents d'aujourd'hui."""

    def test_chaque_agent_du_registre_est_exporte(self):
        """Un agent ajouté au registre et jamais exporté serait invisible dehors.

        La comparaison passe par `nom_opengap` : sept agents du registre portent
        un identifiant en snake_case, que le format n'admet pas. Comparer les
        identifiants bruts ferait échouer ce test pour une raison qui n'est pas
        une dérive.
        """
        registre = yaml.safe_load(open(REGISTRE, encoding="utf-8"))
        attendus = {nom_opengap(entree["id"]) for entree in registre["agents"]}
        exportes = {
            nom for nom in os.listdir(EXPORT_LIVRE)
            if os.path.isdir(os.path.join(EXPORT_LIVRE, nom))
        }
        assert exportes == attendus

    def test_chaque_dossier_livre_se_relit(self):
        """Publier un dossier que notre propre lecteur refuse serait une faute."""
        for nom in sorted(os.listdir(EXPORT_LIVRE)):
            chemin = os.path.join(EXPORT_LIVRE, nom)
            if os.path.isdir(chemin):
                assert lire_agent(chemin).name == nom

    def test_l_export_livre_correspond_au_registre(self, tmp_path):
        """Le test anti-dérive : réexporter ne doit rien changer.

        S'il échoue, c'est que le registre a bougé sans que
        `python scripts/export_opengap.py` soit relancé.
        """
        exporter_registre(REGISTRE, tmp_path, __version__)
        for nom in sorted(os.listdir(EXPORT_LIVRE)):
            livre = os.path.join(EXPORT_LIVRE, nom)
            if not os.path.isdir(livre):
                continue
            assert lire_agent(livre) == lire_agent(tmp_path / nom), (
                f"{nom} a dérivé — relancez python scripts/export_opengap.py"
            )

    def test_la_version_exportee_suit_la_plateforme(self):
        """Deux versions qui divergent rendraient les manifestes intraçables."""
        for nom in sorted(os.listdir(EXPORT_LIVRE)):
            chemin = os.path.join(EXPORT_LIVRE, nom)
            if os.path.isdir(chemin):
                assert lire_agent(chemin).version == __version__

    def test_un_registre_vide_est_signale(self, tmp_path):
        """Exporter zéro agent en silence laisserait croire à une réussite."""
        vide = tmp_path / "registry.yaml"
        vide.write_text("version: '1.0'\nagents: []\n", encoding="utf-8")
        with pytest.raises(OpenGAPError, match="aucun agent"):
            exporter_registre(vide, tmp_path / "sortie", "0.1.0")

    def test_un_registre_absent_est_signale(self, tmp_path):
        """Le chemin fautif doit apparaître dans le message."""
        with pytest.raises(OpenGAPError, match="illisible"):
            exporter_registre(tmp_path / "absent.yaml", tmp_path, "0.1.0")


class TestAttribution:
    """La licence MIT impose de conserver l'attribution d'origine."""

    def test_la_licence_amont_est_conservee(self):
        """Sans ce fichier, notre usage de la spécification serait irrégulier."""
        licence = open(
            os.path.join(RACINE, "third_party", "opengap", "LICENSE"), encoding="utf-8"
        ).read()
        assert "MIT License" in licence
        assert "Copyright (c) 2025" in licence

    def test_la_specification_est_recopiee(self):
        """C'est ce qui rend la plateforme indépendante du dépôt amont.

        Si `open-gitagent/opengap` disparaît, le format contre lequel nous
        écrivons reste décrit ici.
        """
        notice = open(
            os.path.join(RACINE, "third_party", "opengap", "NOTICE.md"), encoding="utf-8"
        ).read()
        assert FICHIER_MANIFESTE in notice and FICHIER_AME in notice
        assert SPEC_VERSION in notice
