from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.settings import settings


SUCCESS_STATUS_CODES = {100, 101, 102}
STATUS_CODE_MAP = {
    401: "risk_hold",
    402: "invalid_sender",
    403: "invalid_phone",
    404: "unsupported_number",
    405: "insufficient_balance",
    406: "blacklisted",
    407: "could_not_route",
    500: "provider_error",
    501: "gateway_error",
    502: "rejected",
}


class SmsProviderError(RuntimeError):
    pass


@dataclass
class SmsRecipientResult:
    phone: str
    delivery_status: str
    provider_reference: str | None = None
    status_code: int | None = None
    cost: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_phone_number(phone: str | None) -> str | None:
    if not phone:
        return None

    raw = str(phone).strip()
    if not raw:
        return None

    leading_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None

    if raw.startswith("00"):
        return f"+{digits[2:]}"
    if leading_plus:
        return f"+{digits}"
    if digits.startswith(settings.sms_default_country_code):
        return f"+{digits}"
    if digits.startswith("0"):
        return f"+{settings.sms_default_country_code}{digits[1:]}"
    if len(digits) == 9:
        return f"+{settings.sms_default_country_code}{digits}"
    return f"+{digits}"


def sms_provider_status() -> dict[str, object]:
    mode = settings.sms_mode.lower().strip()
    credentials_configured = bool(settings.sms_username and settings.sms_api_key)
    external_sending = mode in {"sandbox", "live"}
    ready = mode == "simulate" or (external_sending and credentials_configured)

    if mode == "disabled":
        summary = "SMS sending is disabled."
    elif mode == "simulate":
        summary = "Simulation mode: messages are recorded but no carrier SMS is sent."
    elif ready:
        summary = (
            f"Africa's Talking {mode} credentials are present. "
            "Send a sandbox test to verify authentication."
        )
    else:
        summary = f"Africa's Talking {mode} needs a username and API key."

    return {
        "provider": settings.sms_provider,
        "mode": mode,
        "sender_id": settings.sms_sender_id or None,
        "credentials_configured": credentials_configured,
        "external_sending": external_sending,
        "ready": ready,
        "delivery_report_configured": bool(
            settings.public_base_url and settings.sms_callback_token
        ),
        "summary": summary,
    }


def _endpoint_for_mode(mode: str) -> str:
    if mode == "sandbox":
        return "https://api.sandbox.africastalking.com/version1/messaging"
    if mode == "live":
        return "https://api.africastalking.com/version1/messaging"
    raise SmsProviderError(f"Unsupported SMS mode: {mode}")


def _immediate_status(status_code: int | None, status_text: str | None) -> str:
    if status_code in SUCCESS_STATUS_CODES:
        return "queued"
    if status_code in STATUS_CODE_MAP:
        return STATUS_CODE_MAP[status_code]

    normalized = (status_text or "").strip().lower().replace(" ", "_")
    if normalized in {"success", "sent", "processed", "queued"}:
        return "queued"
    return normalized[:40] or "provider_error"


def delivery_report_status(status_text: str | None) -> str:
    normalized = (status_text or "").strip().lower()
    mapping = {
        "success": "delivered",
        "delivered": "delivered",
        "sent": "sent",
        "submitted": "submitted",
        "buffered": "buffered",
        "rejected": "rejected",
        "failed": "failed",
        "expired": "expired",
    }
    return mapping.get(normalized, normalized.replace(" ", "_")[:40] or "unknown")


def send_sms(body: str, phones: list[str | None]) -> list[SmsRecipientResult]:
    normalized_numbers: list[str] = []
    seen: set[str] = set()
    for phone in phones:
        normalized = normalize_phone_number(phone)
        if normalized and normalized not in seen:
            normalized_numbers.append(normalized)
            seen.add(normalized)

    if not normalized_numbers:
        raise SmsProviderError("No recipients have valid phone numbers.")

    mode = settings.sms_mode.lower().strip()
    if mode == "disabled":
        raise SmsProviderError("SMS sending is disabled.")

    if mode == "simulate":
        return [
            SmsRecipientResult(
                phone=phone,
                delivery_status="queued",
                provider_reference=f"simulated-{uuid4().hex}",
                status_code=102,
            )
            for phone in normalized_numbers
        ]

    if mode not in {"sandbox", "live"}:
        raise SmsProviderError(
            "SMS mode must be one of simulate, sandbox, live, or disabled."
        )

    if not settings.sms_username or not settings.sms_api_key:
        raise SmsProviderError(
            "Africa's Talking credentials are not configured for this SMS mode."
        )

    payload: dict[str, str] = {
        "username": settings.sms_username,
        "to": ",".join(normalized_numbers),
        "message": body,
    }
    if settings.sms_sender_id:
        payload["from"] = settings.sms_sender_id

    request = Request(
        _endpoint_for_mode(mode),
        data=urlencode(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "apiKey": settings.sms_api_key,
        },
    )

    try:
        with urlopen(request, timeout=settings.sms_request_timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401 and mode == "sandbox":
            raise SmsProviderError(
                "Africa's Talking sandbox authentication was rejected. "
                "Confirm the username is sandbox and replace PARISHCONNECT_SMS_API_KEY "
                "with an API key generated from the orange Sandbox dashboard, then wait "
                "a few minutes before testing again."
            ) from exc
        raise SmsProviderError(
            f"Africa's Talking rejected the SMS request ({exc.code}): {detail[:240]}"
        ) from exc
    except URLError as exc:
        raise SmsProviderError(
            f"Africa's Talking could not be reached: {exc.reason}"
        ) from exc

    try:
        response_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmsProviderError("Africa's Talking returned an invalid JSON response.") from exc

    provider_recipients = (
        response_data.get("SMSMessageData", {}).get("Recipients", [])
        if isinstance(response_data, dict)
        else []
    )

    by_phone: dict[str, dict[str, object]] = {}
    for item in provider_recipients:
        if not isinstance(item, dict):
            continue
        normalized = normalize_phone_number(str(item.get("number") or ""))
        if normalized:
            by_phone[normalized] = item

    results: list[SmsRecipientResult] = []
    for phone in normalized_numbers:
        item = by_phone.get(phone)
        if item is None:
            results.append(
                SmsRecipientResult(
                    phone=phone,
                    delivery_status="provider_error",
                    error="Provider response did not include this recipient.",
                )
            )
            continue

        status_code_raw = item.get("statusCode")
        try:
            status_code = int(status_code_raw) if status_code_raw is not None else None
        except (TypeError, ValueError):
            status_code = None

        results.append(
            SmsRecipientResult(
                phone=phone,
                delivery_status=_immediate_status(status_code, str(item.get("status") or "")),
                provider_reference=str(item.get("messageId") or "") or None,
                status_code=status_code,
                cost=str(item.get("cost") or "") or None,
                error=None if status_code in SUCCESS_STATUS_CODES else str(item.get("status") or ""),
            )
        )

    return results
