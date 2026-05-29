import pytest
from fastapi import HTTPException

from ai_engine.auth.staff_session import require_roles


def test_allows_listed_role():
    dep = require_roles("supervisor", "admin")
    assert dep({"role": "admin"}) == {"role": "admin"}
    assert dep({"role": "supervisor"})["role"] == "supervisor"


def test_rejects_other_role():
    dep = require_roles("admin")
    with pytest.raises(HTTPException) as e:
        dep({"role": "agent"})
    assert e.value.status_code == 403
