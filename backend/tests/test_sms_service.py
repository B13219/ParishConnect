from app.core.settings import settings
from app.services.sms import (
    delivery_report_status,
    normalize_phone_number,
    send_sms,
    sms_provider_status,
)


def test_tanzanian_phone_normalization() -> None:
    assert normalize_phone_number("+255 711 100 001") == "+255711100001"
    assert normalize_phone_number("0711-100-001") == "+255711100001"
    assert normalize_phone_number("255711100001") == "+255711100001"
    assert normalize_phone_number("711100001") == "+255711100001"


def test_simulation_mode_queues_without_external_provider(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sms_mode", "simulate")

    results = send_sms("Vinyrd test", ["0711 100 001"])

    assert len(results) == 1
    assert results[0].phone == "+255711100001"
    assert results[0].delivery_status == "queued"
    assert results[0].provider_reference.startswith("simulated-")


def test_provider_status_exposes_no_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sms_mode", "sandbox")
    monkeypatch.setattr(settings, "sms_username", "sandbox-user")
    monkeypatch.setattr(settings, "sms_api_key", "super-secret-key")

    provider = sms_provider_status()

    assert provider["provider"] == "africas_talking"
    assert provider["mode"] == "sandbox"
    assert provider["credentials_configured"] is True
    assert provider["external_sending"] is True
    assert provider["ready"] is True
    assert "api_key" not in provider


def test_delivery_report_status_mapping() -> None:
    assert delivery_report_status("Success") == "delivered"
    assert delivery_report_status("Delivered") == "delivered"
    assert delivery_report_status("Buffered") == "buffered"
    assert delivery_report_status("Failed") == "failed"

def test_live_mode_requires_separate_production_credentials(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sms_mode", "live")
    monkeypatch.setattr(settings, "sms_username", "sandbox")
    monkeypatch.setattr(settings, "sms_api_key", "sandbox-key")
    monkeypatch.setattr(settings, "sms_live_username", "")
    monkeypatch.setattr(settings, "sms_live_api_key", "")
    monkeypatch.setattr(settings, "sms_live_sender_id", "VINYRD")
    monkeypatch.setattr(settings, "sms_live_sender_id_approved", False)

    provider = sms_provider_status()

    assert provider["mode"] == "live"
    assert provider["credentials_configured"] is False
    assert provider["ready"] is False
    assert provider["production"]["live_credentials_configured"] is False
    assert provider["production"]["sender_id_configured"] is True
    assert provider["production"]["sender_id_approved"] is False

