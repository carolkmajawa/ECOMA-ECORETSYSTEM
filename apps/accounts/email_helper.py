# apps/accounts/email_helper.py
import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings

logger = logging.getLogger(__name__)

class EmailHelper:
    @staticmethod
    def send_email(subject, html_content, text_content, recipient_email):
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = settings.EMAIL_HOST_USER
            msg['To'] = recipient_email
            msg['Reply-To'] = 'support@ecoret.com'
            
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            server = smtplib.SMTP(
                settings.EMAIL_HOST, 
                settings.EMAIL_PORT,
                timeout=30
            )
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(
                settings.EMAIL_HOST_USER, 
                settings.EMAIL_HOST_PASSWORD
            )
            server.sendmail(
                settings.EMAIL_HOST_USER, 
                [recipient_email], 
                msg.as_string()
            )
            server.quit()
            
            logger.info(f"Email sent successfully to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            raise