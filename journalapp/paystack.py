"""
Thin Paystack client.

Only the two calls this app needs — initialize a transaction and verify one —
plus webhook-signature verification. All money is handled in the minor unit
(kobo) as Paystack requires. Secret key comes from settings; when it's blank,
``is_configured()`` is False and callers should refuse gracefully rather than
hit the API with no credentials.
"""
import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger('journalapp')

API_BASE = 'https://api.paystack.co'
_TIMEOUT = 15


def is_configured():
    return bool(settings.PAYSTACK_SECRET_KEY)


def _headers():
    return {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }


def initialize_transaction(email, amount_kobo, reference, callback_url=None, metadata=None):
    """Start a transaction. Returns the parsed JSON ``data`` (with
    ``authorization_url``) on success, or None on failure."""
    payload = {
        'email': email,
        'amount': amount_kobo,
        'reference': reference,
    }
    if callback_url:
        payload['callback_url'] = callback_url
    if metadata:
        payload['metadata'] = metadata

    try:
        resp = requests.post(
            f'{API_BASE}/transaction/initialize',
            json=payload, headers=_headers(), timeout=_TIMEOUT,
        )
        data = resp.json()
        if resp.ok and data.get('status'):
            return data['data']
        logger.error('Paystack initialize failed: %s', data)
    except (requests.RequestException, ValueError):
        logger.error('Paystack initialize error', exc_info=True)
    return None


def verify_transaction(reference):
    """Verify a transaction by reference. Returns the parsed ``data`` dict
    (whose ``status`` is 'success' when paid) or None."""
    try:
        resp = requests.get(
            f'{API_BASE}/transaction/verify/{reference}',
            headers=_headers(), timeout=_TIMEOUT,
        )
        data = resp.json()
        if resp.ok and data.get('status'):
            return data['data']
        logger.error('Paystack verify failed: %s', data)
    except (requests.RequestException, ValueError):
        logger.error('Paystack verify error', exc_info=True)
    return None


def verify_webhook_signature(raw_body, signature):
    """True if ``signature`` (the x-paystack-signature header) matches an
    HMAC-SHA512 of the raw request body keyed with the secret key."""
    if not (signature and settings.PAYSTACK_SECRET_KEY):
        return False
    expected = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
