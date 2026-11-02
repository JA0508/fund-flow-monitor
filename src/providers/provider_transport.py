"""Explicit, provider-local transport without changing requests or process proxies."""

import json
import os
import re
import subprocess
from types import FunctionType, ModuleType, SimpleNamespace
from urllib.parse import urlencode

import requests


ENDPOINT = "https://push2.eastmoney.com/api/qt/clist/get"
MAX_BYTES = 4 * 1024 * 1024


def _require_supported_curl():
    try:
        result = subprocess.run(["curl", "--disable", "--version"], capture_output=True,
                                timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise requests.ConnectionError("Unable to verify curl version") from None
    match = re.match(rb"curl (\d+)\.(\d+)\.(\d+)\b", result.stdout)
    if result.returncode or not match or tuple(map(int, match.groups())) < (8, 4, 0):
        raise requests.ConnectionError("Provider direct transport requires curl >= 8.4.0")


def call_sector_provider(provider, **kwargs):
    mode = os.environ.get("FUND_FLOW_PROVIDER_TRANSPORT", "requests")
    if mode == "requests":
        return provider(**kwargs)
    if mode != "curl_direct":
        raise ValueError("Unsupported provider transport")
    if not isinstance(provider, FunctionType):
        raise ValueError("Unsupported AKShare transport binding")
    bindings = {}
    if provider.__globals__.get("requests") is requests:
        bindings["requests"] = None
    http = provider.__globals__.get("http")
    if isinstance(http, ModuleType) and http.__name__ == "akshare.utils.http":
        bindings["http"] = None
    if not bindings:
        raise ValueError("Unsupported AKShare transport binding")
    _require_supported_curl()
    count = 0

    def get(url, *, params=None, headers=None, timeout=None):
        nonlocal count
        if url != ENDPOINT or count >= 10:
            raise ValueError("Provider request outside transport boundary")
        count += 1
        return _curl_get(url, params, headers)

    # Clone only this function's globals; never monkey-patch AKShare or requests.
    overrides = {name: SimpleNamespace(get=get) for name in bindings}
    local = FunctionType(provider.__code__, {**provider.__globals__, **overrides},
                         provider.__name__, provider.__defaults__, provider.__closure__)
    local.__kwdefaults__ = provider.__kwdefaults__
    return local(**kwargs)


def _curl_get(url, params, headers):
    command = ["curl", "--disable", "--noproxy", "*", "--silent", "--show-error",
               "--proto", "=https", "--connect-timeout", "5", "--max-time", "15",
               "--max-filesize", str(MAX_BYTES), "--write-out", "\n%{http_code}"]
    for key, value in (headers or {}).items():
        if key.lower() != "user-agent" or "\n" in value or "\r" in value:
            raise ValueError("Unsupported provider header")
        command.extend(["--user-agent", value])
    command.append(url + "?" + urlencode(params or {}, doseq=True))
    try:
        result = subprocess.run(command, capture_output=True, timeout=20, check=False)
    except subprocess.TimeoutExpired:
        raise requests.Timeout("Provider curl request timed out") from None
    except OSError:
        raise requests.ConnectionError("Provider curl executable unavailable") from None
    if result.returncode:
        error = requests.Timeout if result.returncode == 28 else requests.ConnectionError
        raise error(f"Provider curl transport failed (exit {result.returncode})")
    body, _, status = result.stdout.rpartition(b"\n")
    if status != b"200" or len(body) > MAX_BYTES:
        raise requests.HTTPError("Provider response rejected (HTTP status or size)")
    payload = json.loads(body)
    return SimpleNamespace(json=lambda: payload)
