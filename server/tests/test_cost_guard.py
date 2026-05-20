def test_cost_guard_limits_depth():
    from ai_engine.agent.cost_guard import CostGuard

    g = CostGuard(max_depth=3, max_result_bytes=1024)
    assert g.can_call_again() is True
    g.note_call()
    g.note_call()
    g.note_call()
    assert g.can_call_again() is False


def test_cost_guard_truncates_large_result():
    from ai_engine.agent.cost_guard import CostGuard

    g = CostGuard(max_depth=12, max_result_bytes=10)
    out, truncated = g.maybe_truncate("a" * 100)
    assert truncated is True
    assert len(out) <= 10
