"""loader.load() DB-first：已发布优先于文件；缺失回退文件。"""


async def test_db_published_wins(temp_db_url, monkeypatch, tmp_path):
    from ai_engine.persistence import prompt_drafts
    from ai_engine.persistence.db import init_db
    await init_db()
    import shutil
    from pathlib import Path
    src = Path("src/ai_engine/prompts")
    shutil.copytree(src, tmp_path / "prompts")
    monkeypatch.setenv("PROMPTS_DIR", str(tmp_path / "prompts"))
    from ai_engine.config import settings
    settings.reload()

    did = await prompt_drafts.create_draft("v1.0.0", "reply_style.c.md", "DB优先内容", "EN1")
    await prompt_drafts.publish(did, "EN1")

    from ai_engine.prompts import loader
    content = await loader.load(version="v1.0.0", file_name="reply_style.c.md")
    assert "DB优先内容" in content


async def test_db_missing_falls_back_to_file(temp_db_url, monkeypatch, tmp_path):
    from ai_engine.persistence.db import init_db
    await init_db()
    import shutil
    from pathlib import Path
    src = Path("src/ai_engine/prompts")
    shutil.copytree(src, tmp_path / "prompts")
    monkeypatch.setenv("PROMPTS_DIR", str(tmp_path / "prompts"))
    from ai_engine.config import settings
    settings.reload()

    from ai_engine.prompts import loader
    content = await loader.load(version="v1.0.0", file_name="reply_style.c.md")
    assert content and len(content) > 0
