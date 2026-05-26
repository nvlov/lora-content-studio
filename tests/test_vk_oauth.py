"""Юнит-тесты для VK ID OAuth helper'а."""
from __future__ import annotations

import base64
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.publishers import vk_oauth
from core.publishers.vk_oauth import (
    VKOAuthError,
    build_authorize_url,
    exchange_code_for_tokens,
    generate_pkce_pair,
    generate_state,
    parse_callback_url,
    refresh_access_token,
)
from scripts.get_vk_token import update_env_file


# ----- PKCE -----

def test_pkce_pair_format():
    verifier, challenge = generate_pkce_pair()
    # 43-128 символов из RFC 7636 unreserved set
    assert 43 <= len(verifier) <= 128
    assert all(c.isalnum() or c in "-._~" for c in verifier)
    # challenge = base64url-no-pad(sha256(verifier))
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    assert challenge == expected


def test_pkce_pair_is_random():
    a, _ = generate_pkce_pair()
    b, _ = generate_pkce_pair()
    assert a != b


def test_state_format():
    s = generate_state()
    assert len(s) == 32
    int(s, 16)  # должно парситься как hex


# ----- authorize URL -----

def test_authorize_url_contains_required_params():
    url = build_authorize_url(
        app_id="123",
        redirect_uri="https://oauth.vk.com/blank.html",
        scope="wall photos",
        code_challenge="abc",
        state="state123",
    )
    assert url.startswith("https://id.vk.com/authorize?")
    assert "client_id=123" in url
    assert "response_type=code" in url
    # пробел в scope должен быть закодирован
    assert "scope=wall+photos" in url or "scope=wall%20photos" in url
    assert "code_challenge=abc" in url
    assert "code_challenge_method=s256" in url  # нижний регистр
    assert "state=state123" in url
    # device_id НЕ должен быть в URL
    assert "device_id" not in url


# ----- callback parsing -----

def test_parse_callback_happy_path():
    url = "https://oauth.vk.com/blank.html?code=CODE123&state=STATE&device_id=DEV"
    result = parse_callback_url(url, expected_state="STATE")
    assert result == {"code": "CODE123", "state": "STATE", "device_id": "DEV"}


def test_parse_callback_state_mismatch():
    url = "https://oauth.vk.com/blank.html?code=C&state=WRONG&device_id=D"
    with pytest.raises(VKOAuthError, match="CSRF"):
        parse_callback_url(url, expected_state="EXPECTED")


def test_parse_callback_vk_error():
    url = "https://oauth.vk.com/blank.html?error=access_denied&error_description=user+refused"
    with pytest.raises(VKOAuthError, match="access_denied"):
        parse_callback_url(url, expected_state="X")


def test_parse_callback_missing_code():
    url = "https://oauth.vk.com/blank.html?state=S&device_id=D"
    with pytest.raises(VKOAuthError, match="code"):
        parse_callback_url(url, expected_state="S")


def test_parse_callback_missing_device_id():
    url = "https://oauth.vk.com/blank.html?code=C&state=S"
    with pytest.raises(VKOAuthError, match="device_id"):
        parse_callback_url(url, expected_state="S")


def test_parse_callback_empty_url():
    with pytest.raises(VKOAuthError):
        parse_callback_url("", expected_state="X")


# ----- exchange / refresh (моки httpx) -----

def _mock_response(status: int, json_data: dict):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_data
    m.text = str(json_data)
    return m


def test_exchange_code_for_tokens_success():
    fake = _mock_response(200, {
        "access_token": "AT",
        "refresh_token": "RT",
        "expires_in": 3600,
        "user_id": 42,
        "scope": "wall photos video groups offline",
    })
    with patch("core.vk_oauth.httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = fake

        result = exchange_code_for_tokens(
            code="C", code_verifier="V", app_id="APP",
            redirect_uri="https://oauth.vk.com/blank.html",
            device_id="DEV", state="S",
        )

    assert result["access_token"] == "AT"
    assert result["refresh_token"] == "RT"
    assert result["user_id"] == 42
    assert result["scope"] == "wall photos video groups offline"
    assert isinstance(result["expires_at"], datetime)
    # expires_at ≈ now + 3600s
    delta = result["expires_at"] - datetime.now(timezone.utc)
    assert timedelta(minutes=58) < delta < timedelta(minutes=62)

    # Проверяем что в форме все нужные поля и НЕТ client_secret
    call_kwargs = instance.post.call_args.kwargs
    form = call_kwargs["data"]
    assert form["grant_type"] == "authorization_code"
    assert form["code"] == "C"
    assert form["code_verifier"] == "V"
    assert form["client_id"] == "APP"
    assert form["device_id"] == "DEV"
    assert form["redirect_uri"] == "https://oauth.vk.com/blank.html"
    assert form["state"] == "S"
    assert "client_secret" not in form


def test_refresh_access_token_success():
    fake = _mock_response(200, {
        "access_token": "AT2",
        "refresh_token": "RT2",
        "expires_in": 86400,
    })
    with patch("core.vk_oauth.httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = fake

        result = refresh_access_token(
            refresh_token="RT_OLD", app_id="APP", device_id="DEV", state="S",
        )

    assert result["access_token"] == "AT2"
    assert result["refresh_token"] == "RT2"
    form = instance.post.call_args.kwargs["data"]
    assert form["grant_type"] == "refresh_token"
    assert form["refresh_token"] == "RT_OLD"
    assert form["client_id"] == "APP"
    assert form["device_id"] == "DEV"
    assert "client_secret" not in form


def test_exchange_raises_on_vk_error():
    fake = _mock_response(400, {"error": "invalid_grant", "error_description": "bad code"})
    with patch("core.vk_oauth.httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = fake

        with pytest.raises(VKOAuthError, match="invalid_grant"):
            exchange_code_for_tokens(
                code="C", code_verifier="V", app_id="APP",
                redirect_uri="https://oauth.vk.com/blank.html",
                device_id="DEV", state="S",
            )


# ----- update_env_file -----

def test_update_env_file_replaces_existing(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("FOO=bar\nKEY=old_value\n# comment\nBAZ=qux\n", encoding="utf-8")
    update_env_file(env, {"KEY": "new_value"})
    text = env.read_text(encoding="utf-8")
    assert "KEY=new_value" in text
    assert "KEY=old_value" not in text
    assert "FOO=bar" in text
    assert "# comment" in text
    assert "BAZ=qux" in text


def test_update_env_file_adds_missing(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("FOO=bar\n", encoding="utf-8")
    update_env_file(env, {"NEW_KEY": "value123"})
    text = env.read_text(encoding="utf-8")
    assert "FOO=bar" in text
    assert "NEW_KEY=value123" in text


def test_update_env_file_creates_missing_file(tmp_path: Path):
    env = tmp_path / ".env"
    update_env_file(env, {"KEY": "v"})
    assert env.exists()
    assert "KEY=v" in env.read_text(encoding="utf-8")


def test_update_env_file_preserves_comments_and_order(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("# section A\nA=1\n\n# section B\nB=2\n", encoding="utf-8")
    update_env_file(env, {"A": "11", "C": "3"})
    lines = env.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# section A"
    assert lines[1] == "A=11"
    assert "# section B" in lines
    assert "B=2" in lines
    assert "C=3" in lines  # добавлено в конец


# ----- интеграционный refresh-flow с моком (через VKClient) -----

def test_vkclient_ensure_fresh_token_refreshes_when_expired(tmp_path, monkeypatch):
    """Имитируем VK OAuth-токен с истёкшим expires_at и проверяем, что _ensure_fresh_token
    вызывает refresh_access_token и обновляет состояние клиента + .env.
    """
    # Подменяем .env на временный файл
    env_path = tmp_path / ".env"
    env_path.write_text(
        "VK_USER_ACCESS_TOKEN=OLD\n"
        "VK_USER_REFRESH_TOKEN=RT_OLD\n"
        "VK_USER_TOKEN_EXPIRES_AT=2020-01-01T00:00:00+00:00\n",
        encoding="utf-8",
    )

    import config
    monkeypatch.setattr(config, "VK_USER_ACCESS_TOKEN", "OLD")
    monkeypatch.setattr(config, "VK_USER_REFRESH_TOKEN", "RT_OLD")
    monkeypatch.setattr(config, "VK_USER_TOKEN_EXPIRES_AT", "2020-01-01T00:00:00+00:00")
    monkeypatch.setattr(config, "VK_OAUTH_APP_ID", "APP")
    monkeypatch.setattr(config, "VK_OAUTH_DEVICE_ID", "DEV")
    monkeypatch.setattr(config, "VK_GROUP_ID", "237689862")
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)

    from core.publishers.vk import VKClient

    new_expires = datetime.now(timezone.utc) + timedelta(hours=24)
    fake_tokens = {
        "access_token": "NEW_AT",
        "refresh_token": "NEW_RT",
        "expires_at": new_expires,
        "expires_in": 86400,
    }
    with patch("core.vk_oauth.refresh_access_token", return_value=fake_tokens) as mock_refresh:
        client = VKClient()
        assert client.token_source == "oauth_user"
        assert client.token == "OLD"
        client._ensure_fresh_token()

    assert mock_refresh.called
    assert client.token == "NEW_AT"
    assert client._refresh_token == "NEW_RT"
    assert client.token_expires_at == new_expires

    # .env должен быть обновлён
    text = env_path.read_text(encoding="utf-8")
    assert "VK_USER_ACCESS_TOKEN=NEW_AT" in text
    assert "VK_USER_REFRESH_TOKEN=NEW_RT" in text


def test_vkclient_ensure_fresh_token_skips_when_fresh(monkeypatch):
    """Если до истечения > 5 минут — refresh не вызывается."""
    import config
    monkeypatch.setattr(config, "VK_USER_ACCESS_TOKEN", "AT")
    monkeypatch.setattr(config, "VK_USER_REFRESH_TOKEN", "RT")
    fresh_until = (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat()
    monkeypatch.setattr(config, "VK_USER_TOKEN_EXPIRES_AT", fresh_until)
    monkeypatch.setattr(config, "VK_OAUTH_APP_ID", "APP")
    monkeypatch.setattr(config, "VK_OAUTH_DEVICE_ID", "DEV")
    monkeypatch.setattr(config, "VK_GROUP_ID", "237689862")

    from core.publishers.vk import VKClient
    with patch("core.vk_oauth.refresh_access_token") as mock_refresh:
        client = VKClient()
        client._ensure_fresh_token()
    mock_refresh.assert_not_called()


def test_vkclient_legacy_token_no_refresh(monkeypatch):
    """Legacy-токен не должен пытаться рефрешиться."""
    import config
    monkeypatch.setattr(config, "VK_USER_ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "VK_USER_REFRESH_TOKEN", "")
    monkeypatch.setattr(config, "VK_COMMUNITY_TOKEN", "LEGACY")
    monkeypatch.setattr(config, "VK_GROUP_ID", "237689862")

    from core.publishers.vk import VKClient
    client = VKClient()
    assert client.token_source == "legacy_community"
    with patch("core.vk_oauth.refresh_access_token") as mock_refresh:
        client._ensure_fresh_token()
    mock_refresh.assert_not_called()
