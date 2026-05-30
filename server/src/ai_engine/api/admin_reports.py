"""自定义报表（supervisor/manager/admin）。"""

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, reports

router = APIRouter()
_view = require_roles("supervisor", "manager", "admin")


class DefIn(BaseModel):
    name: str
    source: str
    dims: list[str] = []
    filters: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = [{"op": "count", "col": "*", "alias": "n"}]


@router.get("/admin/api/v1/reports")
async def list_defs(staff: dict[str, Any] = Depends(_view)) -> dict[str, Any]:
    return {"definitions": await reports.list_definitions()}


@router.post("/admin/api/v1/reports")
async def create_def(body: DefIn, staff: dict[str, Any] = Depends(_view)) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    try:
        rid = await reports.create_definition(
            name=body.name, source=body.source,
            dims=body.dims, filters=body.filters, metrics=body.metrics,
            owner=actor,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await admin_audit.log_admin_action(
        actor=actor, action="report.create",
        target_type="report", target_id=str(rid), detail={"name": body.name},
    )
    return {"ok": True, "id": rid}


@router.delete("/admin/api/v1/reports/{report_id}")
async def delete_def(report_id: int, staff: dict[str, Any] = Depends(_view)) -> dict[str, Any]:
    await reports.delete_definition(report_id)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")), action="report.delete",
        target_type="report", target_id=str(report_id),
    )
    return {"ok": True}


async def _run(report_id: int) -> dict[str, Any]:
    d = await reports.get_definition(report_id)
    if d is None:
        raise HTTPException(404, "report not found")
    try:
        return await reports.execute(
            source=str(d["source"]),
            dims=json.loads(str(d["dims_json"])),
            filters=json.loads(str(d["filters_json"])),
            metrics=json.loads(str(d["metrics_json"])),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/admin/api/v1/reports/{report_id}/run")
async def run_def(report_id: int, staff: dict[str, Any] = Depends(_view)) -> dict[str, Any]:
    return await _run(report_id)


@router.get("/admin/api/v1/reports/{report_id}/export.csv")
async def export_csv(report_id: int, staff: dict[str, Any] = Depends(_view)) -> StreamingResponse:
    result = await _run(report_id)
    rows = result["rows"]
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.csv"'},
    )
