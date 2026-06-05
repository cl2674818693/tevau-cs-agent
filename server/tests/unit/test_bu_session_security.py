"""B-P1-7: BU session 生产环境安全护栏 —— DEV_TRUST_BU_HEADER 仅 dev/test 生效。

生产环境 misconfigured（DEV_TRUST_BU_HEADER=true 漏改）时，前端任意构造 X-BU-ID 头即可
冒充任意租户。运行时硬约束：env=production 时永远忽略 X-BU-ID，无论 dev_trust_bu_header
开关状态。
"""

import pytest

from ai_engine.auth.bu_session import _tenant_from_request
from ai_engine.config import settings


class _FakeRequest:
    """最小 Request 替身，仅暴露 cookies / headers 属性供 _tenant_from_request 读取。"""

    def __init__(self, headers: dict[str, str] | None = None, cookies: dict[str, str] | None = None) -> None:
        self.cookies = cookies or {}
        self.headers = headers or {}


class TestDevTrustBuHeaderInProduction:
    def test_x_bu_id_ignored_in_production_even_if_flag_on(self, monkeypatch):
        """env=production + dev_trust_bu_header=True → 仍拒绝 X-BU-ID（防 misconfig）。"""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("DEV_TRUST_BU_HEADER", "true")
        settings.reload()
        try:
            req = _FakeRequest(headers={"X-BU-ID": "1011010000068"})
            assert _tenant_from_request(req) is None
        finally:
            monkeypatch.delenv("ENV", raising=False)
            monkeypatch.delenv("DEV_TRUST_BU_HEADER", raising=False)
            settings.reload()

    def test_x_bu_id_accepted_in_dev_when_flag_on(self, monkeypatch):
        """env=dev + dev_trust_bu_header=True → X-BU-ID 可被信任（保留现有 dev/test 行为）。"""
        monkeypatch.setenv("ENV", "dev")
        monkeypatch.setenv("DEV_TRUST_BU_HEADER", "true")
        settings.reload()
        try:
            req = _FakeRequest(headers={"X-BU-ID": "1011010000068"})
            assert _tenant_from_request(req) == "1011010000068"
        finally:
            monkeypatch.delenv("ENV", raising=False)
            monkeypatch.delenv("DEV_TRUST_BU_HEADER", raising=False)
            settings.reload()

    def test_x_bu_id_ignored_when_flag_off_in_dev(self, monkeypatch):
        """env=dev + dev_trust_bu_header=False → X-BU-ID 头无效（默认安全）。"""
        monkeypatch.setenv("ENV", "dev")
        monkeypatch.setenv("DEV_TRUST_BU_HEADER", "false")
        settings.reload()
        try:
            req = _FakeRequest(headers={"X-BU-ID": "1011010000068"})
            assert _tenant_from_request(req) is None
        finally:
            monkeypatch.delenv("ENV", raising=False)
            monkeypatch.delenv("DEV_TRUST_BU_HEADER", raising=False)
            settings.reload()
