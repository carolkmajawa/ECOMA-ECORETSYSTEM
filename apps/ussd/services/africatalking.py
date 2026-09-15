# apps/ussd/services/africatalking.py
import logging
import httpx
from django.conf import settings
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class AfricaTalkingService:
    """
    Service for sending SMS via Africa's Talking API
    """
    
    def __init__(self):
        # Load configuration from settings
        self.api_key = getattr(settings, 'AFRICA_TALKING_API_KEY', '')
        self.username = getattr(settings, 'AFRICA_TALKING_USERNAME', '')
        self.sandbox = getattr(settings, 'AFRICA_TALKING_SANDBOX', True)
        self.sender_id = getattr(settings, 'AFRICA_TALKING_SENDER_ID', 'ECORET')
        
        # Set the base URL based on sandbox mode
        if self.sandbox:
            self.base_url = 'https://api.sandbox.africastalking.com'
        else:
            self.base_url = 'https://api.africastalking.com'
        
        self.headers = {
            'apiKey': self.api_key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }
        
        # Log configuration status
        if not self.api_key:
            logger.warning("AFRICA_TALKING_API_KEY not configured. SMS will be logged only.")
        if not self.username:
            logger.warning("AFRICA_TALKING_USERNAME not configured. SMS will be logged only.")
    
    def _format_phone_number(self, phone_number: str) -> str:
        """
        Format phone number to international format
        """
        if not phone_number:
            return phone_number
        
        # Remove any whitespace
        phone_number = phone_number.strip()
        
        # If number starts with 0, replace with +265 (Malawi country code)
        if phone_number.startswith('0'):
            phone_number = phone_number[1:]
            phone_number = '+265' + phone_number
        
        # If number doesn't have +, add it
        elif not phone_number.startswith('+'):
            # Check if it's a valid Malawi number without +265
            if len(phone_number) == 9 and phone_number.startswith('99'):
                phone_number = '+265' + phone_number
            else:
                # Assume it's already in international format without +
                phone_number = '+' + phone_number
        
        # Remove any spaces, dashes, or parentheses
        phone_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        
        return phone_number
    
    def send_sms(self, phone_number: str, message: str, sender_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Send SMS to a single phone number
        """
        if not phone_number:
            logger.error("Phone number is required")
            return {"status": "error", "message": "Phone number is required"}
        
        if not message:
            logger.error("Message is required")
            return {"status": "error", "message": "Message is required"}
        
        # If no API key is configured, log the SMS
        if not self.api_key or not self.username:
            logger.info(f"SMS would be sent to {phone_number}: {message[:100]}...")
            return {
                "status": "success", 
                "message": "SMS logged (no API key configured)",
                "mock": True
            }
        
        try:
            # Format the phone number
            formatted_number = self._format_phone_number(phone_number)
            
            # Prepare request data
            data = {
                'username': self.username,
                'to': formatted_number,
                'message': message,
                'from': sender_id or 'ECORET'
            }
            
            # Add sender ID if provided
            if sender_id:
                data['from'] = sender_id[:11]  # Max 11 characters
            elif self.sender_id:
                data['from'] = self.sender_id[:11]
            
            logger.info(f"Sending SMS to {formatted_number}")
            logger.debug(f"Request data: {data}")
            
            # Use httpx with SSL verification disabled
            with httpx.Client(verify=False) as client:
                response = client.post(
                    f"{self.base_url}/version1/messaging",
                    headers=self.headers,
                    data=data,
                    timeout=30.0
                )
            
            # Log response for debugging
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response body: {response.text}")
            
            # Africa's Talking returns 201 for successful SMS
            if response.status_code in [200, 201]:
                try:
                    response_data = response.json()
                except:
                    response_data = {"message": "SMS sent successfully"}
                
                logger.info(f"SMS sent successfully to {formatted_number}")
                return {
                    "status": "success", 
                    "data": response_data,
                    "phone_number": formatted_number,
                    "status_code": response.status_code
                }
            else:
                logger.error(f"Failed to send SMS. Status: {response.status_code}, Response: {response.text}")
                return {
                    "status": "error", 
                    "message": f"HTTP {response.status_code}: {response.text}",
                    "phone_number": formatted_number,
                    "status_code": response.status_code
                }
                
        except httpx.TimeoutException:
            logger.error(f"Timeout sending SMS to {phone_number}")
            return {"status": "error", "message": "Request timeout"}
        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending SMS: {str(e)}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error sending SMS: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def send_bulk_sms(self, phone_numbers: List[str], message: str, sender_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Send SMS to multiple phone numbers
        """
        if not phone_numbers:
            logger.error("Phone numbers list is required")
            return {"status": "error", "message": "Phone numbers list is required"}
        
        if not message:
            logger.error("Message is required")
            return {"status": "error", "message": "Message is required"}
        
        # If no API key is configured, log the SMS
        if not self.api_key or not self.username:
            logger.info(f"Bulk SMS would be sent to {len(phone_numbers)} numbers")
            return {
                "status": "success", 
                "message": "SMS logged (no API key configured)",
                "mock": True,
                "count": len(phone_numbers)
            }
        
        try:
            # Format all phone numbers
            formatted_numbers = [self._format_phone_number(num) for num in phone_numbers if num]
            formatted_numbers = [num for num in formatted_numbers if num]
            
            if not formatted_numbers:
                logger.error("No valid phone numbers provided")
                return {"status": "error", "message": "No valid phone numbers provided"}
            
            # Prepare request data
            data = {
                'username': self.username,
                'to': ','.join(formatted_numbers),
                'message': message,
            }
            
            if sender_id:
                data['from'] = sender_id[:11]
            elif self.sender_id:
                data['from'] = self.sender_id[:11]
            
            logger.info(f"Sending bulk SMS to {len(formatted_numbers)} numbers")
            
            # Use httpx with SSL verification disabled
            with httpx.Client(verify=False) as client:
                response = client.post(
                    f"{self.base_url}/version1/messaging",
                    headers=self.headers,
                    data=data,
                    timeout=60.0
                )
            
            if response.status_code in [200, 201]:
                logger.info(f"Bulk SMS sent successfully to {len(formatted_numbers)} numbers")
                return {
                    "status": "success", 
                    "count": len(formatted_numbers),
                    "status_code": response.status_code
                }
            else:
                logger.error(f"Failed to send bulk SMS: {response.status_code}")
                return {
                    "status": "error", 
                    "message": f"HTTP {response.status_code}"
                }
                
        except httpx.TimeoutException:
            logger.error("Timeout sending bulk SMS")
            return {"status": "error", "message": "Request timeout"}
        except Exception as e:
            logger.error(f"Error sending bulk SMS: {str(e)}")
            return {"status": "error", "message": str(e)}