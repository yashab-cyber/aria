import asyncio
import imaplib
import email
from email.header import decode_header
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.tool_registry import aria_tool
from config import config

class EmailManager:
    @aria_tool(name="send_email", description="Sends an email to a recipient with a subject and body.")
    async def send_email(self, to: str, subject: str, body: str) -> str:
        if not config.email_user or not config.email_pass:
            return "Email credentials not configured in .env"
            
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = config.email_user
            msg["To"] = to

            host = config.email_host or "smtp.gmail.com"
            port = config.email_port or 587

            await aiosmtplib.send(
                msg,
                hostname=host,
                port=port,
                username=config.email_user,
                password=config.email_pass,
                use_tls=(port == 465),
                start_tls=(port == 587),
            )
            return f"Successfully sent email to {to}."
        except Exception as e:
            return f"Failed to send email: {str(e)}"

    @aria_tool(name="fetch_emails", description="Fetches headers of the latest n emails. Returns index numbers, senders, subjects, and dates.")
    async def fetch_emails(self, count: int = 5) -> str:
        if not config.email_user or not config.email_pass:
            return "Email credentials not configured in .env"
            
        host = config.email_host or ""
        imap_host = "imap.gmail.com"
        if "gmail" in host:
            imap_host = "imap.gmail.com"
        elif "outlook" in host or "office365" in host:
            imap_host = "outlook.office365.com"
        elif "yahoo" in host:
            imap_host = "imap.mail.yahoo.com"
        elif host.startswith("smtp."):
            imap_host = host.replace("smtp.", "imap.")
            
        def _fetch():
            try:
                mail = imaplib.IMAP4_SSL(imap_host)
                mail.login(config.email_user, config.email_pass)
                mail.select("inbox")
                
                status, messages = mail.search(None, "ALL")
                if status != "OK":
                    mail.logout()
                    return "Failed to search mailbox."
                    
                mail_ids = messages[0].split()
                if not mail_ids:
                    mail.logout()
                    return "No emails found in mailbox."
                    
                latest_ids = mail_ids[-count:]
                latest_ids.reverse()
                
                results = []
                for msg_id in latest_ids:
                    status, msg_data = mail.fetch(msg_id, "(RFC822.SIZE BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
                    if status != "OK":
                        continue
                    
                    raw_msg = msg_data[0][1]
                    msg = email.message_from_bytes(raw_msg)
                    
                    subject = msg.get("Subject", "(No Subject)")
                    decoded_subject, charset = decode_header(subject)[0]
                    if isinstance(decoded_subject, bytes):
                        subject = decoded_subject.decode(charset or 'utf-8', errors='ignore')
                        
                    sender = msg.get("From", "(Unknown Sender)")
                    decoded_sender, charset = decode_header(sender)[0]
                    if isinstance(decoded_sender, bytes):
                        sender = decoded_sender.decode(charset or 'utf-8', errors='ignore')
                        
                    date = msg.get("Date", "")
                    results.append(f"Index: {msg_id.decode()}\nSender: {sender}\nSubject: {subject}\nDate: {date}\n")
                    
                mail.logout()
                return "\n".join(results) or "No headers could be read."
            except Exception as e:
                return f"IMAP Error: {str(e)}"
                
        return await asyncio.get_event_loop().run_in_executor(None, _fetch)

    @aria_tool(name="read_email", description="Retrieves and reads the detailed text body of an email by its index/ID.")
    async def read_email(self, index: str) -> str:
        if not config.email_user or not config.email_pass:
            return "Email credentials not configured in .env"
            
        host = config.email_host or ""
        imap_host = "imap.gmail.com"
        if "gmail" in host:
            imap_host = "imap.gmail.com"
        elif "outlook" in host or "office365" in host:
            imap_host = "outlook.office365.com"
        elif "yahoo" in host:
            imap_host = "imap.mail.yahoo.com"
        elif host.startswith("smtp."):
            imap_host = host.replace("smtp.", "imap.")
            
        def _read():
            try:
                mail = imaplib.IMAP4_SSL(imap_host)
                mail.login(config.email_user, config.email_pass)
                mail.select("inbox")
                
                status, data = mail.fetch(index, "(RFC822)")
                if status != "OK":
                    mail.logout()
                    return f"Failed to fetch email with index {index}."
                    
                raw_msg = data[0][1]
                msg = email.message_from_bytes(raw_msg)
                
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disp = str(part.get('Content-Disposition'))
                        
                        if content_type == "text/plain" and "attachment" not in content_disp:
                            payload = part.get_payload(decode=True)
                            charset = part.get_content_charset() or 'utf-8'
                            body = payload.decode(charset, errors='ignore')
                            break
                    if not body:
                        for part in msg.walk():
                            if part.get_content_type() == "text/html":
                                payload = part.get_payload(decode=True)
                                charset = part.get_content_charset() or 'utf-8'
                                html = payload.decode(charset, errors='ignore')
                                from bs4 import BeautifulSoup
                                body = BeautifulSoup(html, 'html.parser').get_text()
                                break
                else:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='ignore')
                    
                subject = msg.get("Subject", "(No Subject)")
                decoded_subject, charset = decode_header(subject)[0]
                if isinstance(decoded_subject, bytes):
                    subject = decoded_subject.decode(charset or 'utf-8', errors='ignore')
                sender = msg.get("From", "(Unknown Sender)")
                decoded_sender, charset = decode_header(sender)[0]
                if isinstance(decoded_sender, bytes):
                    sender = decoded_sender.decode(charset or 'utf-8', errors='ignore')
                    
                mail.logout()
                
                res = f"Sender: {sender}\nSubject: {subject}\n\nContent:\n{body}"
                if len(res) > 5000:
                    res = res[:5000] + "\n...[truncated due to length]..."
                return res
            except Exception as e:
                return f"IMAP Error: {str(e)}"
                
        return await asyncio.get_event_loop().run_in_executor(None, _read)

email_manager = EmailManager()
