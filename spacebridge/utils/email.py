"""Email sending utility for SpaceBridge."""

import asyncio
import logging
import os
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from typing import Dict, Any
from spacebridge.config import settings

logger = logging.getLogger(__name__)

# Email configuration
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "hello@preloop.ai")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Preloop AI")
SPACEBRIDGE_URL = os.getenv("SPACEBRIDGE_URL", "https://preloop.ai")
APP_NAME = os.getenv("APP_NAME", "Preloop AI")


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
    # Remove protocol from URL
    portal_url = settings.spacebridge_url.replace("https://", "").replace("http://", "")
    msg["Subject"] = f"[{portal_url}] {subject}"
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
    verification_link = f"{SPACEBRIDGE_URL}/verify-email?token={token}"

    subject = f"Verify your {APP_NAME} account"
    text_body = f"""
    Welcome to {APP_NAME}!

    Please verify your email address by clicking the link below:

    {verification_link}

    If you didn't register for {APP_NAME}, please ignore this email.

    Thank you,
    The {APP_NAME} Team
    """

    html_body = f"""
    <html>
    <body>
        <h2>Welcome to {APP_NAME}!</h2>
        <p>Please verify your email address by clicking the link below:</p>
        <p><a href="{verification_link}">Verify your email</a></p>
        <p>If you didn't register for {APP_NAME}, please ignore this email.</p>
        <p>Thank you,<br>The {APP_NAME} Team</p>
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
    reset_link = f"{SPACEBRIDGE_URL}/reset-password?token={token}"

    subject = f"Reset your {APP_NAME} password"
    text_body = f"""
    You have requested to reset your {APP_NAME} password.

    Please click the link below to set a new password:

    {reset_link}

    If you didn't request a password reset, please ignore this email.

    Thank you,
    The {APP_NAME} Team
    """

    html_body = f"""
    <html>
    <body>
        <h2>Reset your {APP_NAME} password</h2>
        <p>You have requested to reset your {APP_NAME} password.</p>
        <p>Please click the link below to set a new password:</p>
        <p><a href="{reset_link}">Reset your password</a></p>
        <p>If you didn't request a password reset, please ignore this email.</p>
        <p>Thank you,<br>The {APP_NAME} Team</p>
    </body>
    </html>
    """

    send_email(user_email, subject, text_body, html_body)


def send_invitation_email(
    user_email: str, token: str, organization_name: str, invited_by: str
) -> None:
    """Send an invitation email to join an organization.

    Args:
        user_email: The invitee's email address.
        token: The invitation token.
        organization_name: Name of the organization they're invited to.
        invited_by: Name/email of the person who sent the invitation.
    """
    accept_link = f"{SPACEBRIDGE_URL}/invitations/accept?token={token}"

    subject = f"You've been invited to join {organization_name}"

    text_body = f"""
Hello!

{invited_by} has invited you to join {organization_name} on {APP_NAME}.

To accept this invitation and create your account, please click the link below:

{accept_link}

This invitation will expire in 7 days.

If you didn't expect this invitation, you can safely ignore this email.

Best regards,
The {APP_NAME} Team
    """.strip()

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4A90E2; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
            .button {{ display: inline-block; padding: 12px 24px; background-color: #4A90E2; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .button:hover {{ background-color: #357ABD; }}
            .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #777; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>You're Invited!</h1>
            </div>
            <div class="content">
                <p>Hello!</p>
                <p><strong>{invited_by}</strong> has invited you to join <strong>{organization_name}</strong> on {APP_NAME}.</p>
                <p>{APP_NAME} helps teams automate and streamline their development workflows with AI-powered agents.</p>
                <p style="text-align: center;">
                    <a href="{accept_link}" class="button">Accept Invitation</a>
                </p>
                <p style="font-size: 14px; color: #666;">Or copy and paste this link into your browser:</p>
                <p style="font-size: 12px; word-break: break-all; background-color: #f0f0f0; padding: 10px; border-radius: 3px;">{accept_link}</p>
                <div class="footer">
                    <p>This invitation will expire in 7 days.</p>
                    <p>If you didn't expect this invitation, you can safely ignore this email.</p>
                </div>
            </div>
        </div>
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
    trackers_link = f"{SPACEBRIDGE_URL}/console/trackers"

    subject = f"New {tracker_type.title()} tracker registered: {tracker_name}"
    text_body = f"""
    You have successfully registered a new tracker in {APP_NAME}:

    Name: {tracker_name}
    Type: {tracker_type.title()}

    You can view and manage your trackers at:
    {trackers_link}

    Thank you,
    The {APP_NAME} Team
    """

    html_body = f"""
    <html>
    <body>
        <h2>New tracker registered</h2>
        <p>You have successfully registered a new tracker in {APP_NAME}:</p>
        <p>
            <strong>Name:</strong> {tracker_name}<br>
            <strong>Type:</strong> {tracker_type.title()}
        </p>
        <p>You can <a href="{trackers_link}">view and manage your trackers here</a>.</p>
        <p>Thank you,<br>The {APP_NAME} Team</p>
    </body>
    </html>
    """

    send_email(user_email, subject, text_body, html_body)


async def send_product_notification_email(
    user_data: Dict[str, Any],
    tracker_data: Optional[Dict[str, Any]],
    source_ip: str,
) -> None:
    """Send a product notification email with user, tracker, and IP information.

    Args:
        user_data: User account information.
        tracker_data: Tracker information (optional).
        source_ip: Source IP address.

    Raises:
        EmailError: If email sending fails.
    """
    recipient_email = settings.product_team_email
    subject = "Product Notification: User Activity"

    # Filter sensitive fields
    sensitive_fields = {"password", "token", "secret", "api_key"}

    def filter_data(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not data:
            return {}
        return {k: v for k, v in data.items() if k.lower() not in sensitive_fields}

    filtered_user_data = filter_data(user_data)
    filtered_tracker_data = filter_data(tracker_data)

    body_parts = [
        "A product notification event has occurred.",
        "\nUser Data:",
    ]
    for key, value in filtered_user_data.items():
        body_parts.append(f"  {key}: {value}")

    if filtered_tracker_data:
        body_parts.append("\nTracker Data:")
        for key, value in filtered_tracker_data.items():
            body_parts.append(f"  {key}: {value}")

    body_parts.append(f"\nSource IP: {source_ip}")

    body_text = "\n".join(body_parts)

    # HTML body (optional, can be enhanced)
    html_body_parts = [
        "<html><body>",
        "<h2>Product Notification: User Activity</h2>",
        "<p>A product notification event has occurred.</p>",
        "<h3>User Data:</h3><ul>",
    ]
    for key, value in filtered_user_data.items():
        html_body_parts.append(f"<li><strong>{key}:</strong> {value}</li>")
    html_body_parts.append("</ul>")

    if filtered_tracker_data:
        html_body_parts.append("<h3>Tracker Data:</h3><ul>")
        for key, value in filtered_tracker_data.items():
            html_body_parts.append(f"<li><strong>{key}:</strong> {value}</li>")
        html_body_parts.append("</ul>")

    html_body_parts.append(f"<p><strong>Source IP:</strong> {source_ip}</p>")
    html_body_parts.append("</body></html>")
    body_html = "\n".join(html_body_parts)

    try:
        # Run send_email in a separate thread to avoid blocking asyncio event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, send_email, recipient_email, subject, body_text, body_html
        )
        logger.info(f"Product notification email sent to {recipient_email}")
    except EmailError as e:
        logger.error(f"Failed to send product notification email: {str(e)}")
        raise  # Re-raise the EmailError to be handled by the caller
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while sending product notification email: {str(e)}"
        )
        raise EmailError(f"An unexpected error occurred: {str(e)}")
