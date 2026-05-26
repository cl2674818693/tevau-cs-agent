"""C 端用户咨询时绝不能出现 'Open API' 字眼（那是 B 端概念）。
线上现象：C 端问 1+1 被拒答时模板说'账户、卡片或 Open API'，泄露了 B 端术语。"""
import pytest

from ai_engine.prompts.loader import build_system_blocks

VERS = ["v1.0.0", "v1.1.0"]


@pytest.mark.parametrize("ver", VERS)
def test_c_user_prompt_has_no_open_api(ver):
    text = "\n".join(b["text"] for b in build_system_blocks(user_type="c", version=ver))
    assert "Open API" not in text and "OpenAPI" not in text


@pytest.mark.parametrize("ver", VERS)
def test_guest_prompt_has_no_open_api(ver):
    text = "\n".join(b["text"] for b in build_system_blocks(user_type="g", version=ver))
    assert "Open API" not in text and "OpenAPI" not in text


@pytest.mark.parametrize("ver", VERS)
def test_b_user_prompt_keeps_open_api(ver):
    # B 端是 Open API 对接方，技术口径要保留
    text = "\n".join(b["text"] for b in build_system_blocks(user_type="b", version=ver))
    assert "Open API" in text
