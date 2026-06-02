"""Tool: search_code（本地代码 grep）

被测对象：tools.search_code.run + _parse_grep
- repo 必须在 ALLOWED_REPOS。
- query 长度 1..200，max_hits 1..200。
- 未配置 repo 路径 → 返回 {hits:[], note:...}（不抛）。
- 真实临时仓库 grep 命中：返回 path/line/preview。
- 超时：模拟 subprocess 超时 → note='搜索超时…'。
- _parse_grep：跳过非 path:lineno:content 形式的行；max_hits 截断。
"""

import os
from pathlib import Path

import pytest

from ai_engine.agent.tools import search_code as sc


class TestArgValidation:
    async def test_invalid_repo(self) -> None:
        with pytest.raises(ValueError, match="repo"):
            await sc.run("unknown_repo", "X", 5)

    async def test_empty_query(self) -> None:
        with pytest.raises(ValueError, match="query length"):
            await sc.run("app_backend", "", 5)

    async def test_query_too_long(self) -> None:
        with pytest.raises(ValueError, match="query length"):
            await sc.run("app_backend", "x" * 201, 5)

    async def test_max_hits_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="max_hits"):
            await sc.run("app_backend", "x", 0)
        with pytest.raises(ValueError, match="max_hits"):
            await sc.run("app_backend", "x", 201)


class TestRepoNotConfigured:
    """settings.code_repo_paths 没该 repo → 返回 note，不抛。"""

    async def test_missing_path_returns_note(self, monkeypatch) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "code_repo_paths", {})
        out = await sc.run("app_backend", "anything")
        assert out["hits"] == []
        assert "未配置" in out["note"]

    async def test_path_exists_but_not_dir_returns_note(
        self, monkeypatch, tmp_path
    ) -> None:
        f = tmp_path / "not-a-dir"
        f.write_text("x")
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(
            _settings, "code_repo_paths", {"app_backend": str(f)}
        )
        out = await sc.run("app_backend", "x")
        assert out["hits"] == []


class TestParseGrep:
    """_parse_grep：处理 prefix 截断、非数字行号、max_hits 截断、坏行跳过。"""

    def test_strips_prefix_and_parses(self) -> None:
        base = "/tmp/myrepo"
        out = b"/tmp/myrepo/a.py:12:def foo():\n/tmp/myrepo/b.py:7:return 1\n"
        hits = sc._parse_grep(out, base, max_hits=10)
        assert len(hits) == 2
        assert hits[0] == {"path": "a.py", "line": 12, "preview": "def foo():"}
        assert hits[1]["path"] == "b.py"

    def test_skips_malformed_lines(self) -> None:
        base = "/x"
        out = b"no-colon-only\n/x/a.py:badline:hit\n"
        hits = sc._parse_grep(out, base, max_hits=10)
        assert len(hits) == 1  # 第 1 行跳过；第 2 行 line=0
        assert hits[0]["line"] == 0

    def test_truncates_to_max_hits(self) -> None:
        base = "/x"
        rows = [f"/x/f{i}.py:1:hit{i}" for i in range(20)]
        out = ("\n".join(rows) + "\n").encode()
        hits = sc._parse_grep(out, base, max_hits=5)
        assert len(hits) == 5
        assert hits[-1]["path"] == "f4.py"

    def test_preview_capped_to_300(self) -> None:
        base = "/x"
        long_line = "x" * 1000
        out = f"/x/f.py:1:{long_line}\n".encode()
        hits = sc._parse_grep(out, base, max_hits=1)
        assert len(hits[0]["preview"]) == 300


class TestRealGrep:
    """真实临时仓库下 grep 一段固定字符串。"""

    async def test_grep_finds_match_in_temp_repo(self, monkeypatch, tmp_path) -> None:
        # 准备一个 .py 文件包含目标字符串
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / "a.py").write_text("MATCH_THIS_KEY\nfoo bar\n")
        (repo / "b.py").write_text("nope nothing\n")
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(
            _settings, "code_repo_paths", {"app_backend": str(repo)}
        )
        # grep 命令可能在 mac/linux 都有；若没有则 skip
        from shutil import which

        if not which("grep"):
            pytest.skip("grep not available on this host")
        out = await sc.run("app_backend", "MATCH_THIS_KEY", 5)
        assert out["hits"]
        assert out["hits"][0]["path"] == "a.py"

    async def test_grep_no_match_returns_empty(
        self, monkeypatch, tmp_path
    ) -> None:
        repo = tmp_path / "r"
        repo.mkdir()
        (repo / "x.py").write_text("hello\n")
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "code_repo_paths", {"app_backend": str(repo)})
        if not os.access("/usr/bin/grep", os.X_OK) and not os.access(
            "/bin/grep", os.X_OK
        ):
            from shutil import which

            if not which("grep"):
                pytest.skip("grep not available")
        out = await sc.run("app_backend", "XX_NEVER_PRESENT_KEY", 5)
        assert out["hits"] == []

    async def test_excludes_node_modules(self, monkeypatch, tmp_path) -> None:
        repo = tmp_path / "r"
        (repo / "node_modules").mkdir(parents=True)
        (repo / "node_modules" / "lib.js").write_text("SECRET_TOKEN\n")
        (repo / "src.js").write_text("nothing here\n")
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "code_repo_paths", {"app_backend": str(repo)})
        from shutil import which

        if not which("grep"):
            pytest.skip("grep not available")
        out = await sc.run("app_backend", "SECRET_TOKEN", 5)
        # node_modules 被 exclude-dir，应当查不到
        assert out["hits"] == []


class TestTimeoutHandling:
    """模拟 wait_for TimeoutError，应返回 note='搜索超时…'。"""

    async def test_timeout_returns_note(self, monkeypatch, tmp_path) -> None:
        # 准备一个合法 repo（必须 isdir）
        repo = tmp_path / "r"
        repo.mkdir()
        (repo / "x.py").write_text("hello")
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "code_repo_paths", {"app_backend": str(repo)})

        # 替换 asyncio.wait_for 让它直接抛 TimeoutError
        async def _raise_timeout(*_a, **_k):  # noqa: ANN002,ANN003
            raise TimeoutError("simulated")

        monkeypatch.setattr(sc.asyncio, "wait_for", _raise_timeout)

        out = await sc.run("app_backend", "needle", 5)
        assert out["hits"] == []
        assert "超时" in out["note"]


class TestSymlinkResolved:
    """base = settings 路径含软链时 realpath 解析；确保 grep 进入实路径不丢命中。"""

    async def test_symlinked_repo_works(self, monkeypatch, tmp_path) -> None:
        real = tmp_path / "real"
        real.mkdir()
        (real / "f.py").write_text("MATCH_SYM\n")
        link = tmp_path / "link"
        try:
            Path(link).symlink_to(real)
        except OSError:
            pytest.skip("symlink not supported")
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "code_repo_paths", {"app_backend": str(link)})
        from shutil import which

        if not which("grep"):
            pytest.skip("grep not available")
        out = await sc.run("app_backend", "MATCH_SYM", 5)
        assert out["hits"] and out["hits"][0]["path"] == "f.py"
