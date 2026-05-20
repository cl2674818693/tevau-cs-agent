def test_loader_returns_system_blocks_b():
    from ai_engine.prompts.loader import build_system_blocks

    blocks = build_system_blocks(user_type="b")
    texts = [b["text"] for b in blocks]
    assert any("角色" in t or "你是" in t for t in texts)
    assert any("分类" in t for t in texts)


def test_loader_b_uses_b_style():
    from ai_engine.prompts.loader import build_system_blocks

    blocks = build_system_blocks(user_type="b")
    text = "\n".join(b["text"] for b in blocks)
    assert "技术" in text  # b 端可显露技术细节


def test_loader_includes_topic_scope():
    """spec §6.4: 必须包含话题边界约束 + 固定 refusal 模板"""
    from ai_engine.prompts.loader import build_system_blocks

    text = "\n".join(b["text"] for b in build_system_blocks(user_type="b"))
    assert "Tevau" in text and ("refuse" in text.lower() or "拒绝" in text or "我是 Tevau" in text)


def test_loader_includes_language_mirror():
    """spec §6.2: AI 必须按用户语言镜像回复"""
    from ai_engine.prompts.loader import build_system_blocks

    text = "\n".join(b["text"] for b in build_system_blocks(user_type="b"))
    assert "镜像" in text or "same language" in text.lower()


def test_loader_includes_business_category():
    """spec §6.1: 分类必须包含商务/账户操作 类"""
    from ai_engine.prompts.loader import build_system_blocks

    text = "\n".join(b["text"] for b in build_system_blocks(user_type="b"))
    assert "商务" in text or "账户操作" in text


def test_loader_includes_handoff_trigger():
    """spec §13.7: AI 必须识别用户转人工意图（MVP-1 无 /request-human 端点，靠 prompt）"""
    from ai_engine.prompts.loader import build_system_blocks

    text = "\n".join(b["text"] for b in build_system_blocks(user_type="b"))
    assert "转人工" in text or "人工介入" in text
