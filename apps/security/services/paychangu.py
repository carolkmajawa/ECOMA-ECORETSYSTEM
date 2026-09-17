



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

logger = logging.getLogger(__name__)

class PayChanguService:
    """
    PayChangu Mobile Money Service for Malawi
    Supports sandbox and production environments
    """

    def __init__(self):
        self.environment = settings.PAYCHANGU_ENVIRONMENT
        self.public_key = settings.PAYCHANGU_PUBLIC_KEY
        self.secret_key = settings.PAYCHANGU_SECRET_KEY
        self.direct_charge_base_url = settings.PAYCHANGU_BASE_URL.rstrip('/')

        if self.environment == 'sandbox':
            self.base_url = "https://sandbox.paychangu.com/api/v1"
        else:
            self.base_url = "https://paychangu.com/api/v1"

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.secret_key}"
        }

    def _callback_url(self):
        base = getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')
        return f"{base}/api/payments/webhook/"

    def get_banks(self, currency='MWK'):
        """
        Fetch PayChangu's list of supported banks/mobile money providers
        and their UUIDs, needed for bank_uuid in payout requests.
        """
        try:
            url = f"{self.direct_charge_base_url}/direct-charge/payouts/supported-banks"
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
            url = f"{self.direct_charge_base_url}/direct-charge/payouts/initialize"
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
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json()
                except ValueError:
                    error_detail = e.response.text
            logger.error(f"PayChangu bank payout error: {error_detail} | payload sent: {payload}")
            return {'success': False, 'error': error_detail, 'reference': reference}


paychangu = PayChanguService()