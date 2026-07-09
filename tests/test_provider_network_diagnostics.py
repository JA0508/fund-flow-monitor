from __future__ import annotations

import os

import pytest

from src import provider_network_diagnostics as diag


def test_proxy_flags_do_not_expose_values(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://user:password@example.com:8080")
    flags = diag.get_proxy_presence_flags()
    assert flags["HTTPS_PROXY"] is True
    assert "password" not in str(flags)


def test_sanitize_message_redacts_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://user:password@example.com:8080")
    text = diag._sanitize_message("failed via http://user:password@example.com:8080")
    assert "password" not in text
    assert "http://user" not in text


def test_sanitize_message_redacts_request_query():
    text = diag._sanitize_message("failed with url: /api/qt/clist/get?token=secret&fields=f62")
    assert "/api/qt/clist/get" not in text
    assert "secret" not in text
    assert "<request_url_redacted>" in text


def test_dns_failure_classification(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("dns nope")

    monkeypatch.setattr(diag.socket, "getaddrinfo", boom)
    result = diag.diagnose_dns("example.invalid")
    assert result["success"] is False
    report = {"proxy_presence_flags": {}, "stages": [result]}
    assert diag.classify_network_diagnosis(report) == "dns_failure"


def test_network_report_can_skip_live_akshare(monkeypatch):
    monkeypatch.setattr(diag, "diagnose_dns", lambda *a, **k: {"stage": "dns", "success": True})
    monkeypatch.setattr(diag, "diagnose_tcp", lambda *a, **k: {"stage": "tcp", "success": True})
    monkeypatch.setattr(diag, "diagnose_http", lambda *a, **k: {"stage": "http", "success": False, "error_type": "ProxyError"})
    report = diag.build_provider_network_diagnosis(include_akshare=False, include_http=True)
    assert report["final_classification"] == "tls_or_http_failure"
    assert "akshare_provider" not in [stage["stage"] for stage in report["stages"]]
