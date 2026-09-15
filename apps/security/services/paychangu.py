import os
import json
import requests
import hashlib
import hmac
import uuid
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import logging
from django.conf import settings


logger = logging.getLogger(__name__)

class PayChanguService:
    """
    PayChangu Mobile Money Service for Malawi
    Supports sandbox and production environments
    """
    
    def __init__(self, environment='sandbox'):
        self.environment = environment
        self.public_key = "pub-test-MqOeyf0sdYolfPkJXUodu5bO8zUW9pbG"
        self.secret_key = "sec-test-XN7uZgXNi8kmegTWIitFKYPPlsPLlaVB"

        if environment == 'sandbox':
            self.base_url = "https://sandbox.paychangu.com/api/v1"
        else:
            self.base_url = "https://paychangu.com/api/v1"

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.secret_key}"
        }

    def _callback_url(self):
        """Build the webhook URL PayChangu should call back on -
        driven by settings so it stays correct as ngrok/production
        domains change, instead of a hardcoded placeholder."""
        base = getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')
        return f"{base}/api/payments/webhook/"
    
    def initiate_payout(self, phone_number, amount, reference=None, customer_name=None):
        """
        Initiate a mobile money payout (send money to member)
        
        Args:
            phone_number (str): Recipient's phone number (with country code)
            amount (Decimal): Amount to send
            reference (str): Unique reference for this transaction
            customer_name (str): Recipient's full name
        
        Returns:
            dict: Response from PayChangu
        """
        if not reference:
            reference = f"ECORET-{uuid.uuid4().hex[:8].upper()}"
        
        # Prepare payload
        payload = {
            "mobile": phone_number,
            "amount": float(amount),
            "reference": reference,
            "currency": "MWK",
            "callback_url": self._callback_url(),
            "description": f"ECORET payout to {customer_name or 'Member'}"
        }
        
        if customer_name:
            payload["customer_name"] = customer_name
        
        try:
            url = f"{self.base_url}/payouts"
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"PayChangu payout initiated: {reference} - {result}")
            return {
                'success': True,
                'reference': reference,
                'transaction_id': result.get('data', {}).get('transaction_id'),
                'response': result
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PayChangu payout error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'reference': reference
            }
    
    def initiate_payment(self, phone_number, amount, reference=None, customer_name=None):
        """
        Initiate a mobile money collection (collect payment from member)
        
        Args:
            phone_number (str): Payer's phone number (with country code)
            amount (Decimal): Amount to collect
            reference (str): Unique reference for this transaction
            customer_name (str): Payer's full name
        
        Returns:
            dict: Response from PayChangu
        """
        if not reference:
            reference = f"ECORET-{uuid.uuid4().hex[:8].upper()}"
        
        # Prepare payload
        payload = {
            "mobile": phone_number,
            "amount": float(amount),
            "reference": reference,
            "currency": "MWK",
            "callback_url": self._callback_url(),
            "description": f"ECORET collection from {customer_name or 'Member'}"
        }
        
        if customer_name:
            payload["customer_name"] = customer_name
        
        try:
            url = f"{self.base_url}/payments"
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"PayChangu payment initiated: {reference} - {result}")
            return {
                'success': True,
                'reference': reference,
                'transaction_id': result.get('data', {}).get('transaction_id'),
                'response': result
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PayChangu payment error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'reference': reference
            }

    def get_banks(self, currency='MWK'):
        """
        Fetch PayChangu's list of supported banks/mobile money providers
        and their UUIDs, needed for bank_uuid in payout requests.
        """
        try:
            url = "https://api.paychangu.com/direct-charge/payouts/supported-banks"
            response = requests.get(url, params={'currency': currency}, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            return {
                'success': True,
                'banks': result.get('data', []),
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"PayChangu get_banks error: {str(e)}")
            return {'success': False, 'error': str(e), 'banks': []}

    def initiate_bank_payout(self, *, bank_uuid, account_number, account_name, amount, reference):
        """
        Initiate a real bank payout (ECORET -> recipient's bank account)
        via PayChangu's direct-charge payout endpoint. Status starts
        'pending' and is only confirmed via webhook (event_type: 'api.payout').
        """
        payload = {
            "payout_method": "bank_transfer",
            "bank_uuid": bank_uuid,
            "amount": str(amount),
            "charge_id": reference,
            "bank_account_name": account_name,
            "bank_account_number": account_number,
        }

        try:
            url = "https://api.paychangu.com/direct-charge/payouts/initialize"
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            result = response.json()

            transaction = result.get('data', {}).get('transaction', {})
            logger.info(f"PayChangu bank payout initiated: {reference} - {result}")

            return {
                'success': result.get('status') == 'success',
                'reference': reference,
                'charge_id': transaction.get('charge_id'),
                'ref_id': transaction.get('ref_id'),
                'status': transaction.get('status'),
                'response': result,
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"PayChangu bank payout error: {str(e)}")
            return {'success': False, 'error': str(e), 'reference': reference}
        
    
    def verify_transaction(self, reference):
        """
        Verify the status of a transaction
        
        Args:
            reference (str): The reference of the transaction to verify
        
        Returns:
            dict: Transaction status
        """
        try:
            url = f"{self.base_url}/transactions/{reference}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            
            return {
                'success': True,
                'status': result.get('data', {}).get('status'),
                'transaction': result.get('data', {})
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PayChangu verification error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_balance(self):
        """
        Check account balance
        
        Returns:
            dict: Account balance information
        """
        try:
            url = f"{self.base_url}/balance"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            
            return {
                'success': True,
                'balance': result.get('data', {}).get('balance'),
                'currency': result.get('data', {}).get('currency')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PayChangu balance check error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

# Singleton instance
paychangu = PayChanguService(environment='sandbox')