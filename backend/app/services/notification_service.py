from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.notification import NotificationLog
from backend.app.models.alert import Alert


class NotificationService:
    """
    Multi-channel notification dispatcher supporting Email, SMS, WhatsApp, and In-App alerts.
    """

    @staticmethod
    async def dispatch_notification(
        session: AsyncSession,
        channel: str,
        recipient: str,
        alert_id: Optional[str],
        subject: str,
        message: str
    ) -> NotificationLog:
        """
        Dispatches notification to the designated channel and creates an audit record.
        """
        ch = channel.upper()
        if ch not in ["EMAIL", "SMS", "WHATSAPP", "IN_APP"]:
            raise ValueError(f"Invalid notification channel: {channel}")

        # Format simulated message payload per channel
        if ch == "EMAIL":
            formatted_body = (
                f"Subject: {subject}\n\n"
                f"Dear Supply Chain Team,\n\n"
                f"{message}\n\n"
                f"Please review in MedCare Pharma SCM Control Tower.\n"
                f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        elif ch == "WHATSAPP":
            formatted_body = (
                f"🚨 *MedCare Pharma SCM Alert*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📌 *{subject}*\n\n"
                f"{message}\n\n"
                f"🔗 *Quick Action Link*: https://controltower.medcare.com/alerts/{alert_id or ''}"
            )
        elif ch == "SMS":
            formatted_body = f"MedCare Alert: {subject}. {message[:120]}... Action required."
        else:
            formatted_body = message

        log = NotificationLog(
            alert_id=alert_id,
            channel=ch,
            recipient=recipient,
            subject=subject,
            message_body=formatted_body,
            status="DELIVERED" if ch in ["EMAIL", "WHATSAPP", "SMS"] else "SENT",
            timestamp=datetime.utcnow()
        )
        session.add(log)
        await session.flush()
        return log
