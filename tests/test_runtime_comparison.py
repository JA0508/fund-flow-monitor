import pandas as pd
import pytest

from tools.verify_runtime import _semiconductor_comparison


@pytest.mark.parametrize("empty_index", [0, 1, 2, None])
def test_comparison_preserves_missing_modes(empty_index, capsys):
    populated = pd.DataFrame([{
        "theme_name": "半导体/芯片链",
        "main_net_inflow_billion": 1.5,
        "used_sectors": "test-sector",
        "used_sector_count": 1,
    }])
    frames = [
        pd.DataFrame() if empty_index is None or index == empty_index else populated.copy()
        for index in range(3)
    ]
    originals = [frame.copy(deep=True) for frame in frames]
    _semiconductor_comparison(*frames)
    output = capsys.readouterr().out
    for index, mode in enumerate(("strict", "representative", "breadth")):
        value = "<empty>" if frames[index].empty else "1.5"
        assert f"{mode} value: {value}" in output
        pd.testing.assert_frame_equal(frames[index], originals[index])


def test_comparison_does_not_hide_nonempty_invalid_schema():
    with pytest.raises(KeyError, match="theme_name"):
        _semiconductor_comparison(pd.DataFrame({"invalid": [1]}), pd.DataFrame(), pd.DataFrame())
