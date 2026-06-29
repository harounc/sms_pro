import base64

import requests
from django.conf import settings
from django.core.cache import cache

_TOKEN_CACHE_KEY = "sms_gateway_access_token"
_TOKEN_CACHE_TTL = 23 * 3600  # 23 h (le token expire à 24 h)

# Préfixes CI par opérateur (format local 10 chiffres)
_ORANGE_PREFIXES = ("07", "08", "09")
_MTN_PREFIXES    = ("05", "06")
_MOOV_PREFIXES   = ("01", "02")

MOTEURS_VALIDES = ("ORANGE", "MTN", "MOOV")


def _basic_key() -> str:
    if settings.SMS_API_KEY_BASE64:
        return settings.SMS_API_KEY_BASE64

    if settings.SMS_API_CLIENT_ID and settings.SMS_API_CLIENT_SECRET:
        raw = f"{settings.SMS_API_CLIENT_ID}:{settings.SMS_API_CLIENT_SECRET}"
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")

    return ""


def validate_sms_configuration(sender: str = None) -> str | None:
    if not settings.SMS_API_BASE_URL:
        return "SMS_API_BASE_URL n'est pas configuré."

    if not sender and not settings.SMS_API_FROM:
        return "SMS_API_FROM n'est pas configuré."

    if not _basic_key():
        return "SMS_API_KEY_BASE64 n'est pas configuré."

    return None


def _to_local(phone: str) -> str:
    """Convertit +225XXXXXXXXXX → 0XXXXXXXXX (format local CI)."""
    if phone.startswith("+225"):
        return phone[4:]
    return phone


def _detect_moteur(local_phone: str) -> str:
    """Détermine le moteur API à partir du préfixe CI."""
    prefix = local_phone[:2]
    if prefix in _MTN_PREFIXES:
        return "MTN"
    if prefix in _MOOV_PREFIXES:
        return "MOOV"
    return "ORANGE"   # 07, 08, 09 et inconnus → Orange


def _get_token() -> str:
    """Retourne le token OAuth2 en cache, ou en récupère un nouveau."""
    basic_key = _basic_key()
    if not basic_key:
        raise ValueError("SMS_API_KEY_BASE64 n'est pas configuré.")

    token = cache.get(_TOKEN_CACHE_KEY)
    if token:
        return token

    resp = requests.post(
        f"{settings.SMS_API_BASE_URL}/oauth2/token",
        headers={
            "Authorization": f"Basic {basic_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials", "scope": "api_access"},
        timeout=15,
    )
    resp.raise_for_status()

    token = resp.json()["access_token"]
    cache.set(_TOKEN_CACHE_KEY, token, _TOKEN_CACHE_TTL)
    return token


def send_sms(phone: str, message: str, sender: str = None, moteur: str = None) -> dict:
    """
    Envoie un SMS réel via ivoiresoftservices.net.

    moteur : "ORANGE", "MTN" ou "MOOV". Si None, il est détecté depuis le numéro.
    Retourne {"success": True} ou {"success": False, "error": "..."}
    """
    config_error = validate_sms_configuration(sender=sender)
    if config_error:
        return {"success": False, "error": config_error}

    local_phone = _to_local(phone)
    from_number = settings.SMS_API_FROM or sender

    if moteur:
        moteur = moteur.upper()
        if moteur not in MOTEURS_VALIDES:
            return {"success": False, "error": f"Moteur invalide : {moteur}"}
    else:
        moteur = _detect_moteur(local_phone)

    for attempt in range(2):
        try:
            token = _get_token()

            payload = {
                "from": from_number,
                "to":   local_phone,
                "msg":  message,
            }
            payload["moteur"] = moteur

            resp = requests.post(
                f"{settings.SMS_API_BASE_URL}/api/external/sms/send",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15,
            )

            # Token expiré → vider le cache et réessayer une fois
            if resp.status_code == 401 and attempt == 0:
                cache.delete(_TOKEN_CACHE_KEY)
                continue

            if not resp.ok:
                try:
                    error_message = resp.json().get("message") or resp.text[:300]
                except ValueError:
                    error_message = resp.text[:300]
                return {"success": False, "error": f"HTTP {resp.status_code} : {error_message}"}

            data = resp.json()

            if data.get("status") == "SUCCESS":
                return {"success": True}

            return {"success": False, "error": data.get("message", "Erreur API gateway")}

        except (requests.RequestException, ValueError) as exc:
            return {"success": False, "error": str(exc)}

    return {"success": False, "error": "Échec après re-authentification"}
