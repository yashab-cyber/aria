from core.tool_registry import aria_tool
from config import config

class EmailManager:
    @aria_tool(name="send_email", description="Sends an email.")
    async def send_email(self, to: str, subject: str, body: str) -> str:
        if not config.email_user or not config.email_pass:
            return "Email credentials not configured in .env"
            
        # Actual SMTP logic would go here
        return f"Simulated sending email to {to} with subject '{subject}'"

email_manager = EmailManager()
