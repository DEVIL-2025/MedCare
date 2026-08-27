import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.database import AsyncSessionLocal
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.auth import User
from backend.app.models.notification import NotificationLog
from backend.app.models.alert import Alert
from backend.app.models.settings import SystemSetting
from backend.app.services.email_service import EmailService, sanitize_recipients
from backend.app.utils.timezone import format_ist_datetime, get_now_ist

logger = logging.getLogger("MedCareControlTower.EmailAlertService")


class EmailAlertService:
    """
    Dynamic, zero-static Low-Stock Consolidated Digest Email service reading live state from PostgreSQL.
    Aggregates all flagged low-stock items into a single consolidated email digest.
    Features 24-hour deduplication cooldown, pharma-styled HTML formatting,
    and isolated asynchronous background execution.
    """

    @staticmethod
    def render_consolidated_digest_html(
        items: List[Dict[str, Any]],
        frontend_url: str,
        interval_hours: int = 2
    ) -> str:
        """
        Generates an executive, pharma-grade responsive HTML email digest template
        aggregating multiple low-stock items into a structured table.
        """
        item_count = len(items)
        unique_dcs = sorted(list(set(it["warehouse_id"] for it in items)))
        dc_count = len(unique_dcs)
        total_deficit = sum(it["deficit"] for it in items)
        critical_count = sum(1 for it in items if it["status"] in ["CRITICAL", "OUT_OF_STOCK"])

        action_url = f"{frontend_url}/replenishment"
        timestamp_ist = format_ist_datetime(get_now_ist(), "%d %b %Y, %I:%M:%S %p IST")
        timestamp_utc = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

        # Generate Table Rows
        rows_html = ""
        for idx, it in enumerate(items):
            bg_color = "#ffffff" if idx % 2 == 0 else "#f8fafc"
            status_color = "#b91c1c" if it["status"] in ["CRITICAL", "OUT_OF_STOCK"] else "#c2410c"
            status_bg = "#fef2f2" if it["status"] in ["CRITICAL", "OUT_OF_STOCK"] else "#fff7ed"

            rows_html += f"""
            <tr style="background-color: {bg_color}; border-bottom: 1px solid #e2e8f0;">
              <td style="padding: 12px 14px; font-size: 13px; color: #0f172a; font-weight: 700; vertical-align: top;">
                {it["product_name"]}
                <div style="font-size: 11px; color: #64748b; font-family: monospace; font-weight: 500; margin-top: 2px;">
                  {it["sku"]} &bull; {it["category"]}
                </div>
              </td>
              <td style="padding: 12px 14px; font-size: 12.5px; color: #334155; vertical-align: top;">
                <span style="font-weight: 700; color: #0f172a;">{it["warehouse_id"]}</span>
                <div style="font-size: 11px; color: #64748b; margin-top: 2px;">{it["warehouse_name"]}</div>
              </td>
              <td style="padding: 12px 14px; font-size: 13.5px; color: #b91c1c; font-weight: 800; text-align: right; vertical-align: top;">
                {it["available_stock"]:,}
                <div style="font-size: 10.5px; color: #64748b; font-weight: 400;">Phys: {it["current_stock"]:,}</div>
              </td>
              <td style="padding: 12px 14px; font-size: 12.5px; color: #334155; text-align: right; vertical-align: top;">
                {it["reorder_point"]:,}
                <div style="font-size: 10.5px; color: #94a3b8;">Safe: {it["safety_stock"]:,}</div>
              </td>
              <td style="padding: 12px 14px; font-size: 13px; color: #b91c1c; font-weight: 800; text-align: right; vertical-align: top;">
                -{it["deficit"]:,}
              </td>
              <td style="padding: 12px 14px; text-align: center; vertical-align: top;">
                <span style="display: inline-block; background-color: {status_bg}; color: {status_color}; font-size: 10.5px; font-weight: 700; padding: 3px 8px; border-radius: 9999px; text-transform: uppercase; border: 1px solid {status_color}30;">
                  {it["status"].replace('_', ' ')}
                </span>
              </td>
            </tr>
            """

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Consolidated Low Stock Digest</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 30px 15px;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table role="presentation" width="100%" max-width="720" style="max-width: 720px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.08); border: 1px solid #cbd5e1;">
          
          <!-- Header Banner -->
          <tr>
            <td style="background-color: #1b4332; padding: 24px 30px; text-align: left;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td>
                    <div style="font-size: 11.5px; font-weight: 700; color: #86efac; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 4px;">
                      MedCare Pharma SCM Control Tower
                    </div>
                    <div style="font-size: 21px; font-weight: 800; color: #ffffff; line-height: 1.3;">
                      ⚠️ Consolidated Low-Stock Digest
                    </div>
                  </td>
                  <td align="right" style="vertical-align: middle;">
                    <span style="background-color: #b91c1c; color: #ffffff; font-size: 11px; font-weight: 800; padding: 5px 12px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.5px;">
                      {item_count} ITEMS FLAGGED
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Summary Metric Cards -->
          <tr>
            <td style="padding: 24px 30px 16px 30px;">
              <p style="margin: 0 0 16px 0; font-size: 14px; line-height: 1.6; color: #334155;">
                Automated inventory scan detected <strong>{item_count} pharmaceutical {('item' if item_count == 1 else 'items')}</strong> operating below required reorder thresholds across <strong>{dc_count} Distribution {('Center' if dc_count == 1 else 'Centers')}</strong>. Review the consolidated summary below:
              </p>

              <!-- Metric Grid -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 20px;">
                <tr>
                  <td width="32%" style="background-color: #f8fafc; padding: 14px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
                    <div style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">Low-Stock Items</div>
                    <div style="font-size: 20px; font-weight: 800; color: #0f172a; margin-top: 4px;">{item_count}</div>
                  </td>
                  <td width="2%"></td>
                  <td width="32%" style="background-color: #fef2f2; padding: 14px; border-radius: 8px; border: 1px solid #fecaca; text-align: center;">
                    <div style="font-size: 11px; color: #991b1b; font-weight: 600; text-transform: uppercase;">Total Units Deficit</div>
                    <div style="font-size: 20px; font-weight: 800; color: #b91c1c; margin-top: 4px;">-{total_deficit:,}</div>
                  </td>
                  <td width="2%"></td>
                  <td width="32%" style="background-color: #f8fafc; padding: 14px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
                    <div style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">Affected DCs</div>
                    <div style="font-size: 20px; font-weight: 800; color: #1b4332; margin-top: 4px;">{dc_count}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Consolidated Low-Stock Table -->
          <tr>
            <td style="padding: 0 30px 20px 30px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; border-collapse: collapse;">
                <thead>
                  <tr style="background-color: #0f172a; color: #ffffff; text-align: left;">
                    <th style="padding: 11px 14px; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Product & SKU</th>
                    <th style="padding: 11px 14px; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">DC Location</th>
                    <th style="padding: 11px 14px; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: right;">Available</th>
                    <th style="padding: 11px 14px; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: right;">Reorder Pt</th>
                    <th style="padding: 11px 14px; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: right;">Deficit</th>
                    <th style="padding: 11px 14px; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: center;">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rows_html}
                </tbody>
              </table>
            </td>
          </tr>

          <!-- Single Action CTA Button -->
          <tr>
            <td style="padding: 10px 30px 28px 30px; text-align: center;">
              <a href="{action_url}" style="display: inline-block; background-color: #1b4332; color: #ffffff; text-decoration: none; font-size: 14.5px; font-weight: 700; padding: 14px 32px; border-radius: 8px; box-shadow: 0 4px 10px rgba(27,67,50,0.35);">
                Review Replenishment & Transfers &rarr;
              </a>
              <div style="margin-top: 12px; font-size: 11.5px; color: #64748b;">
                Clicking opens the MedCare Control Tower Replenishment & FEFO Network Balancing module.
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; padding: 18px 30px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 11.5px; color: #64748b; line-height: 1.6;">
              <div><strong>MedCare Pharma SCM Control Tower</strong> &bull; Single Source of Truth: PostgreSQL</div>
              <div style="margin-top: 4px; color: #94a3b8;">
                Alert generated on {timestamp_ist} ({timestamp_utc}) &bull; {interval_hours}-hour periodic digest interval active
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    @classmethod
    async def get_configured_interval_hours(cls, session: AsyncSession) -> int:
        """
        Fetches the user-configured low-stock digest interval in hours from SystemSetting.
        Defaults to 2 hours if not explicitly set.
        """
        try:
            res = await session.execute(
                select(SystemSetting.value).where(SystemSetting.key == "alert_interval_hours")
            )
            val = res.scalar()
            if val:
                return max(1, int(float(val)))
        except Exception as e:
            logger.debug("[EmailAlertService] Error reading alert_interval_hours: %s", str(e))
        return 2

    @classmethod
    async def is_item_in_cooldown(
        cls,
        session: AsyncSession,
        sku: str,
        warehouse_id: str,
        cooldown_hours: Optional[int] = None
    ) -> bool:
        """
        Checks NotificationLog to verify whether an email alert for this specific (sku, warehouse_id)
        was successfully delivered within the past cooldown window (configured in Settings, default 2h).
        Only checks logs with status SENT or DELIVERED (failed attempts do not trigger cooldown).
        """
        if cooldown_hours is None:
            cooldown_hours = await cls.get_configured_interval_hours(session)

        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=cooldown_hours)

        res = await session.execute(
            select(func.count(NotificationLog.id)).where(
                and_(
                    NotificationLog.channel == "EMAIL",
                    NotificationLog.status.in_(["SENT", "DELIVERED"]),
                    NotificationLog.timestamp >= cutoff,
                    NotificationLog.message_body.like(f"%{sku}%"),
                    NotificationLog.message_body.like(f"%{warehouse_id}%")
                )
            )
        )
        count = res.scalar() or 0
        return count > 0

    @classmethod
    async def get_active_recipient_emails(cls, session: AsyncSession) -> List[str]:
        """
        Fetches the designated recipient email address entered by the user in Settings.
        Strictly reads from database system_settings table (alert_recipient_email) or config.
        Does NOT query all active users from the users table.
        """
        res_setting = await session.execute(
            select(SystemSetting.value).where(
                SystemSetting.key.in_(["alert_recipient_email", "notification_recipient_email"])
            )
        )
        for row in res_setting.scalars().all():
            if row:
                recipients = sanitize_recipients(row)
                if recipients:
                    return recipients

        # Fallback to config if explicitly set
        if getattr(settings, "EMAIL_TO", None):
            recipients = sanitize_recipients(settings.EMAIL_TO)
            if recipients:
                return recipients

        return []

    @classmethod
    async def check_and_dispatch_low_stock_email_alerts(
        cls,
        session: AsyncSession,
        target_sku: Optional[str] = None,
        target_warehouse_id: Optional[str] = None,
        force_ignore_cooldown: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Scans PostgreSQL database for inventory items where available_stock <= reorder_point.
        Deduplicates against the 24-hour alert history, aggregates all qualifying items
        into a SINGLE consolidated email digest, and dispatches via EmailService.
        """
        # 1. Query live inventory directly from database with robust null coalescing and outer joins
        query = (
            select(Inventory, Product, Warehouse)
            .outerjoin(Product, Inventory.sku == Product.sku)
            .outerjoin(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .where(
                and_(
                    func.coalesce(Product.is_active, True) == True,
                    func.coalesce(Warehouse.is_active, True) == True,
                    (func.coalesce(Inventory.current_stock, 0) - func.coalesce(Inventory.reserved_stock, 0)) <= func.coalesce(Inventory.reorder_point, 0)
                )
            )
            .order_by(Inventory.sku.asc(), Inventory.warehouse_id.asc())
        )

        if target_sku:
            query = query.where(func.upper(Inventory.sku) == target_sku.strip().upper())
        if target_warehouse_id:
            query = query.where(func.upper(Inventory.warehouse_id) == target_warehouse_id.strip().upper())

        res = await session.execute(query)
        low_stock_records = res.all()

        logger.info(
            "[EmailAlertService] Database scan found %d items meeting low-stock condition: %s",
            len(low_stock_records),
            [(inv.sku, inv.warehouse_id) for inv, prod, wh in low_stock_records]
        )

        if not low_stock_records:
            logger.info("[EmailAlertService] No low-stock items detected in PostgreSQL.")
            return []

        # 2. Filter items based on dynamic deduplication cooldown interval
        interval_hours = await cls.get_configured_interval_hours(session)
        qualifying_items = []
        for inv, prod, wh in low_stock_records:
            sku = inv.sku
            wh_id = inv.warehouse_id
            curr_stock = inv.current_stock if inv.current_stock is not None else 0
            resv_stock = inv.reserved_stock if inv.reserved_stock is not None else 0
            reorder_pt = inv.reorder_point if inv.reorder_point is not None else 0
            avail_stock = max(0, curr_stock - resv_stock)
            deficit = max(0, reorder_pt - avail_stock)

            if not force_ignore_cooldown:
                in_cooldown = await cls.is_item_in_cooldown(session, sku, wh_id, cooldown_hours=interval_hours)
                if in_cooldown:
                    logger.info("[EmailAlertService] %dh Cooldown active for %s @ %s (omitted from digest)", interval_hours, sku, wh_id)
                    continue

            qualifying_items.append({
                "sku": sku,
                "product_name": prod.name if prod and prod.name else sku,
                "category": prod.category if prod and prod.category else "General",
                "warehouse_id": wh_id,
                "warehouse_name": wh.name if wh and wh.name else wh_id,
                "warehouse_location": wh.location if wh and wh.location else "Central Storage",
                "current_stock": curr_stock,
                "available_stock": avail_stock,
                "reorder_point": reorder_pt,
                "safety_stock": inv.safety_stock if inv.safety_stock is not None else 0,
                "deficit": deficit,
                "status": inv.status or ("CRITICAL" if avail_stock == 0 else "LOW_STOCK"),
            })

        logger.info(
            "[EmailAlertService] Digest payload contains %d qualifying items: %s",
            len(qualifying_items),
            [(it['sku'], it['warehouse_id']) for it in qualifying_items]
        )

        if not qualifying_items:
            logger.info("[EmailAlertService] All %d low-stock items are currently within %dh cooldown.", len(low_stock_records), interval_hours)
            return []

        # 3. Query dynamic recipients from database
        recipients = await cls.get_active_recipient_emails(session)
        if not recipients:
            logger.warning("[EmailAlertService] No active recipient email addresses found in database.")
            return []

        # 4. Construct Single Consolidated Email Payload
        item_count = len(qualifying_items)
        subject = f"[ALERT] Consolidated Low Stock Digest - {item_count} {'Item Requires' if item_count == 1 else 'Items Require'} Attention"

        html_body = cls.render_consolidated_digest_html(
            items=qualifying_items,
            frontend_url=settings.APP_FRONTEND_URL,
            interval_hours=interval_hours
        )

        text_lines = [
            f"{subject}\n",
            f"Automated inventory scan detected {item_count} items below reorder threshold:\n"
        ]
        for it in qualifying_items:
            text_lines.append(
                f"- {it['product_name']} ({it['sku']}) @ {it['warehouse_id']}: {it['available_stock']} units avail (Reorder Pt: {it['reorder_point']}, Deficit: -{it['deficit']})"
            )
        text_lines.append(f"\nReview replenishment at: {settings.APP_FRONTEND_URL}/replenishment")
        text_body = "\n".join(text_lines)

        # 5. Dispatch Single Consolidated Email Asynchronously
        send_res = await EmailService.send_email(
            to=recipients,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            session=session
        )

        # 6. Find any matching open alert ID if present (FK constraint)
        first_sku = qualifying_items[0]["sku"]
        first_wh = qualifying_items[0]["warehouse_id"]
        alt_res = await session.execute(
            select(Alert.id).where(
                and_(
                    Alert.sku == first_sku,
                    Alert.warehouse_id == first_wh,
                    Alert.status != "Resolved"
                )
            ).order_by(Alert.created_at.desc())
        )
        matched_alert_id = alt_res.scalars().first()

        delivered_recipients = send_res.get("successful_recipients") or send_res.get("recipients", recipients)
        recipient_str = ", ".join(delivered_recipients) if delivered_recipients else ", ".join(recipients)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        delivery_status = send_res.get("status", "FAILED")
        error_detail = send_res.get("error")

        # Include error note in log if delivery failed
        logged_body = html_body
        if error_detail and delivery_status == "FAILED":
            logged_body = f"<!-- Delivery Error: {error_detail} -->\n" + html_body

        log = NotificationLog(
            alert_id=matched_alert_id,
            channel="EMAIL",
            recipient=recipient_str,
            subject=subject,
            message_body=logged_body,
            status=delivery_status,
            timestamp=now_utc
        )
        session.add(log)
        await session.commit()

        logger.info("[EmailAlertService] Dispatched 1 consolidated digest covering %d items. Status: %s. Recipients: %s", item_count, delivery_status, recipient_str)

        return [{
            "digest_subject": subject,
            "item_count": item_count,
            "items": qualifying_items,
            "recipients": delivered_recipients,
            "delivery_status": delivery_status,
            "provider": send_res.get("provider"),
            "successful_recipients": send_res.get("successful_recipients", []),
            "failed_recipients": send_res.get("failed_recipients", []),
            "delivery_results": send_res.get("delivery_results", []),
            "error": error_detail
        }]


def trigger_async_low_stock_check(sku: Optional[str] = None, warehouse_id: Optional[str] = None, force_ignore_cooldown: bool = False):
    """
    Isolated background task trigger that runs in a completely detached coroutine/thread.
    Creates its own database session and guarantees that any network or email error
    NEVER impacts the calling transaction.
    """
    async def _runner():
        try:
            async with AsyncSessionLocal() as session:
                await EmailAlertService.check_and_dispatch_low_stock_email_alerts(
                    session=session,
                    target_sku=sku,
                    target_warehouse_id=warehouse_id,
                    force_ignore_cooldown=force_ignore_cooldown
                )
        except Exception as e:
            logger.warning("[EmailAlertService] Background low-stock check encountered error: %s", str(e))

    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(_runner())
        else:
            asyncio.run(_runner())
    except RuntimeError:
        import threading
        threading.Thread(target=lambda: asyncio.run(_runner()), daemon=True).start()
    except Exception as e:
        logger.warning("[EmailAlertService] Failed to schedule background check task: %s", str(e))


class PeriodicEmailAlertScheduler:
    """
    Automated background worker that runs continuously during FastAPI application lifespan.
    Checks PostgreSQL at regular intervals (every 60 seconds). When alert_interval_hours has
    elapsed since the last successful digest and active low-stock deficits exist in the database,
    it dispatches an updated consolidated low-stock digest email.
    """
    _task: Optional[asyncio.Task] = None
    _running: bool = False

    @classmethod
    def start(cls):
        if cls._running or cls._task is not None:
            return
        cls._running = True
        try:
            loop = asyncio.get_running_loop()
            cls._task = loop.create_task(cls._run_loop())
            logger.info("[PeriodicEmailAlertScheduler] Background periodic email worker task started.")
        except RuntimeError:
            logger.warning("[PeriodicEmailAlertScheduler] No running event loop to start background periodic email worker.")

    @classmethod
    def stop(cls):
        cls._running = False
        if cls._task:
            cls._task.cancel()
            cls._task = None
        logger.info("[PeriodicEmailAlertScheduler] Background periodic email worker stopped.")

    @classmethod
    async def _run_loop(cls):
        # Initial brief wait on server startup
        await asyncio.sleep(15)
        while cls._running:
            try:
                async with AsyncSessionLocal() as session:
                    # 1. Check if low stock alerts are enabled
                    enabled_res = await session.execute(
                        select(SystemSetting.value).where(SystemSetting.key == "low_stock_alerts_enabled")
                    )
                    enabled_val = enabled_res.scalar() or "Enabled"
                    if str(enabled_val).strip().lower() == "disabled":
                        await asyncio.sleep(60)
                        continue

                    # 2. Check configured interval in hours
                    interval_hours = await EmailAlertService.get_configured_interval_hours(session)

                    # 3. Check when the last successful email digest was dispatched
                    last_log_res = await session.execute(
                        select(NotificationLog.timestamp)
                        .where(
                            and_(
                                NotificationLog.channel == "EMAIL",
                                NotificationLog.status.in_(["SENT", "DELIVERED"])
                            )
                        )
                        .order_by(NotificationLog.timestamp.desc())
                        .limit(1)
                    )
                    last_sent_time = last_log_res.scalar()

                    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                    should_check = False
                    if last_sent_time is None:
                        should_check = True
                    else:
                        elapsed_seconds = (now_utc - last_sent_time).total_seconds()
                        if elapsed_seconds >= (interval_hours * 3600):
                            should_check = True

                    if should_check:
                        logger.info(
                            "[PeriodicEmailAlertScheduler] Periodic interval (%dh) elapsed since last digest. Running automated low-stock check...",
                            interval_hours
                        )
                        await EmailAlertService.check_and_dispatch_low_stock_email_alerts(
                            session=session,
                            force_ignore_cooldown=False
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("[PeriodicEmailAlertScheduler] Background interval check error: %s", str(e))

            # Sleep between background evaluation passes
            await asyncio.sleep(60)
