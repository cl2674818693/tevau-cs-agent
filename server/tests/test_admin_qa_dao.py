import json

from ai_engine.persistence import admin_qa


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_scorecard_crud(temp_db_url):
    await _init(temp_db_url)
    sid = await admin_qa.create_scorecard(
        "默认评分卡", [{"key": "polite", "label": "礼貌", "weight": 1}]
    )
    rows = await admin_qa.list_scorecards()
    assert len(rows) == 1 and rows[0]["id"] == sid
    parsed = json.loads(rows[0]["items_json"])
    assert parsed[0]["key"] == "polite"
    await admin_qa.set_scorecard_active(sid, 0)
    assert int((await admin_qa.list_scorecards())[0]["active"]) == 0


async def test_review_submit_and_list_by_conv(temp_db_url):
    await _init(temp_db_url)
    sid = await admin_qa.create_scorecard("c1", [{"key": "polite"}])
    rid = await admin_qa.submit_review(
        conversation_id=42, reviewer_staff_id="SUP1", scorecard_id=sid,
        score=88, items_result={"polite": 1}, tags="excellent", comment="不错",
    )
    rows = await admin_qa.list_reviews(conversation_id=42)
    assert len(rows) == 1 and rows[0]["id"] == rid
    assert rows[0]["score"] == 88
    assert rows[0]["tags"] == "excellent"


async def test_list_reviews_filter_by_reviewer(temp_db_url):
    await _init(temp_db_url)
    sid = await admin_qa.create_scorecard("c1", [])
    await admin_qa.submit_review(conversation_id=1, reviewer_staff_id="SUP1",
                                 scorecard_id=sid, score=80, items_result={})
    await admin_qa.submit_review(conversation_id=2, reviewer_staff_id="SUP2",
                                 scorecard_id=sid, score=60, items_result={})
    rows = await admin_qa.list_reviews(reviewer_staff_id="SUP1")
    assert len(rows) == 1 and rows[0]["reviewer_staff_id"] == "SUP1"
