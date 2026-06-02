"""Tool: read_file

被测对象：tools.read_file.run + _validate_path / _read_sync
- repo 必须在 ALLOWED_REPOS。
- path 校验：禁止 .. / 绝对路径 / 反斜杠 / 超长。
- 路径解析后必须仍在 base 目录内（二次越权防护）。
- repo 未配置 → ValueError。
- 文件不存在 → ValueError。
- start_line / end_line 行号区间裁剪。
- 超 MAX_BYTES 截断并打 truncated=True。
"""

import pytest

from ai_engine.agent.tools import read_file as rf


class TestValidatePath:
    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            rf._validate_path("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError):
            rf._validate_path("a/" * 300)

    def test_rejects_dotdot(self) -> None:
        with pytest.raises(ValueError, match="relative"):
            rf._validate_path("../etc/passwd")

    def test_rejects_dotdot_in_middle(self) -> None:
        with pytest.raises(ValueError, match="relative"):
            rf._validate_path("src/../../etc")

    def test_rejects_absolute(self) -> None:
        with pytest.raises(ValueError, match="relative"):
            rf._validate_path("/etc/passwd")

    def test_rejects_backslash(self) -> None:
        with pytest.raises(ValueError, match="relative"):
            rf._validate_path("src\\evil")

    def test_accepts_relative(self) -> None:
        # 不抛
        rf._validate_path("src/main.py")


class TestRunValidation:
    async def test_invalid_repo(self) -> None:
        with pytest.raises(ValueError, match="repo"):
            await rf.run("nope", "a.py")

    async def test_repo_not_configured(self, monkeypatch) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "code_repo_paths", {})
        with pytest.raises(ValueError, match="未配置"):
            await rf.run("app_backend", "a.py")

    async def test_repo_path_missing_on_disk(
        self, monkeypatch, tmp_path
    ) -> None:
        from ai_engine.config import settings as _settings

        missing = tmp_path / "ghost"
        monkeypatch.setattr(
            _settings, "code_repo_paths", {"app_backend": str(missing)}
        )
        with pytest.raises(ValueError, match="代码仓库未配置"):
            await rf.run("app_backend", "a.py")


class TestReadRealFile:
    @pytest.fixture
    def _repo(self, monkeypatch, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / "a.py").write_text("line1\nline2\nline3\nline4\n")
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "code_repo_paths", {"app_backend": str(repo)})
        return repo

    async def test_full_read(self, _repo) -> None:
        out = await rf.run("app_backend", "a.py")
        assert "line1" in out["content"]
        assert "line4" in out["content"]
        assert out["truncated"] is False

    async def test_start_end_line_slice(self, _repo) -> None:
        out = await rf.run("app_backend", "a.py", start_line=2, end_line=3)
        # 取 line2 + line3
        assert "line2" in out["content"]
        assert "line3" in out["content"]
        assert "line1" not in out["content"]
        assert "line4" not in out["content"]

    async def test_start_only(self, _repo) -> None:
        out = await rf.run("app_backend", "a.py", start_line=3)
        assert "line3" in out["content"]
        assert "line1" not in out["content"]

    async def test_end_only(self, _repo) -> None:
        out = await rf.run("app_backend", "a.py", end_line=2)
        assert "line1" in out["content"]
        assert "line2" in out["content"]
        assert "line3" not in out["content"]

    async def test_file_not_found(self, _repo) -> None:
        with pytest.raises(ValueError, match="file not found"):
            await rf.run("app_backend", "missing.py")

    async def test_truncates_large_file(
        self, monkeypatch, _repo
    ) -> None:
        # 调低 MAX_BYTES 让真实 4 行文件也截断
        monkeypatch.setattr(rf, "MAX_BYTES", 5)
        out = await rf.run("app_backend", "a.py")
        assert out["truncated"] is True
        # 注意：MAX_BYTES=5 时只读前 5 字节；start/end 行号会针对截断后的内容裁剪
        assert len(out["content"].encode("utf-8")) <= 5


class TestSymlinkEscapeBlocked:
    """虽然 path 字面没 ..，但若软链指向 base 外，二次防护应当抛。"""

    async def test_symlink_outside_base_rejected(
        self, monkeypatch, tmp_path
    ) -> None:
        outside = tmp_path / "secret.txt"
        outside.write_text("top secret")
        repo = tmp_path / "repo"
        repo.mkdir()
        link = repo / "link.txt"
        try:
            link.symlink_to(outside)
        except OSError:
            pytest.skip("symlink unsupported")
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "code_repo_paths", {"app_backend": str(repo)})
        with pytest.raises(ValueError, match="越权"):
            await rf.run("app_backend", "link.txt")
