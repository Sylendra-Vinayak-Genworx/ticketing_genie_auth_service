from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self) -> None:
        settings = get_settings()
        self._host = settings.SMTP_HOST
        self._port = settings.SMTP_PORT
        self._user = settings.SMTP_USER
        self._password = settings.SMTP_PASSWORD
        self._from_name = getattr(settings, "SMTP_FROM_NAME", "Support Team")

    # ------------------------------------------------------------------ #
    # Core send                                                            #
    # ------------------------------------------------------------------ #

    def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> None:
        """
        Send an email via Gmail SMTP (TLS on port 587).
        Raises on any SMTP error so the caller can handle/retry.
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self._from_name} <{self._user}>"
        msg["To"] = to

        if text:
            msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(self._host, self._port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(self._user, self._password)
                smtp.sendmail(self._user, to, msg.as_string())
            logger.info("email_sent: to=%s subject=%r", to, subject)
        except smtplib.SMTPException as exc:
            logger.error("email_failed: to=%s subject=%r error=%s", to, subject, exc)
            raise

    # ------------------------------------------------------------------ #
    # Invite email                                                         #
    # ------------------------------------------------------------------ #

    def send_team_invite(
        self,
        *,
        to: str,
        full_name: str,
        role: str,
        team_name: str,
        temporary_password: str,
        login_url: str,
    ) -> None:
        """
        Send a team invite email with the user's credentials.
        Called right after admin creates a new user in the dashboard.
        """
        subject = f"You've been invited to join {team_name}"
        html = _invite_html(
            full_name=full_name,
            role=role,
            team_name=team_name,
            email=to,
            temporary_password=temporary_password,
            login_url=login_url,
        )
        text = _invite_text(
            full_name=full_name,
            role=role,
            team_name=team_name,
            email=to,
            temporary_password=temporary_password,
            login_url=login_url,
        )
        self.send(to=to, subject=subject, html=html, text=text)

    def send_user_invite(
        self,
        *,
        to: str,
        full_name: str,
        role: str,
        temporary_password: str,
        login_url: str,
    ) -> None:
        """
        Send a welcome email with the user's credentials, without a team context.
        """
        subject = "Welcome to Ticketing Genie"
        html = _user_invite_html(
            full_name=full_name,
            role=role,
            email=to,
            temporary_password=temporary_password,
            login_url=login_url,
        )
        text = _user_invite_text(
            full_name=full_name,
            role=role,
            email=to,
            temporary_password=temporary_password,
            login_url=login_url,
        )
        self.send(to=to, subject=subject, html=html, text=text)

# ------------------------------------------------------------------ #
# Email templates                                                      #
# ------------------------------------------------------------------ #

def _invite_html(
    *,
    full_name: str,
    role: str,
    team_name: str,
    email: str,
    temporary_password: str,
    login_url: str,
) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: auto; padding: 24px;">
  <h2 style="color: #4F46E5;">You've been added to {team_name}</h2>
  <p>Hi {full_name},</p>
  <p>An admin has created an account for you. Here are your login credentials:</p>

  <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
    <tr>
      <td style="padding: 8px; background: #F3F4F6; font-weight: bold; width: 40%;">Email</td>
      <td style="padding: 8px; background: #F9FAFB;">{email}</td>
    </tr>
    <tr>
      <td style="padding: 8px; background: #F3F4F6; font-weight: bold;">Temporary Password</td>
      <td style="padding: 8px; background: #F9FAFB; font-family: monospace; letter-spacing: 2px;">{temporary_password}</td>
    </tr>
    <tr>
      <td style="padding: 8px; background: #F3F4F6; font-weight: bold;">Role</td>
      <td style="padding: 8px; background: #F9FAFB;">{role.capitalize()}</td>
    </tr>
    <tr>
      <td style="padding: 8px; background: #F3F4F6; font-weight: bold;">Team</td>
      <td style="padding: 8px; background: #F9FAFB;">{team_name}</td>
    </tr>
  </table>

  <p>
    <a href="{login_url}"
       style="display: inline-block; background: #4F46E5; color: white;
              padding: 12px 24px; border-radius: 6px; text-decoration: none;
              font-weight: bold;">
      Log In Now
    </a>
  </p>

  <p style="color: #6B7280; font-size: 13px;">
    For security, please change your password after your first login.<br>
    If you weren't expecting this email, you can safely ignore it.
  </p>
</body>
</html>
"""


def _invite_text(
    *,
    full_name: str,
    role: str,
    team_name: str,
    email: str,
    temporary_password: str,
    login_url: str,
) -> str:
    return f"""Hi {full_name},

You've been added to {team_name} as {role.capitalize()}.

Your login credentials:
  Email:              {email}
  Temporary Password: {temporary_password}
  Role:               {role.capitalize()}
  Team:               {team_name}

Log in here: {login_url}

Please change your password after your first login.
If you weren't expecting this email, you can safely ignore it.
"""

def _user_invite_html(
    *,
    full_name: str,
    role: str,
    email: str,
    temporary_password: str,
    login_url: str,
) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: auto; padding: 24px;">
  <h2 style="color: #4F46E5;">Welcome to Ticketing Genie</h2>
  <p>Hi {full_name},</p>
  <p>An admin has created an account for you. Here are your login credentials:</p>

  <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
    <tr>
      <td style="padding: 8px; background: #F3F4F6; font-weight: bold; width: 40%;">Email</td>
      <td style="padding: 8px; background: #F9FAFB;">{email}</td>
    </tr>
    <tr>
      <td style="padding: 8px; background: #F3F4F6; font-weight: bold;">Temporary Password</td>
      <td style="padding: 8px; background: #F9FAFB; font-family: monospace; letter-spacing: 2px;">{temporary_password}</td>
    </tr>
    <tr>
      <td style="padding: 8px; background: #F3F4F6; font-weight: bold;">Role</td>
      <td style="padding: 8px; background: #F9FAFB;">{role.capitalize()}</td>
    </tr>
  </table>

  <p>
    <a href="{login_url}"
       style="display: inline-block; background: #4F46E5; color: white;
              padding: 12px 24px; border-radius: 6px; text-decoration: none;
              font-weight: bold;">
      Log In Now
    </a>
  </p>

  <p style="color: #6B7280; font-size: 13px;">
    For security, please change your password after your first login.<br>
    If you weren't expecting this email, you can safely ignore it.
  </p>
</body>
</html>
"""

def _user_invite_text(
    *,
    full_name: str,
    role: str,
    email: str,
    temporary_password: str,
    login_url: str,
) -> str:
    return f"""Hi {full_name},

Welcome to Ticketing Genie!

Your login credentials:
  Email:              {email}
  Temporary Password: {temporary_password}
  Role:               {role.capitalize()}

Log in here: {login_url}

Please change your password after your first login.
If you weren't expecting this email, you can safely ignore it.
"""


# Module-level singleton
email_service = EmailService()