import subprocess
from types import SimpleNamespace

import pytest
import requests

from src.providers.provider_transport import call_sector_provider


URL = "https://push2.eastmoney.com/api/qt/clist/get"


@pytest.fixture(autouse=True)
def supported_curl(monkeypatch):
    monkeypatch.setattr("src.providers.provider_transport._require_supported_curl", lambda: None, raising=False)


@pytest.mark.parametrize("version,accepted", [(b'curl 8.4.0 platform', True),
    (b'curl 8.7.1 platform', True), (b'curl 8.3.0 platform', False), (b'unknown', False)])
def test_curl_version_gate(monkeypatch, version, accepted):
    import importlib
    import src.providers.provider_transport as transport
    transport = importlib.reload(transport)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=version))
    if accepted:
        transport._require_supported_curl()
    else:
        with pytest.raises(requests.RequestException):
            transport._require_supported_curl()


def fake_provider(**kwargs):
    return requests.get(URL, params={"fs": "m:90 t:2"}).json()


def test_default_uses_original_callable(monkeypatch):
    monkeypatch.delenv("FUND_FLOW_PROVIDER_TRANSPORT", raising=False)
    assert call_sector_provider(lambda **kw: kw, indicator="today") == {"indicator": "today"}


def test_curl_is_scoped_and_bounded(monkeypatch):
    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "curl_direct")
    original_get = requests.get
    seen = []
    def run(command, **kwargs):
        seen.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=b'{"data": {}}\n200', stderr=b'')
    monkeypatch.setattr(subprocess, "run", run)
    assert call_sector_provider(fake_provider) == {"data": {}}
    assert requests.get is original_get
    command, options = seen[0]
    assert command[1] == "--disable"
    assert command[command.index("--noproxy") + 1] == "*"
    assert "--location" not in command
    assert "--insecure" not in command
    assert options["timeout"] == 20
    assert "fs=m%3A90+t%3A2" in command[-1]


@pytest.mark.parametrize("code,body", [(52, b''), (0, b'{}\n302'), (0, b'{}\n503')])
def test_transport_failure_is_not_accepted(monkeypatch, code, body):
    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "curl_direct")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=code, stdout=body, stderr=b'secret proxy'))
    with pytest.raises(requests.RequestException) as error:
        call_sector_provider(fake_provider)
    assert "secret" not in str(error.value)


def test_unknown_transport_fails_closed(monkeypatch):
    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "typo")
    with pytest.raises(ValueError):
        call_sector_provider(fake_provider)


def test_other_url_is_rejected(monkeypatch):
    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "curl_direct")
    def other(**kw):
        return requests.get("https://example.com").json()
    with pytest.raises(ValueError):
        call_sector_provider(other)


def test_request_budget_and_global_binding_preserved(monkeypatch):
    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "curl_direct")
    calls = []
    def run(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(returncode=0, stdout=b'{}\n200')
    monkeypatch.setattr(subprocess, "run", run)
    def many():
        for _ in range(11):
            requests.get(URL)
    with pytest.raises(ValueError):
        call_sector_provider(many)
    assert len(calls) == 10
    assert many.__globals__["requests"] is requests


@pytest.mark.parametrize("error,expected", [(OSError(), requests.ConnectionError),
    (subprocess.TimeoutExpired('curl', 20), requests.Timeout)])
def test_local_transport_errors_are_sanitized(monkeypatch, error, expected):
    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "curl_direct")
    def run(*a, **kw):
        raise error
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(expected):
        call_sector_provider(fake_provider)


def test_unexpected_upstream_binding_fails_closed(monkeypatch):
    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "curl_direct")
    with pytest.raises(ValueError):
        call_sector_provider(SimpleNamespace())


@pytest.mark.parametrize("body", [b'not-json\n200', b'{}\n301'])
def test_invalid_payload_or_redirect_rejected(monkeypatch, body):
    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "curl_direct")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=body))
    with pytest.raises((ValueError, requests.HTTPError)):
        call_sector_provider(fake_provider)


def test_oversized_response_rejected(monkeypatch):
    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "curl_direct")
    body = b' ' * (4 * 1024 * 1024 + 1) + b'\n200'
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=body))
    with pytest.raises(requests.HTTPError):
        call_sector_provider(fake_provider)


def test_headers_cannot_inject_curl_options(monkeypatch):
    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "curl_direct")
    def bad_headers():
        return requests.get(URL, headers={"User-Agent": "agent\r\nCookie: private"})
    with pytest.raises(ValueError):
        call_sector_provider(bad_headers)


def test_current_akshare_http_binding_is_scoped(monkeypatch):
    from types import FunctionType, ModuleType

    monkeypatch.setenv("FUND_FLOW_PROVIDER_TRANSPORT", "curl_direct")
    http_module = ModuleType("akshare.utils.http")
    http_module.get = lambda *a, **kw: pytest.fail("Original HTTP client must not run")
    namespace = {"http": http_module, "URL": URL}
    exec("def provider():\n    return http.get(URL).json()", namespace)
    provider = namespace["provider"]
    assert isinstance(provider, FunctionType)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=b'{}\n200'))
    assert call_sector_provider(provider) == {}
    assert provider.__globals__["http"] is http_module
