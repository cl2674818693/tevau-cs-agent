"""tools_usage 提示词的工具边界护栏（修复"查不到就是没有"导致 AI 误报"您没有交易"）。"""
import pytest

from ai_engine.prompts.loader import read_prompt

VERSIONS = ["v1.0.0", "v1.1.0"]


@pytest.mark.parametrize("ver", VERSIONS)
def test_no_harmful_absent_means_none(ver):
    # 旧指令"查不到就是没有"会让 AI 把单工具查空当成业务事实，必须删除
    text = read_prompt("tools_usage", version=ver)
    assert "查不到就是没有" not in text


@pytest.mark.parametrize("ver", VERSIONS)
def test_has_boundary_guardrail(ver):
    text = read_prompt("tools_usage", version=ver)
    assert "查不到" in text and "≠" in text  # 明确"查不到 ≠ 用户没有"


@pytest.mark.parametrize("ver", VERSIONS)
def test_kyc_authoritative_field(ver):
    text = read_prompt("tools_usage", version=ver)
    assert "user_kyc_status" in text


@pytest.mark.parametrize("ver", VERSIONS)
def test_keeps_cross_tenant_isolation_rule(ver):
    # 安全护栏（绝不查其他用户/BU）必须保留
    text = read_prompt("tools_usage", version=ver)
    assert "绝不尝试查其他用户/BU 的数据" in text
