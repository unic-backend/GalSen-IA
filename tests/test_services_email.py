"""
Tests unitaires pour le service Email.

Couvre :
- EmailMessage, EmailAttachment, EmailSendResult, EmailStats
- InMemoryEmailStore : CRUD, filtrage, statistiques
- EmailManagerImpl : envoi, validation, dégradation gracieuse du store
- SmtpTransport, ConsoleTransport, NoopTransport
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestEmailTypes:
    """Vérifie les modèles de données des emails."""

    def test_generate_email_id_prefix(self):
        """L'identifiant d'email doit commencer par 'email_'."""
        from src.services.email import generate_email_id
        eid = generate_email_id()
        assert eid.startswith("email_")
        assert len(eid) > 10

    def test_email_default_status(self):
        """Un nouvel email doit avoir le statut DRAFT."""
        from src.services.email import EmailMessage
        msg = EmailMessage(subject="Test", body="Message", sender="a@b.com", recipients=["b@c.com"])
        assert msg.status.value == "draft"

    def test_email_mark_sent(self):
        """mark_sent() doit passer le statut à SENT et horodater."""
        from src.services.email import EmailMessage
        msg = EmailMessage(subject="Test", body="Message", sender="a@b.com", recipients=["b@c.com"])
        msg.mark_sent()
        assert msg.status.value == "sent"
        assert msg.sent_at is not None

    def test_email_to_dict(self):
        """to_dict() doit inclure les champs obligatoires et optionnels."""
        from src.services.email import EmailMessage, EmailAttachment
        att = EmailAttachment(filename="doc.pdf", content_type="application/pdf", data=b"pdf")
        msg = EmailMessage(
            subject="Sujet",
            body="Corps du message",
            sender="moi@exemple.com",
            recipients=["toi@exemple.com"],
            cc=["cc@exemple.com"],
            reply_to="reply@exemple.com",
            attachments=[att],
            metadata={"source": "test"},
        )
        msg.mark_sent()
        d = msg.to_dict()
        assert d["id"] == msg.id
        assert d["subject"] == "Sujet"
        assert d["sender"] == "moi@exemple.com"
        assert d["recipients"] == ["toi@exemple.com"]
        assert d["status"] == "sent"
        assert d["cc"] == ["cc@exemple.com"]
        assert d["reply_to"] == "reply@exemple.com"
        assert d["attachment_count"] == 1
        assert "sent_at" in d
        assert "metadata" in d

    def test_email_to_dict_truncates_body(self):
        """to_dict() doit tronquer le corps à 500 caractères."""
        from src.services.email import EmailMessage
        long_body = "x" * 1000
        msg = EmailMessage(subject="Long", body=long_body, sender="a@b.com", recipients=["b@c.com"])
        d = msg.to_dict()
        assert len(d["body"]) <= 503  # 500 + "..."

    def test_email_attachment_post_init_size(self):
        """EmailAttachment doit calculer la taille automatiquement."""
        from src.services.email import EmailAttachment
        att = EmailAttachment(filename="f.txt", content_type="text/plain", data=b"hello")
        assert att.size == 5

    def test_email_attachment_to_dict(self):
        """EmailAttachment.to_dict() ne doit pas inclure les données."""
        from src.services.email import EmailAttachment
        att = EmailAttachment(filename="f.txt", content_type="text/plain", data=b"secret", size=5)
        d = att.to_dict()
        assert d["filename"] == "f.txt"
        assert d["size"] == 5
        assert "data" not in d

    def test_email_from_mapping(self):
        """from_mapping() doit reconstruire un EmailMessage depuis un dictionnaire."""
        from src.services.email import EmailMessage, EmailStatus
        original = EmailMessage(
            subject="Test", body="Corps", sender="a@b.com",
            recipients=["b@c.com"], status=EmailStatus.SENT,
        )
        d = original.to_dict()
        restored = EmailMessage.from_mapping(d)
        assert restored.id == original.id
        assert restored.subject == original.subject
        assert restored.sender == original.sender
        assert restored.status == EmailStatus.SENT

    def test_email_from_mapping_string_status(self):
        """from_mapping() doit accepter un statut sous forme de chaîne."""
        from src.services.email import EmailMessage, EmailStatus
        restored = EmailMessage.from_mapping({
            "subject": "T", "body": "M", "sender": "a@b.com",
            "recipients": ["b@c.com"], "status": "sent",
        })
        assert restored.status == EmailStatus.SENT

    def test_email_from_mapping_invalid_status_defaults_draft(self):
        """Un statut invalide dans from_mapping() doit être remplacé par DRAFT."""
        from src.services.email import EmailMessage, EmailStatus
        restored = EmailMessage.from_mapping({
            "subject": "T", "body": "M", "sender": "a@b.com",
            "recipients": ["b@c.com"], "status": "unknown",
        })
        assert restored.status == EmailStatus.DRAFT

    def test_email_send_result_defaults(self):
        """EmailSendResult doit accepter les champs minimaux."""
        from src.services.email import EmailSendResult
        r = EmailSendResult(True, "Succès")
        assert r.success is True
        assert r.message == "Succès"
        assert r.email_id is None

    def test_email_stats_creation(self):
        """EmailStats doit stocker les compteurs."""
        from src.services.email import EmailStats
        stats = EmailStats(total=5, sent=3, failed=1, draft=1)
        assert stats.total == 5
        assert stats.sent == 3


class TestInMemoryEmailStore:
    """Vérifie le stockage en mémoire des emails."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.email import InMemoryEmailStore, EmailMessage, EmailStatus
        self.store = InMemoryEmailStore()
        self.msg_a = EmailMessage(
            subject="A", body="Msg A", sender="a@b.com",
            recipients=["r@b.com"], status=EmailStatus.SENT,
        )
        self.msg_b = EmailMessage(
            subject="B", body="Msg B", sender="b@b.com",
            recipients=["r@b.com"], status=EmailStatus.DRAFT,
        )
        self.msg_c = EmailMessage(
            subject="C", body="Msg C", sender="a@b.com",
            recipients=["autre@b.com"], cc=["cc@b.com"], status=EmailStatus.SENT,
        )

    def test_save_and_get(self):
        """save() puis get() doivent retourner le même message."""
        eid = self.store.save(self.msg_a)
        retrieved = self.store.get(eid)
        assert retrieved is not None
        assert retrieved.id == self.msg_a.id
        assert retrieved.subject == "A"

    def test_save_duplicate_raises(self):
        """save() d'un identifiant existant doit lever ValueError."""
        self.store.save(self.msg_a)
        with pytest.raises(ValueError, match="existe déjà"):
            self.store.save(self.msg_a)

    def test_get_missing_returns_none(self):
        """get() d'un identifiant inconnu doit retourner None."""
        assert self.store.get("nonexistent") is None

    def test_list_emails_ordered_by_recency(self):
        """list_emails() doit retourner du plus récent au plus ancien."""
        self.store.save(self.msg_a)
        time.sleep(0.01)
        self.store.save(self.msg_b)
        all_msgs = self.store.list_emails(limit=10)
        assert len(all_msgs) == 2
        assert all_msgs[0].id == self.msg_b.id  # plus récent d'abord
        assert all_msgs[1].id == self.msg_a.id

    def test_list_emails_filter_status(self):
        """list_emails() doit filtrer par statut."""
        self.store.save(self.msg_a)  # SENT
        self.store.save(self.msg_b)  # DRAFT
        self.store.save(self.msg_c)  # SENT
        sent = self.store.list_emails(limit=10, status="sent")
        assert len(sent) == 2
        assert all(m.status.value == "sent" for m in sent)

    def test_list_emails_filter_sender(self):
        """list_emails() doit filtrer par expéditeur."""
        self.store.save(self.msg_a)  # a@b.com
        self.store.save(self.msg_b)  # b@b.com
        self.store.save(self.msg_c)  # a@b.com
        sent_by_a = self.store.list_emails(limit=10, sender="a@b.com")
        assert len(sent_by_a) == 2

    def test_list_emails_filter_recipient(self):
        """list_emails() doit filtrer par destinataire (inclut CC)."""
        self.store.save(self.msg_a)  # recipients=[r@b.com]
        self.store.save(self.msg_c)  # cc=[cc@b.com]
        cc_emails = self.store.list_emails(limit=10, recipient="cc@b.com")
        assert len(cc_emails) == 1

    def test_update_status(self):
        """update_status() doit mettre à jour le statut."""
        eid = self.store.save(self.msg_a)
        assert self.store.update_status(eid, "draft")
        retrieved = self.store.get(eid)
        assert retrieved.status.value == "draft"

    def test_update_status_missing(self):
        """update_status() d'un email inconnu doit retourner False."""
        assert not self.store.update_status("nonexistent", "sent")

    def test_update_status_invalid(self):
        """update_status() avec un statut invalide doit retourner False."""
        eid = self.store.save(self.msg_a)
        assert not self.store.update_status(eid, "unknown_status")

    def test_update_status_sent_sets_sent_at(self):
        """Passer le statut à SENT doit définir sent_at si absent."""
        eid = self.store.save(self.msg_b)  # DRAFT
        assert self.store.update_status(eid, "sent")
        retrieved = self.store.get(eid)
        assert retrieved.sent_at is not None

    def test_delete(self):
        """delete() doit supprimer un email."""
        eid = self.store.save(self.msg_a)
        assert self.store.delete(eid)
        assert self.store.get(eid) is None

    def test_delete_missing(self):
        """delete() d'un email inconnu doit retourner False."""
        assert not self.store.delete("nonexistent")

    def test_stats(self):
        """stats() doit retourner des statistiques correctes."""
        self.store.save(self.msg_a)  # SENT, a@b.com
        self.store.save(self.msg_b)  # DRAFT, b@b.com
        stats = self.store.stats()
        assert stats["total"] == 2
        assert stats["by_status"]["sent"] == 1
        assert stats["by_status"]["draft"] == 1
        assert stats["unique_senders"] == 2

    def test_clear(self):
        """clear() doit supprimer tous les emails."""
        self.store.save(self.msg_a)
        self.store.save(self.msg_b)
        assert self.store.clear() == 2
        assert self.store.count() == 0

    def test_list_with_limit(self):
        """list_emails() doit respecter la limite."""
        self.store.save(self.msg_a)
        self.store.save(self.msg_b)
        self.store.save(self.msg_c)
        assert len(self.store.list_emails(limit=2)) == 2

    def test_list_with_offset(self):
        """list_emails() doit respecter l'offset."""
        self.store.save(self.msg_a)
        self.store.save(self.msg_b)
        self.store.save(self.msg_c)
        results = self.store.list_emails(limit=10, offset=2)
        assert len(results) == 1


class TestEmailManager:
    """Vérifie le gestionnaire d'emails (best-effort)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.email import EmailManagerImpl
        self.manager = EmailManagerImpl()

    def test_send_email(self):
        """Sans transport configuré, l'envoi est refusé et le message conservé.

        Ce test affirmait `result.success` alors qu'aucun serveur n'était
        contacté : il rendait permanente une réponse fabriquée. Il vérifie
        désormais ce qui se passe vraiment.
        """
        result = self.manager.send_email(
            subject="Test", body="Message", sender="a@b.com",
            recipients=["b@c.com"],
        )
        assert result.success is False
        assert "aucun transport" in result.message.lower()
        # Le message est enregistré : ce qui a été rédigé ne disparaît pas.
        assert result.email_id is not None
        assert result.email_id.startswith("email_")
        assert self.manager.get_email(result.email_id) is not None

    def test_send_and_get(self):
        """send_email() puis get_email() doivent retourner le même email."""
        result = self.manager.send_email(
            subject="Sujet", body="Corps", sender="a@b.com",
            recipients=["b@c.com"],
        )
        email = self.manager.get_email(result.email_id)
        assert email is not None
        assert email.subject == "Sujet"
        # `sent` seulement quand un transport a accepté le message.
        assert email.status.value == "failed"

    def test_send_email_empty_subject(self):
        """send_email() avec un sujet vide doit échouer."""
        result = self.manager.send_email(
            subject="", body="Message", sender="a@b.com",
            recipients=["b@c.com"],
        )
        assert not result.success
        assert "sujet" in result.message.lower()

    def test_send_email_empty_body(self):
        """send_email() avec un corps vide doit échouer."""
        result = self.manager.send_email(
            subject="Test", body="", sender="a@b.com",
            recipients=["b@c.com"],
        )
        assert not result.success
        assert "vide" in result.message.lower()

    def test_send_email_invalid_sender(self):
        """send_email() avec un expéditeur invalide doit échouer."""
        result = self.manager.send_email(
            subject="Test", body="Message", sender="invalide",
            recipients=["b@c.com"],
        )
        assert not result.success
        assert "invalide" in result.message.lower()

    def test_send_email_no_recipients(self):
        """send_email() sans destinataires doit échouer."""
        result = self.manager.send_email(
            subject="Test", body="Message", sender="a@b.com",
            recipients=[],
        )
        assert not result.success
        assert "destinataire" in result.message.lower()

    def test_send_email_invalid_recipient(self):
        """send_email() avec un destinataire invalide doit échouer."""
        result = self.manager.send_email(
            subject="Test", body="Message", sender="a@b.com",
            recipients=["invalide"],
        )
        assert not result.success

    def test_send_email_with_all_fields(self):
        """send_email() doit accepter CC, BCC, is_html, metadata."""
        result = self.manager.send_email(
            subject="Complet", body="Corps", sender="a@b.com",
            recipients=["b@c.com"],
            cc=["cc@c.com"],
            bcc=["bcc@c.com"],
            is_html=True,
            metadata={"source": "test"},
        )
        assert result.success is False  # aucun transport configuré
        assert result.details["cc"] == ["cc@c.com"]
        assert result.details["delivered"] is False

    def test_list_emails(self):
        """list_emails() doit retourner les emails envoyés."""
        self.manager.send_email(subject="A", body="a", sender="a@b.com", recipients=["r@b.com"])
        self.manager.send_email(subject="B", body="b", sender="b@b.com", recipients=["r@b.com"])
        emails = self.manager.list_emails()
        assert len(emails) == 2

    def test_list_emails_filter_sender(self):
        """list_emails(sender=...) doit filtrer."""
        self.manager.send_email(subject="A", body="a", sender="a@b.com", recipients=["r@b.com"])
        self.manager.send_email(subject="B", body="b", sender="b@b.com", recipients=["r@b.com"])
        emails = self.manager.list_emails(sender="a@b.com")
        assert len(emails) == 1
        assert emails[0].subject == "A"

    def test_delete_email(self):
        """delete_email() doit supprimer l'email."""
        result = self.manager.send_email(
            subject="Del", body="x", sender="a@b.com", recipients=["r@b.com"],
        )
        assert self.manager.delete_email(result.email_id)
        assert self.manager.get_email(result.email_id) is None

    def test_delete_email_missing(self):
        """delete_email() d'un email inconnu doit retourner False sans erreur."""
        assert not self.manager.delete_email("nonexistent")

    def test_stats(self):
        """stats() doit retourner des statistiques cohérentes."""
        self.manager.send_email(subject="A", body="a", sender="a@b.com", recipients=["r@b.com"])
        self.manager.send_email(subject="B", body="b", sender="b@b.com", recipients=["r@b.com"])
        stats = self.manager.stats()
        assert stats["total"] == 2
        # Enregistrés mais non délivrés : le compte le dit.
        assert stats["by_status"]["failed"] == 2

    def test_clear(self):
        """clear() doit tout supprimer."""
        self.manager.send_email(subject="A", body="a", sender="a@b.com", recipients=["r@b.com"])
        assert self.manager.clear() == 1
        assert len(self.manager.list_emails()) == 0

    def test_store_failure_graceful(self):
        """Une panne du store ne doit pas crasher le manager."""
        from src.services.email import EmailStore
        broken_store = MagicMock(spec=EmailStore)
        broken_store.save.side_effect = RuntimeError("Stockage indisponible")
        broken_store.get.side_effect = RuntimeError("Stockage indisponible")
        broken_store.list_emails.side_effect = RuntimeError("Stockage indisponible")
        broken_store.delete.side_effect = RuntimeError("Stockage indisponible")
        broken_store.stats.side_effect = RuntimeError("Stockage indisponible")
        broken_store.clear.side_effect = RuntimeError("Stockage indisponible")
        manager = type(self.manager)(store=broken_store)

        result = manager.send_email(subject="T", body="M", sender="a@b.com", recipients=["b@c.com"])
        assert not result.success

        assert manager.get_email("any") is None
        assert manager.list_emails() == []
        assert manager.delete_email("any") is False
        assert manager.stats() == {}
        assert manager.clear() == 0


class TestEmailTransport:
    """Vérifie les transports email."""

    def test_noop_transport_default_behavior(self):
        """Le transport qui n'envoie rien doit le dire, pas rendre un succès.

        Il retournait `(True, "")`, si bien que le gestionnaire répondait
        « Email envoyé » sans qu'aucun serveur ait été contacté.
        """
        from src.services.email.transport import NoopTransport
        transport = NoopTransport()
        ok, msg = transport.send("a@b.com", ["b@c.com"], "Sujet", "Corps")
        assert ok is False
        assert "aucun transport" in msg.lower()
        # Le message dit quoi faire, pas seulement que ça n'a pas marché.
        assert "GALSEN_SMTP_HOST" in msg

    def test_console_transport_logs(self):
        """ConsoleTransport doit logger le message."""
        from src.services.email.transport import ConsoleTransport
        transport = ConsoleTransport()
        ok, msg = transport.send("a@b.com", ["b@c.com"], "Sujet", "Corps")
        assert ok

    def test_smtp_transport_not_configured_by_default(self):
        """SmtpTransport par défaut doit cibler localhost:587."""
        from src.services.email.transport import SmtpTransport
        transport = SmtpTransport()
        assert transport._host == "localhost"
        assert transport._port == 587

    def test_smtp_transport_custom_config(self):
        """SmtpTransport doit accepter une configuration personnalisée."""
        from src.services.email.transport import SmtpTransport
        transport = SmtpTransport(
            host="smtp.gmail.com", port=465,
            username="user@gmail.com", password="app-pw",
            use_ssl=True, use_tls=False,
        )
        assert transport._host == "smtp.gmail.com"
        assert transport._port == 465
        assert transport._username == "user@gmail.com"
        assert transport._password == "app-pw"
        assert transport._use_ssl is True
        assert transport._use_tls is False

    def test_smtp_transport_connection_refused(self):
        """SmtpTransport doit gérer une connexion refusée."""
        from src.services.email.transport import SmtpTransport
        transport = SmtpTransport(host="127.0.0.1", port=1, timeout=1)
        ok, msg = transport.send("a@b.com", ["b@c.com"], "Sujet", "Corps")
        assert not ok
        assert "réseau" in msg.lower() or "refus" in msg.lower() or "SMTP" in msg.upper() or "connexion" in msg.lower()

    def test_smtp_build_message_simple(self):
        """SmtpTransport._build_message() doit créer un message MIME texte."""
        from src.services.email.transport import SmtpTransport
        transport = SmtpTransport()
        msg = transport._build_message("a@b.com", ["b@c.com"], "Sujet", "Corps", False, None, None, None)
        assert msg["From"] == "a@b.com"
        assert msg["To"] == "b@c.com"
        assert msg["Subject"] == "Sujet"

    def test_smtp_build_message_html(self):
        """SmtpTransport._build_message() doit ajouter un texte alternatif en HTML."""
        from src.services.email.transport import SmtpTransport
        transport = SmtpTransport()
        msg = transport._build_message("a@b.com", ["b@c.com"], "Sujet", "<p>Salut</p>", True, None, None, None)
        # Doit avoir 2 parties : text/plain + text/html
        assert msg.is_multipart()

    def test_smtp_build_message_with_cc(self):
        """SmtpTransport._build_message() doit inclure le Cc dans l'en-tête."""
        from src.services.email.transport import SmtpTransport
        transport = SmtpTransport()
        msg = transport._build_message("a@b.com", ["b@c.com"], "Sujet", "Corps", False, ["cc@d.com"], None, None)
        assert "Cc" in msg
        assert "cc@d.com" in msg["Cc"]

    def test_smtp_is_configured_default_not(self):
        """SmtpTransport.is_configured() doit retourner False pour localhost."""
        from src.services.email.transport import SmtpTransport
        transport = SmtpTransport()
        assert not transport.is_configured()

    def test_smtp_is_configured_with_host(self):
        """SmtpTransport.is_configured() doit retourner True si non-localhost."""
        from src.services.email.transport import SmtpTransport
        transport = SmtpTransport(host="smtp.gmail.com")
        assert transport.is_configured()

    def test_smtp_is_configured_with_username(self):
        """SmtpTransport.is_configured() doit retourner True si username fourni."""
        from src.services.email.transport import SmtpTransport
        transport = SmtpTransport(username="user@example.com")
        assert transport.is_configured()

    def test_html_to_plain_basic(self):
        """_html_to_plain() doit convertir du HTML simple en texte."""
        from src.services.email.transport import _html_to_plain
        result = _html_to_plain("<p>Bonjour</p><p>Monde</p>")
        assert "Bonjour" in result
        assert "Monde" in result

    def test_html_to_plain_br(self):
        """_html_to_plain() doit convertir <br> en sauts de ligne."""
        from src.services.email.transport import _html_to_plain
        result = _html_to_plain("Ligne 1<br>Ligne 2")
        assert "Ligne 1" in result
        assert "Ligne 2" in result

    def test_html_to_plain_strip_tags(self):
        """_html_to_plain() doit supprimer toutes les balises."""
        from src.services.email.transport import _html_to_plain
        result = _html_to_plain("<b>Gras</b> et <i>italique</i>")
        assert "Gras" in result
        assert "italique" in result
        assert "<b>" not in result
        assert "<i>" not in result

    def test_manager_with_noop_transport(self):
        """Sans transport, le gestionnaire stocke et signale la non-délivrance."""
        from src.services.email import EmailManagerImpl
        from src.services.email.transport import NoopTransport
        manager = EmailManagerImpl(transport=NoopTransport())
        result = manager.send_email(
            subject="Test", body="Message", sender="a@b.com",
            recipients=["b@c.com"],
        )
        assert result.success is False
        assert result.email_id is not None
        assert manager.get_email(result.email_id).status.value == "failed"

    def test_manager_with_console_transport(self):
        """EmailManagerImpl avec ConsoleTransport doit logger et stocker."""
        from src.services.email import EmailManagerImpl
        from src.services.email.transport import ConsoleTransport
        manager = EmailManagerImpl(transport=ConsoleTransport())
        result = manager.send_email(
            subject="Console", body="Test", sender="a@b.com",
            recipients=["b@c.com"],
        )
        assert result.success

    def test_manager_transport_failure_reported(self):
        """Un échec du transport doit être rapporté sans sauvegarde."""
        from src.services.email import EmailManagerImpl
        from src.services.email.transport import EmailTransport
        mock_transport = MagicMock(spec=EmailTransport)
        mock_transport.send.return_value = (False, "SMTP indisponible")
        manager = EmailManagerImpl(transport=mock_transport)
        result = manager.send_email(
            subject="Fail", body="X", sender="a@b.com",
            recipients=["b@c.com"],
        )
        assert not result.success
        assert "indisponible" in result.message.lower()

    def test_manager_with_broken_transport(self):
        """Un transport qui lève une exception doit être géré."""
        from src.services.email import EmailManagerImpl
        from src.services.email.transport import EmailTransport
        broken = MagicMock(spec=EmailTransport)
        broken.send.side_effect = RuntimeError("Transport cassé")
        manager = EmailManagerImpl(transport=broken)
        # Le manager doit capturer l'exception et retourner un échec
        # (send() n'est jamais censé lever, mais par sécurité)
        result = manager.send_email(
            subject="Casse", body="X", sender="a@b.com",
            recipients=["b@c.com"],
        )
        assert not result.success