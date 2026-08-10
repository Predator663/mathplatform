"""
WhatsApp message delivery, via Twilio's WhatsApp Business API.

Mirrors the email backend's dev/prod split (settings.EMAIL_HOST unset ->
console backend): with no TWILIO_ACCOUNT_SID configured, messages are
logged instead of sent, so local dev and tests never need real credentials
or touch a real phone number.

Usage:
    ok, error = send_whatsapp_message('+255700000000', 'Hello!')
"""
import logging
import re

from django.conf import settings

logger = logging.getLogger('mathapi.whatsapp')


class WhatsAppDeliveryError(Exception):
    pass


def _normalize_phone(phone: str) -> str | None:
    """Loose E.164-ish normalization — strips spaces/dashes/parens, keeps
    a leading '+'. Doesn't attempt to guess a missing country code, since
    guessing wrong silently sends nowhere. Returns None if what's left
    doesn't look like a phone number at all."""
    if not phone:
        return None
    cleaned = re.sub(r'[\s\-().]', '', phone.strip())
    if not re.match(r'^\+?\d{7,15}$', cleaned):
        return None
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    return cleaned


def is_configured() -> bool:
    return bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN)


def send_whatsapp_message(phone: str, body: str) -> tuple[bool, str]:
    """Sends one WhatsApp message. Returns (success, error_message) —
    never raises, matching the email sender's "log and move on" contract
    so a delivery failure never blocks the request that triggered it."""
    normalized = _normalize_phone(phone)
    if not normalized:
        return False, f'"{phone}" is not a valid phone number.'

    if not is_configured():
        logger.info('[WhatsApp console backend] To: %s\n%s', normalized, body)
        return True, ''

    try:
        import requests
    except ImportError:
        return False, 'The "requests" package is required for WhatsApp delivery.'

    url = f'https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json'
    try:
        resp = requests.post(
            url,
            data={
                'From': settings.TWILIO_WHATSAPP_FROM,
                'To': f'whatsapp:{normalized}',
                'Body': body,
            },
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            timeout=15,
        )
        if 200 <= resp.status_code < 300:
            return True, ''
        return False, f'Twilio returned {resp.status_code}: {resp.text[:300]}'
    except Exception as exc:  # noqa: BLE001 — any network/library failure is a delivery failure
        return False, str(exc)
