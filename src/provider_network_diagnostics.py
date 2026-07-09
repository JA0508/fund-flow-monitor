from __future__ import annotations

import json
import os
import re
import socket
from typing import Any

import requests

from src.providers.akshare_sector_flow import (
    API_NAME,
    DEFAULT_INDICATOR,
    DEFAULT_SECTOR_TYPE,
    ProviderBoundaryError,
    fetch_raw_sector_flow,
    validate_provider_text,
)


UPSTREAM_HOST = "push2.eastmoney.com"
UPSTREAM_URL = "https://push2.eastmoney.com"
PROXY_ENV_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy")


def _sanitize_message(message: object, max_len: int = 240) -> str:
    text = str(message or "")
    for name in PROXY_ENV_NAMES:
        value = os.environ.get(name)
        if value:
            text = text.replace(value, f"<{name}_redacted>")
    text = re.sub(r"https?://[^\s\"')]+", "<request_url_redacted>", text)
    text = re.sub(r"url:\s*/[^\s\"')]+", "url: <request_url_redacted>", text)
    text = text.replace("://", ":[slash][slash]")
    return text[:max_len]


def get_proxy_presence_flags() -> dict[str, bool]:
    return {
        "HTTP_PROXY": bool(os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")),
        "HTTPS_PROXY": bool(os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")),
        "ALL_PROXY": bool(os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")),
        "NO_PROXY": bool(os.environ.get("NO_PROXY") or os.environ.get("no_proxy")),
    }


def diagnose_dns(hostname: str = UPSTREAM_HOST) -> dict[str, Any]:
    try:
        socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
        return {"stage": "dns", "hostname": hostname, "success": True, "error_type": None, "message": "DNS resolution succeeded."}
    except Exception as exc:
        return {"stage": "dns", "hostname": hostname, "success": False, "error_type": type(exc).__name__, "message": _sanitize_message(exc)}


def diagnose_tcp(hostname: str = UPSTREAM_HOST, port: int = 443, timeout: float = 3.0) -> dict[str, Any]:
    try:
        with socket.create_connection((hostname, int(port)), timeout=timeout):
            pass
        return {"stage": "tcp", "hostname": hostname, "port": int(port), "success": True, "error_type": None, "message": "TCP connection succeeded."}
    except Exception as exc:
        return {"stage": "tcp", "hostname": hostname, "port": int(port), "success": False, "error_type": type(exc).__name__, "message": _sanitize_message(exc)}


def diagnose_http(url: str = UPSTREAM_URL, timeout: float = 5.0) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=timeout)
        return {
            "stage": "http",
            "url_host": UPSTREAM_HOST,
            "success": bool(response.status_code < 500),
            "status_code": int(response.status_code),
            "error_type": None,
            "message": f"HTTP request returned status {response.status_code}.",
        }
    except Exception as exc:
        return {"stage": "http", "url_host": UPSTREAM_HOST, "success": False, "status_code": None, "error_type": type(exc).__name__, "message": _sanitize_message(exc)}


def diagnose_akshare_provider() -> dict[str, Any]:
    try:
        result = fetch_raw_sector_flow(sector_type=DEFAULT_SECTOR_TYPE, indicator=DEFAULT_INDICATOR, attempts=1)
        diagnostic = result.diagnostic or {}
        return {
            "stage": "akshare_provider",
            "provider_api": API_NAME,
            "success": True,
            "error_category": None,
            "error_type": None,
            "row_count": int(diagnostic.get("row_count", 0) or 0),
            "message": "AKShare provider probe succeeded.",
        }
    except ProviderBoundaryError as exc:
        return {
            "stage": "akshare_provider",
            "provider_api": API_NAME,
            "success": False,
            "error_category": exc.category,
            "error_type": type(exc.original).__name__ if exc.original is not None else type(exc).__name__,
            "row_count": 0,
            "message": _sanitize_message(exc),
        }
    except Exception as exc:
        return {
            "stage": "akshare_provider",
            "provider_api": API_NAME,
            "success": False,
            "error_category": "provider_error",
            "error_type": type(exc).__name__,
            "row_count": 0,
            "message": _sanitize_message(exc),
        }


def classify_network_diagnosis(report: dict) -> str:
    proxy_flags = report.get("proxy_presence_flags") or {}
    stages = {item.get("stage"): item for item in report.get("stages", [])}
    if not stages.get("dns", {}).get("success"):
        return "dns_failure"
    if not stages.get("tcp", {}).get("success"):
        return "tcp_unreachable"
    if not stages.get("http", {}).get("success"):
        return "tls_or_http_failure"
    provider_stage = stages.get("akshare_provider", {})
    if provider_stage and not provider_stage.get("success"):
        category = str(provider_stage.get("error_category") or "")
        if "parse" in category:
            return "provider_parse_failure"
        return "provider_request_failure"
    if provider_stage.get("success"):
        return "provider_success"
    if any(proxy_flags.values()):
        return "proxy_configuration_present"
    return "network_diagnostic_completed"


def build_provider_network_diagnosis(include_akshare: bool = True, include_http: bool = True) -> dict:
    stages = [diagnose_dns(), diagnose_tcp()]
    if include_http:
        stages.append(diagnose_http())
    if include_akshare:
        stages.append(diagnose_akshare_provider())
    report = {
        "proxy_presence_flags": get_proxy_presence_flags(),
        "stages": stages,
    }
    report["final_classification"] = classify_network_diagnosis(report)
    report["forbidden_hits"] = validate_provider_text(json.dumps(report, ensure_ascii=False))
    return report


def validate_network_diagnostic_text(text: str) -> list[str]:
    return validate_provider_text(text)
