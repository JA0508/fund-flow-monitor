from src.providers.provider_transport import normalize_today_sector_params


def test_today_sector_request_uses_stable_sort_without_stale_parameters():
    original = {"stat": "1", "fs": "m:90 t:2", "fid0": "f62", "ut": "old", "rt": "old", "_": 123, "pn": 2, "fields": "f12,f62"}
    result = normalize_today_sector_params(original)
    assert result == {"fs": "m:90 t:2", "fid": "f12", "pn": 2, "fields": "f12,f62"}
    assert original["ut"] == "old"


def test_other_requests_are_unchanged():
    original = {"stat": "5", "fs": "m:90 t:2", "fid0": "f164"}
    assert normalize_today_sector_params(original) == original
