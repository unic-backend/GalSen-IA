"""
Entrées non textuelles : parole et image (VOLET 32).

La plateforme lit des documents depuis longtemps. Elle n'entendait rien —
**aucun chemin audio n'existait dans `src/`** — et le moteur de vision, 1 845
lignes d'OpenCV et de Pillow, n'était relié à aucune ingestion. Une photo de
parcelle et un message vocal, deux des façons les plus naturelles de s'adresser
à cette plateforme dans son pays, n'entraient nulle part.

La règle qui gouverne ces tests : **une capacité absente refuse, elle n'invente
pas**. Une transcription fabriquée met des mots dans la bouche de quelqu'un ;
c'est la forme la plus dommageable que puisse prendre la fabrication que ce dépôt
refuse, et la seule qui puisse nuire à une personne nommée.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.ingestion import DocumentIngestor  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.knowledge_engine.types import SourceCategory  # noqa: E402
from src.multimodal.interfaces import (  # noqa: E402
    TranscriptionProvider,
    TranscriptionProviderInfo,
    TranscriptionResult,
    TranscriptionUnavailable,
)
from src.multimodal.registry import (  # noqa: E402
    active_transcriber,
    reset_transcriber,
    set_transcriber,
    transcription_status,
)
from src.multimodal.whisper_provider import WhisperTranscriber  # noqa: E402


class TranscripteurDeTest(TranscriptionProvider):
    """
    Transcripteur déterministe : il rend ce qu'on lui a dit de rendre.

    Ce n'est pas mocker la chose sous test. Ce qui est testé ici, c'est
    l'ingestion — le chemin, la provenance, le refus, le rapport — et tout cela
    reste réel. Le modèle acoustique, lui, ne peut pas tourner ici : les poids
    se téléchargent depuis Hugging Face, qui répond 403 à travers ce mandataire.
    """

    def __init__(self, texte="Bonjour, ma parcelle de mil est atteinte.", disponible=True):
        self._texte = texte
        self._disponible = disponible
        self.appels = []

    @property
    def provider_id(self):
        return "test"

    @property
    def model_name(self):
        return "modele-de-test"

    def check_availability(self):
        return TranscriptionProviderInfo(
            provider_id=self.provider_id, model_name=self.model_name,
            available=self._disponible,
        )

    def transcribe(self, chemin, language=None):
        self.appels.append(chemin)
        return TranscriptionResult(
            text=self._texte, language="fr", confidence=0.94, model_name=self.model_name,
        )


@pytest.fixture(autouse=True)
def transcripteur_neuf():
    """Le transcripteur partagé ne doit pas fuir d'un test à l'autre."""
    reset_transcriber()
    yield
    reset_transcriber()


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Base de connaissances isolée."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "in-memory")
    return KnowledgeManagerImpl()


@pytest.fixture
def image(tmp_path):
    """Une vraie image, écrite sur disque."""
    from PIL import Image

    chemin = tmp_path / "parcelle.png"
    Image.new("RGB", (640, 480), (40, 120, 60)).save(chemin)
    return str(chemin)


@pytest.fixture
def audio(tmp_path):
    """Un fichier portant une extension audio — son contenu n'est pas décodé ici."""
    chemin = tmp_path / "message.wav"
    chemin.write_bytes(b"RIFF....WAVEfmt ")
    return str(chemin)


# ----------------------------------------------------------------------
# Sans transcripteur, l'audio est refusé — jamais transcrit à vide
# ----------------------------------------------------------------------

def test_sans_transcripteur_le_fichier_audio_est_ecarte(base, audio):
    """
    Le traiter comme un document vide serait le pire des deux mondes : la base
    gagnerait une entrée sans contenu, et l'opérateur croirait le message
    enregistré.
    """
    rapport = DocumentIngestor(base).ingest_file(
        audio, title="Message vocal", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert rapport.knowledge_ids == []
    assert rapport.skipped, "Le refus doit être rapporté, pas silencieux"
    assert "audio non transcrit" in rapport.skipped[0]


def test_le_defaut_est_sans_transcripteur():
    """L'état normal d'une installation sans Whisper."""
    assert active_transcriber() is None
    etat = transcription_status()
    assert etat["available"] is False
    assert etat["reason"] == "missing_dependency"


def test_l_etat_dit_quoi_installer():
    """Un motif sans geste n'aide personne."""
    assert "requirements-audio.txt" in transcription_status()["detail"]


def test_la_transcription_peut_etre_coupee_explicitement(monkeypatch):
    """Un exploitant doit pouvoir refuser l'audio sans désinstaller quoi que ce soit."""
    monkeypatch.setenv("GALSEN_TRANSCRIPTION_ENABLED", "false")
    set_transcriber(TranscripteurDeTest())

    assert active_transcriber() is None
    assert transcription_status()["reason"] == "disabled"


# ----------------------------------------------------------------------
# Avec un transcripteur, l'audio devient une connaissance sourcée
# ----------------------------------------------------------------------

def test_un_message_vocal_devient_une_connaissance(base, audio):
    """Le chemin complet : audio → texte → bloc de connaissance avec sa provenance."""
    transcripteur = TranscripteurDeTest()
    set_transcriber(transcripteur)

    rapport = DocumentIngestor(base).ingest_file(
        audio, title="Message vocal d'un agriculteur",
        source_category=SourceCategory.INSTITUTIONAL,
    )

    assert transcripteur.appels == [audio]
    assert len(rapport.knowledge_ids) == 1
    item = base.get_knowledge(rapport.knowledge_ids[0])
    assert "parcelle de mil" in item.content
    assert item.source.title == "Message vocal d'un agriculteur"


def test_le_rapport_dit_quel_modele_a_transcrit(base, audio):
    """
    Une transcription est une interprétation.

    Savoir quel modèle l'a produite, dans quelle langue et avec quelle confiance
    est ce qui permet de la traiter comme une hypothèse plutôt que comme un fait.
    """
    set_transcriber(TranscripteurDeTest())

    rapport = DocumentIngestor(base).ingest_file(
        audio, title="Message", source_category=SourceCategory.INSTITUTIONAL,
    )

    note = next(note for note in rapport.notes if note["kind"] == "transcription")
    assert note["model"] == "modele-de-test"
    assert note["language"] == "fr"
    assert note["confidence"] == 0.94


def test_un_audio_inaudible_n_entre_pas(base, audio):
    """Un silence n'est pas une connaissance."""
    set_transcriber(TranscripteurDeTest(texte="   "))

    rapport = DocumentIngestor(base).ingest_file(
        audio, title="Message", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert rapport.knowledge_ids == []
    assert "transcription vide" in rapport.skipped[0]


def test_une_transcription_qui_echoue_est_rapportee(base, audio):
    """Une panne du transcripteur ne doit pas se confondre avec un fichier vide."""

    class Cassé(TranscripteurDeTest):
        def transcribe(self, chemin, language=None):
            raise RuntimeError("modèle introuvable")

    set_transcriber(Cassé())

    rapport = DocumentIngestor(base).ingest_file(
        audio, title="Message", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert rapport.knowledge_ids == []
    assert any("transcription impossible" in erreur for erreur in rapport.errors)


# ----------------------------------------------------------------------
# Le fournisseur Whisper, dans un environnement qui ne peut pas l'exécuter
# ----------------------------------------------------------------------

def test_whisper_absent_rapporte_au_lieu_de_lever():
    """
    L'état est interrogeable sans rien télécharger.

    C'est ce qui permet à `/health` de dire la vérité sur une capacité absente.
    """
    etat = WhisperTranscriber().check_availability()

    assert etat.available is False
    assert etat.reason is TranscriptionUnavailable.MISSING_DEPENDENCY


def test_whisper_leve_plutot_que_rendre_un_texte_vide(tmp_path):
    """
    Rendre `""` se confondrait avec « la personne n'a rien dit ».

    Rendre un texte plausible serait pire encore : ce serait mettre des mots
    dans la bouche de quelqu'un.
    """
    fichier = tmp_path / "voix.wav"
    fichier.write_bytes(b"RIFF")

    with pytest.raises(RuntimeError):
        WhisperTranscriber().transcribe(str(fichier))


def test_un_format_non_pris_en_charge_est_refuse_tot(tmp_path):
    """Refuser avec un message utile vaut mieux que laisser échouer le décodage."""
    fichier = tmp_path / "note.xyz"
    fichier.write_bytes(b"...")

    with pytest.raises(RuntimeError, match="Format non pris en charge"):
        WhisperTranscriber().transcribe(str(fichier))


# ----------------------------------------------------------------------
# L'image entre avec ce qui est mesuré, jamais avec ce qui est imaginé
# ----------------------------------------------------------------------

def test_une_image_devient_une_description_mesuree(base, image):
    """
    « Image PNG de 640×480 » est vrai et vérifiable.

    « Une parcelle de mil en bonne santé » serait inventé — et c'est exactement
    ce qu'un modèle de description produirait sans être branché.
    """
    rapport = DocumentIngestor(base).ingest_file(
        image, title="Photo de parcelle", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert len(rapport.knowledge_ids) == 1
    contenu = base.get_knowledge(rapport.knowledge_ids[0]).content
    assert "640" in contenu and "480" in contenu
    assert "PNG" in contenu


def test_l_absence_d_ocr_retire_le_texte_mais_pas_l_image(base, image):
    """
    `pytesseract` est souvent absent — c'est l'un des huit paquets optionnels
    trouvés au VOLET 26.4. Son absence ne doit pas empêcher l'image d'entrer.
    """
    rapport = DocumentIngestor(base).ingest_file(
        image, title="Photo", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert rapport.knowledge_ids, "L'image doit entrer même sans OCR"
    notes = {note["kind"] for note in rapport.notes}
    assert "ocr" in notes, "L'absence d'OCR doit être dite, pas tue"


def test_une_image_illisible_est_signalee(base, tmp_path):
    """Un fichier qui porte l'extension d'une image sans en être une."""
    faux = tmp_path / "faux.png"
    faux.write_bytes(b"ceci n'est pas une image")

    rapport = DocumentIngestor(base).ingest_file(
        str(faux), title="Faux", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert rapport.knowledge_ids == []
    assert any("illisible" in erreur for erreur in rapport.errors)


def test_l_image_garde_sa_provenance(base, image):
    """Une photo versée sans source serait une affirmation sans auteur, comme le reste."""
    rapport = DocumentIngestor(base).ingest_file(
        image, title="Photo de parcelle", source_category=SourceCategory.INSTITUTIONAL,
        author="Coopérative de Thiès",
    )

    source = base.get_knowledge(rapport.knowledge_ids[0]).source
    assert source.author == "Coopérative de Thiès"
    assert "passage 1/" in source.citation
