"""
A.R.I.A. Notification Manager — Multi-channel outbound notifications.

Supported channels:
  - Slack     (webhook URL)
  - Telegram  (bot token + chat ID)
  - WhatsApp  (Twilio API)
  - Email     (SMTP via aiosmtplib)
  - Discord   (webhook URL)
"""

import asyncio
from typing import Optional, Dict, List
from core.tool_registry import aria_tool
from config import config
from rich.console import Console
import aiohttp

console = Console()


class NotificationManager:
    """Unified notification dispatch for A.R.I.A."""

    def _get_configured_channels(self) -> Dict[str, bool]:
        """Return which channels have valid credentials configured."""
        return {
            "slack": bool(config.slack_webhook_url),
            "telegram": bool(config.telegram_bot_token and config.telegram_chat_id),
            "whatsapp": bool(config.twilio_account_sid and config.twilio_auth_token),
            "email": bool(config.email_user and config.email_pass),
            "discord": bool(config.discord_webhook_url),
        }

    # ── Channel Dispatchers ───────────────────────────────────────────

    async def _send_slack(self, message: str) -> str:
        url = config.slack_webhook_url
        if not url:
            return "Slack webhook URL not configured."
        async with aiohttp.ClientSession() as session:
            payload = {"text": message}
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return "Sent to Slack."
                return f"Slack error: HTTP {resp.status}"

    async def _send_telegram(self, message: str) -> str:
        token = config.telegram_bot_token
        chat_id = config.telegram_chat_id
        if not token or not chat_id:
            return "Telegram bot token or chat ID not configured."
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return "Sent to Telegram."
                body = await resp.text()
                return f"Telegram error: HTTP {resp.status} — {body[:200]}"

    async def _send_whatsapp(self, message: str) -> str:
        sid = config.twilio_account_sid
        token = config.twilio_auth_token
        from_num = config.twilio_whatsapp_from
        to_num = config.twilio_whatsapp_to
        if not all([sid, token, from_num, to_num]):
            return "Twilio WhatsApp credentials not fully configured."
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        async with aiohttp.ClientSession() as session:
            data = {
                "From": f"whatsapp:{from_num}",
                "To": f"whatsapp:{to_num}",
                "Body": message[:1600],
            }
            auth = aiohttp.BasicAuth(sid, token)
            async with session.post(url, data=data, auth=auth, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status in (200, 201):
                    return "Sent to WhatsApp."
                body = await resp.text()
                return f"WhatsApp/Twilio error: HTTP {resp.status} — {body[:200]}"

    async def _send_email(self, message: str, subject: str = "A.R.I.A. Notification") -> str:
        if not config.email_user or not config.email_pass:
            return "Email credentials not configured."
        try:
            import aiosmtplib
            from email.mime.text import MIMEText

            msg = MIMEText(message)
            msg["Subject"] = subject
            msg["From"] = config.email_user
            msg["To"] = config.email_user  # Self-notify by default

            host = config.email_host or "smtp.gmail.com"
            port = config.email_port or 587

            await aiosmtplib.send(
                msg,
                hostname=host,
                port=port,
                username=config.email_user,
                password=config.email_pass,
                use_tls=True,
            )
            return "Sent via Email."
        except ImportError:
            return "aiosmtplib not installed. Run: pip install aiosmtplib"
        except Exception as e:
            return f"Email error: {str(e)}"

    async def _send_discord(self, message: str) -> str:
        url = config.discord_webhook_url
        if not url:
            return "Discord webhook URL not configured."
        async with aiohttp.ClientSession() as session:
            # Discord limits content to 2000 chars
            payload = {"content": message[:2000]}
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status in (200, 204):
                    return "Sent to Discord."
                return f"Discord error: HTTP {resp.status}"

    # ── Core Dispatch ─────────────────────────────────────────────────

    async def send(self, channel: str, message: str, **kwargs) -> str:
        """Send a notification to a specific channel."""
        dispatchers = {
            "slack": self._send_slack,
            "telegram": self._send_telegram,
            "whatsapp": self._send_whatsapp,
            "email": self._send_email,
            "discord": self._send_discord,
        }
        fn = dispatchers.get(channel.lower())
        if not fn:
            return f"Unknown channel: '{channel}'. Available: {', '.join(dispatchers.keys())}"
        try:
            return await fn(message, **kwargs)
        except Exception as e:
            return f"Notification error ({channel}): {str(e)}"

    async def broadcast(self, message: str) -> Dict[str, str]:
        """Send a notification to ALL configured channels."""
        channels = self._get_configured_channels()
        active = [ch for ch, ok in channels.items() if ok]
        if not active:
            return {"error": "No notification channels configured."}
        results = {}
        tasks = [self.send(ch, message) for ch in active]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for ch, res in zip(active, responses):
            results[ch] = str(res)
        return results

    # ── ARIA Tools ────────────────────────────────────────────────────

    @aria_tool(
        name="send_notification",
        description="Send a notification message to a specific channel: 'slack', 'telegram', 'whatsapp', 'email', or 'discord'.",
    )
    async def send_notification(self, channel: str, message: str) -> str:
        result = await self.send(channel, message)
        console.print(f"[cyan]Notification → {channel}: {result}[/cyan]")
        return result

    @aria_tool(
        name="broadcast_notification",
        description="Send a notification to ALL configured channels simultaneously (Slack, Telegram, WhatsApp, Email, Discord).",
    )
    async def broadcast_notification(self, message: str) -> str:
        results = await self.broadcast(message)
        lines = ["Broadcast results:"]
        for ch, res in results.items():
            lines.append(f"  {ch}: {res}")
        summary = "\n".join(lines)
        console.print(f"[cyan]{summary}[/cyan]")
        return summary

    @aria_tool(
        name="list_notification_channels",
        description="Shows which notification channels are configured and ready to use.",
    )
    async def list_notification_channels(self) -> str:
        channels = self._get_configured_channels()
        lines = ["📡 Notification Channels:\n"]
        for ch, ok in channels.items():
            icon = "✅" if ok else "❌"
            lines.append(f"  {icon} {ch.capitalize()}: {'Configured' if ok else 'Not configured'}")
        return "\n".join(lines)


# Global singleton
notifier = NotificationManager()
