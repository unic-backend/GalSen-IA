"""
Tests for the Email tool.
"""

from unittest.mock import patch, MagicMock

import pytest

from src.tools.email.tool import EmailTool


@pytest.fixture
def email_tool():
    """Return an EmailTool instance with default configuration."""
    return EmailTool()


def test_email_tool_initialization(email_tool):
    """Test that the tool initializes."""
    assert email_tool is not None


def test_email_tool_available_operations(email_tool):
    """Test that the available operations are returned correctly."""
    assert email_tool.available_operations() == ["send"]


def test_email_tool_send_success(email_tool):
    """Test sending an email successfully (mocked)."""
    with patch("smtplib.SMTP") as mock_smtp:
        # Configure the mock SMTP instance
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance
        mock_instance.starttls.return_value = None
        mock_instance.login.return_value = None
        mock_instance.send_message.return_value = {}

        # Configuration for the tool (using TLS)
        tool = EmailTool(
            config={
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "user@example.com",
                "smtp_password": "password",
                "use_tls": True,
                "use_ssl": False,
            }
        )

        result = tool.execute(
            "send",
            to=["recipient@example.com"],
            subject="Test Subject",
            body="This is a test email.",
        )

        # Verify the SMTP calls
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_instance.starttls.assert_called_once()
        mock_instance.login.assert_called_once_with("user@example.com", "password")
        mock_instance.send_message.assert_called_once()
        # Check that the message was sent with the correct parameters
        args, kwargs = mock_instance.send_message.call_args
        assert kwargs["from_addr"] == "user@example.com"
        assert kwargs["to_addrs"] == ["recipient@example.com"]
        # Check the message content (we can't easily check the EmailMessage object, but we can check it was called)
        assert "msg" in kwargs

        # Verify the result
        assert result["status"] == "success"
        assert "email sent" in result["message"].lower()
        assert result["details"]["to"] == ["recipient@example.com"]
        assert result["details"]["subject"] == "Test Subject"


def test_email_tool_send_ssl_success(email_tool):
    """Test sending an email successfully using SSL (mocked)."""
    with patch("smtplib.SMTP_SSL") as mock_smtp_ssl:
        # Configure the mock SMTP_SSL instance
        mock_instance = MagicMock()
        # For SMTP_SSL, we don't use a context manager in the same way, but we'll mock it similarly
        # In the actual code, SMTP_SSL is used without a context manager for starttls, so we adjust
        # We'll mock the SMTP_SSL constructor to return an object that we can call methods on
        mock_smtp_ssl.return_value.__enter__.return_value = mock_instance
        mock_instance.login.return_value = None
        mock_instance.send_message.return_value = {}

        # Configuration for the tool (using SSL)
        tool = EmailTool(
            config={
                "smtp_host": "smtp.example.com",
                "smtp_port": 465,
                "smtp_user": "user@example.com",
                "smtp_password": "password",
                "use_tls": False,
                "use_ssl": True,
            }
        )

        result = tool.execute(
            "send",
            to=["recipient@example.com"],
            subject="Test Subject SSL",
            body="This is a test email via SSL.",
        )

        # Verify the SMTP_SSL calls
        mock_smtp_ssl.assert_called_once_with("smtp.example.com", 465)
        # Note: With SSL, we don't call starttls
        # Note: With SSL, we don't call starttls, but we still call login
        mock_instance.login.assert_called_once_with("user@example.com", "password")
        mock_instance.send_message.assert_called_once()
        # Check the from_addr and to_addrs
        args, kwargs = mock_instance.send_message.call_args
        assert kwargs["from_addr"] == "user@example.com"
        assert kwargs["to_addrs"] == ["recipient@example.com"]

        # Verify the result
        assert result["status"] == "success"
        assert "email sent" in result["message"].lower()


def test_email_tool_send_failure(email_tool):
    """Test that an error is raised when sending fails."""
    with patch("smtplib.SMTP") as mock_smtp:
        # Configure the mock to raise an exception
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance
        # Simulate an error during starttls
        mock_instance.starttls.side_effect = Exception("Connection failed")

        tool = EmailTool(
            config={
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "user@example.com",
                "smtp_password": "password",
                "use_tls": True,
                "use_ssl": False,
            }
        )

        with pytest.raises(RuntimeError, match="Échec de l'envoi de l'e-mail"):
            tool.execute(
                "send",
                to=["recipient@example.com"],
                subject="Test Subject",
                body="This is a test email.",
            )


def test_email_tool_send_invalid_to(email_tool):
    """Test that a ValueError is raised for invalid 'to' parameter."""
    with pytest.raises(ValueError, match="Le paramètre 'to' doit être une liste de chaînes de caractères"):
        email_tool.execute(
            "send",
            to="not a list",
            subject="Test",
            body="Body",
        )

    with pytest.raises(ValueError, match="La liste des destinataires 'to' ne peut pas être vide"):
        email_tool.execute(
            "send",
            to=[],
            subject="Test",
            body="Body",
        )


def test_email_tool_send_invalid_subject(email_tool):
    """Test that a ValueError is raised for invalid subject."""
    with pytest.raises(ValueError, match="Le sujet doit être une chaîne non vide"):
        email_tool.execute(
            "send",
            to=["test@example.com"],
            subject="",
            body="Body",
        )


def test_email_tool_send_invalid_body(email_tool):
    """Test that a ValueError is raised for invalid body (non-string)."""
    with pytest.raises(ValueError, match="Le corps doit être une chaîne de caractères"):
        email_tool.execute(
            "send",
            to=["test@example.com"],
            subject="Test",
            body=123,
        )


def test_email_tool_send_invalid_cc_bcc(email_tool):
    """Test that a ValueError is raised for invalid cc or bcc."""
    with pytest.raises(ValueError, match="Le paramètre 'cc' doit être une liste de chaînes de caractères"):
        email_tool.execute(
            "send",
            to=["test@example.com"],
            subject="Test",
            body="Body",
            cc="not a list",
        )

    with pytest.raises(ValueError, match="Le paramètre 'bcc' doit être une liste de chaînes de caractères"):
        email_tool.execute(
            "send",
            to=["test@example.com"],
            subject="Test",
            body="Body",
            bcc=123,
        )


def test_email_tool_send_minimal_config(email_tool):
    """Test sending with minimal configuration (only host)."""
    with patch("smtplib.SMTP") as mock_smtp:
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance
        # For minimal config, we still have use_tls=True, use_ssl=False from __init__ defaults
        mock_instance.starttls.return_value = None
        mock_instance.login.return_value = None  # No login if user/password not set
        mock_instance.send_message.return_value = {}

        tool = EmailTool(
            config={
                "smtp_host": "smtp.example.com",
                # No port, user, password, TLS, SSL settings (defaults apply)
            }
        )

        result = tool.execute(
            "send",
            to=["recipient@example.com"],
            subject="Minimal Test",
            body="Just a test.",
        )

        # Should use default port 25 and attempt STARTTLS (use_tls defaults to True)
        # We are not asserting on the exact call, just that it doesn't throw an exception due to configuration.
        assert result["status"] == "success"


def test_email_tool_unknown_operation(email_tool):
    """Test that calling an unknown operation raises ValueError."""
    with pytest.raises(ValueError, match="Opération 'unknown' inconnue. Opérations disponibles: send"):
        email_tool.execute("unknown")