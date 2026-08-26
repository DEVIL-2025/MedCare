import os
import re
import smtplib
import logging
import asyncio
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict, Any, Union
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models.settings import SystemSetting

logger = logging.getLogger("MedCareControlTower.EmailService")


def sanitize_recipients(to: Union[List[str], str, None]) -> List[str]:
    """
    Sanitizes recipient email addresses: splits multi-recipient strings,
    strips whitespace, removes empty values, filters valid formats,
    and deduplicates while preserving order.
    """
    if not to:
        return []
    
    raw_list = [to] if isinstance(to, str) else list(to)
    split_list = []
    for item in raw_list:
        if isinstance(item, str):
            # Split by comma, semicolon, newline or spaces
            parts = re.split(r'[,;\n\r]+', item)
            split_list.extend(parts)
        else:
            split_list.append(str(item))

    seen = set()
    cleaned = []
    for email in split_list:
        e = email.strip()
        # Extract email address if wrapped in <...>
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', e)
        if match:
            extracted = match.group(0).lower()
            if extracted not in seen:
                seen.add(extracted)
                cleaned.append(extracted)
    return cleaned


class EmailService:
    """
    Asynchronous, non-blocking email delivery service supporting Resend API,
    standard SMTP, and simulated test logging.
    Strictly delivers to user-configured recipient email addresses with per-recipient
    loop delivery for Resend API and robust error capturing.
    """

    @classmethod
    async def get_effective_config(cls, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Resolves effective email configuration prioritizing database system_settings,
        falling back to config.settings and environment variables.
        """
        resend_key = settings.RESEND_API_KEY or os.getenv("RESEND_API_KEY", "")
        email_from = settings.EMAIL_FROM
        smtp_host = settings.SMTP_HOST
        smtp_port = settings.SMTP_PORT
        smtp_user = settings.SMTP_USER
        smtp_pass = settings.SMTP_PASSWORD
        recipient_override = None

        if session:
            try:
                res = await session.execute(
                    select(SystemSetting).where(
                        SystemSetting.key.in_([
                            "resend_api_key",
                            "email_from",
                            "alert_recipient_email",
                            "smtp_host",
                            "smtp_port",
                            "smtp_user",
                            "smtp_password"
                        ])
                    )
                )
                settings_rows = res.scalars().all()
                settings_map = {s.key: s.value for s in settings_rows if s.value}

                if settings_map.get("resend_api_key"):
                    resend_key = settings_map["resend_api_key"].strip()
                if settings_map.get("email_from"):
                    email_from = settings_map["email_from"].strip()
                if settings_map.get("alert_recipient_email"):
                    recipient_override = settings_map["alert_recipient_email"].strip()
                if settings_map.get("smtp_host"):
                    smtp_host = settings_map["smtp_host"].strip()
                if settings_map.get("smtp_port"):
                    try:
                        smtp_port = int(settings_map["smtp_port"])
                    except ValueError:
                        pass
                if settings_map.get("smtp_user"):
                    smtp_user = settings_map["smtp_user"].strip()
                if settings_map.get("smtp_password"):
                    smtp_pass = settings_map["smtp_password"].strip()
            except Exception as e:
                logger.debug("[EmailService] Could not load DB settings: %s", str(e))

        return {
            "resend_api_key": resend_key,
            "email_from": email_from,
            "recipient_override": recipient_override,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_user": smtp_user,
            "smtp_password": smtp_pass
        }

    @classmethod
    async def send_email(
        cls,
        to: Union[List[str], str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        from_email: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Dispatches an email asynchronously via Resend API (with per-recipient loop delivery)
        or standard SMTP.
        Captures exact API errors for HTTP >= 400 and returns structured diagnostic payload.
        """
        cfg = await cls.get_effective_config(session)
        raw_to = cfg.get("recipient_override") or to
        recipients = sanitize_recipients(raw_to)

        if not recipients:
            logger.warning("[EmailService] No valid recipient email addresses provided after sanitization.")
            return {
                "status": "FAILED",
                "error": "No valid recipient email address configured",
                "recipients": [],
                "delivery_results": []
            }

        sender = from_email or cfg["email_from"]
        resend_key = cfg["resend_api_key"]

        # 1. Resend API Transport (with Per-Recipient Loop Delivery)
        if resend_key:
            # Strict Resend Configuration Defaults:
            # Must use onboarding@resend.dev unless a custom verified domain is active
            unverified_domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "medcarepharma.com", "example.com"]
            if not sender or any(domain in sender.lower() for domain in unverified_domains) or "resend.dev" not in sender.lower():
                effective_sender = "MedCare Control Tower <onboarding@resend.dev>"
            else:
                effective_sender = sender

            delivery_results = []
            successful_recipients = []
            failed_recipients = []

            async with httpx.AsyncClient(timeout=12.0) as client:
                for single_recipient in recipients:
                    payload = {
                        "from": effective_sender,
                        "to": [single_recipient],
                        "subject": subject,
                        "html": html_body,
                    }
                    if text_body:
                        payload["text"] = text_body

                    try:
                        resp = await client.post(
                            "https://api.resend.com/emails",
                            headers={
                                "Authorization": f"Bearer {resend_key}",
                                "Content-Type": "application/json"
                            },
                            json=payload
                        )

                        if resp.status_code in [200, 201]:
                            data = resp.json()
                            msg_id = data.get("id")
                            logger.info("[EmailService] Successfully sent email via Resend API to %s: %s (id: %s)", single_recipient, subject, msg_id)
                            successful_recipients.append(single_recipient)
                            delivery_results.append({
                                "recipient": single_recipient,
                                "status": "SENT",
                                "id": msg_id,
                                "status_code": resp.status_code
                            })
                        else:
                            # Capture and log explicit JSON error payload from Resend API
                            err_json = {}
                            try:
                                err_json = resp.json()
                            except Exception:
                                pass
                            
                            err_msg = err_json.get("message") or resp.text
                            err_name = err_json.get("name", "Error")
                            logger.warning(
                                "[EmailService] Resend API failed for %s with HTTP %s: %s (Error Payload: %s)",
                                single_recipient, resp.status_code, err_msg, resp.text
                            )
                            failed_recipients.append(single_recipient)
                            delivery_results.append({
                                "recipient": single_recipient,
                                "status": "FAILED",
                                "error": err_msg,
                                "name": err_name,
                                "status_code": resp.status_code,
                                "raw_response": resp.text
                            })

                    except Exception as e:
                        logger.warning("[EmailService] Exception dispatching Resend to %s: %s", single_recipient, str(e))
                        failed_recipients.append(single_recipient)
                        delivery_results.append({
                            "recipient": single_recipient,
                            "status": "FAILED",
                            "error": str(e),
                            "status_code": 500
                        })

            # Determine overall aggregate delivery status
            if successful_recipients and not failed_recipients:
                overall_status = "SENT"
                primary_id = delivery_results[0].get("id")
                err = None
            elif successful_recipients and failed_recipients:
                overall_status = "PARTIAL"
                primary_id = next((d.get("id") for d in delivery_results if d.get("id")), None)
                err = f"Delivered to {len(successful_recipients)}/{len(recipients)} recipients. Failed: {', '.join(failed_recipients)}"
            else:
                overall_status = "FAILED"
                primary_id = None
                first_failure = delivery_results[0] if delivery_results else {}
                err = first_failure.get("error", "Failed delivering to all recipients")

            return {
                "status": overall_status,
                "provider": "resend",
                "id": primary_id,
                "recipients": recipients,
                "successful_recipients": successful_recipients,
                "failed_recipients": failed_recipients,
                "delivery_results": delivery_results,
                "error": err
            }

        # 2. SMTP Transport
        if cfg["smtp_host"]:
            try:
                def _send_smtp():
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = subject
                    msg["From"] = sender or (cfg.get("smtp_user") or "alerts@medcare.local")
                    msg["To"] = ", ".join(recipients)

                    if text_body:
                        msg.attach(MIMEText(text_body, "plain", "utf-8"))
                    msg.attach(MIMEText(html_body, "html", "utf-8"))

                    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=10) as server:
                        server.ehlo()
                        if server.has_extn("STARTTLS"):
                            server.starttls()
                            server.ehlo()
                        if cfg["smtp_user"] and cfg["smtp_password"]:
                            server.login(cfg["smtp_user"], cfg["smtp_password"])
                        server.sendmail(sender or cfg["smtp_user"], recipients, msg.as_string())

                await asyncio.to_thread(_send_smtp)
                logger.info("[EmailService] Sent email via SMTP to %s: %s", recipients, subject)
                return {
                    "status": "SENT",
                    "provider": "smtp",
                    "recipients": recipients,
                    "successful_recipients": recipients,
                    "failed_recipients": [],
                    "delivery_results": [{"recipient": r, "status": "SENT"} for r in recipients]
                }

            except Exception as e:
                logger.warning("[EmailService] Error dispatching via SMTP: %s", str(e))
                return {
                    "status": "FAILED",
                    "provider": "smtp",
                    "error": str(e),
                    "recipients": recipients,
                    "failed_recipients": recipients,
                    "delivery_results": [{"recipient": r, "status": "FAILED", "error": str(e)} for r in recipients]
                }

        # 3. Simulated / Development Transport
        simulated_id = f"sim-{uuid.uuid4().hex[:12]}"
        logger.info("[EmailService] [SIMULATED DELIVERY] To: %s | Subject: %s | ID: %s", recipients, subject, simulated_id)
        return {
            "status": "SIMULATED",
            "provider": "simulation",
            "id": simulated_id,
            "recipients": recipients,
            "successful_recipients": recipients,
            "failed_recipients": [],
            "delivery_results": [{"recipient": r, "status": "SIMULATED", "id": simulated_id} for r in recipients]
        }


email_service = EmailService()
