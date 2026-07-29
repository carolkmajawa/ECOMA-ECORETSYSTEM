# apps/accounts/email_backend.py
import smtplib
import ssl
import socket
from django.core.mail.backends.smtp import EmailBackend
import logging

logger = logging.getLogger(__name__)

class CustomEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False
        
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            self.connection = smtplib.SMTP(
                self.host, 
                self.port,
                timeout=self.timeout or 30
            )
            
            self.connection.ehlo()
            
            if self.use_tls:
                self.connection.starttls(context=context)
                self.connection.ehlo()
            
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            
            logger.info(f"Email connection established to {self.host}:{self.port}")
            return True
            
        except socket.error as e:
            logger.error(f"Socket error: {str(e)}")
            if not self.fail_silently:
                raise
            return False
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"Authentication failed: {str(e)}")
            if not self.fail_silently:
                raise
            return False
            
        except Exception as e:
            logger.error(f"Failed to open email connection: {str(e)}")
            if not self.fail_silently:
                raise
            return False
    
    def close(self):
        try:
            if self.connection:
                self.connection.quit()
                self.connection = None
                logger.debug("Email connection closed")
        except Exception as e:
            logger.warning(f"Error closing email connection: {str(e)}")
            self.connection = None