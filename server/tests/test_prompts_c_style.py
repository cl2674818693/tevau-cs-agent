def test_loader_c_returns_c_style():
    from ai_engine.prompts.loader import build_system_blocks

    blocks = build_system_blocks(user_type="c")
    text = "\n".join(b["text"] for b in blocks)
    assert "大白话" in text
    assert "file:line" in text  # 显式禁止输出
    assert "R-217" in text  # 显式禁止规则名


def test_loader_c_still_has_topic_scope_and_classification():
    """C 端也必须保留话题边界 + 分类 + 语言镜像。"""
    from ai_engine.prompts.loader import build_system_blocks

    text = "\n".join(b["text"] for b in build_system_blocks(user_type="c"))
    assert "Tevau" in text
    assert "镜像" in text or "same language" in text.lower()
    assert "商务" in text or "账户操作" in text
