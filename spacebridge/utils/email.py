"""Email sending utility for SpaceBridge."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

# Email configuration
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "hello@spacecode.ai")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "SpaceBridge")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://spacebridge.io")


class EmailError(Exception):
    """Raised when email sending fails."""

    pass


def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    from_email: Optional[str] = None,
) -> None:
    """Send an email using the configured SMTP server.

    Args:
        to_email: Recipient email address.
        subject: Email subject.
        body_text: Plain text email body.
        body_html: HTML email body (optional).
        from_email: Sender email address (defaults to SMTP_FROM).

    Raises:
        EmailError: If email sending fails.
    """
    if not from_email:
        from_email = SMTP_FROM

    # Create message container
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    # Create the body of the message
    part1 = MIMEText(body_text, "plain")
    msg.attach(part1)

    if body_html:
        part2 = MIMEText(body_html, "html")
        msg.attach(part2)

    # Skip sending if SMTP credentials are not configured (development mode)
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning(
            "Email not sent: SMTP credentials not configured. "
            f"Would have sent email to {to_email} with subject '{subject}'"
        )
        logger.debug(f"Email body: {body_text}")
        return

    try:
        # Send the message via SMTP server
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(from_email, to_email, msg.as_string())
            logger.info(f"Email sent to {to_email}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        raise EmailError(f"Failed to send email: {str(e)}")


def send_verification_email(user_email: str, token: str) -> None:
    """Send a verification email to a newly registered user.

    Args:
        user_email: The user's email address.
        token: The verification token.
    """
    verification_link = f"{FRONTEND_URL}/verify-email?token={token}"

    subject = "Verify your SpaceBridge account"
    text_body = f"""
    Welcome to SpaceBridge!

    Please verify your email address by clicking the link below:

    {verification_link}

    If you didn't register for SpaceBridge, please ignore this email.

    Thank you,
    The SpaceBridge Team
    """

    html_body = f"""
    <html>
    <body>
        <h2>Welcome to SpaceBridge!</h2>
        <p>Please verify your email address by clicking the link below:</p>
        <p><a href="{verification_link}">Verify your email</a></p>
        <p>If you didn't register for SpaceBridge, please ignore this email.</p>
        <p>Thank you,<br>The SpaceBridge Team</p>
    </body>
    </html>
    """

    send_email(user_email, subject, text_body, html_body)


def send_password_reset_email(user_email: str, token: str) -> None:
    """Send a password reset email.

    Args:
        user_email: The user's email address.
        token: The password reset token.
    """
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"

    subject = "Reset your SpaceBridge password"
    text_body = f"""
    You have requested to reset your SpaceBridge password.

    Please click the link below to set a new password:

    {reset_link}

    If you didn't request a password reset, please ignore this email.

    Thank you,
    The SpaceBridge Team
    """

    html_body = f"""
    <html>
    <body>
        <h2>Reset your SpaceBridge password</h2>
        <p>You have requested to reset your SpaceBridge password.</p>
        <p>Please click the link below to set a new password:</p>
        <p><a href="{reset_link}">Reset your password</a></p>
        <p>If you didn't request a password reset, please ignore this email.</p>
        <p>Thank you,<br>The SpaceBridge Team</p>
    </body>
    </html>
    """

    send_email(user_email, subject, text_body, html_body)


def send_tracker_registered_email(
    user_email: str, tracker_name: str, tracker_type: str
) -> None:
    """Send a confirmation email when a new tracker is registered.

    Args:
        user_email: The user's email address.
        tracker_name: The name of the registered tracker.
        tracker_type: The type of tracker (e.g., 'github', 'gitlab', 'jira').
    """
    trackers_link = f"{FRONTEND_URL}/trackers"

    subject = f"New {tracker_type.title()} tracker registered: {tracker_name}"
    text_body = f"""
    You have successfully registered a new tracker in SpaceBridge:

    Name: {tracker_name}
    Type: {tracker_type.title()}

    You can view and manage your trackers at:
    {trackers_link}

    Thank you,
    The SpaceBridge Team
    """

    html_body = f"""
    <html>
    <body>
        <h2>New tracker registered</h2>
        <p>You have successfully registered a new tracker in SpaceBridge:</p>
        <p>
            <strong>Name:</strong> {tracker_name}<br>
            <strong>Type:</strong> {tracker_type.title()}
        </p>
        <p>You can <a href="{trackers_link}">view and manage your trackers here</a>.</p>
        <p>Thank you,<br>The SpaceBridge Team</p>
    </body>
    </html>
    """

    send_email(user_email, subject, text_body, html_body)
