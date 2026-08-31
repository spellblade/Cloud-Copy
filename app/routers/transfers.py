# Transfer HTTP + WebSocket routes: queue, list, cancel, retry, live job updates.

from __future__ import annotations

import asyncio
import json
from typing import Set

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.models import (
    MessageResponse,
    TransferCreateRequest,
    TransferJob,
    TransferListResponse,
)
from app.services.transfer_service import transfer_service

router = APIRouter(tags=["transfers"])

_ws_clients: Set[WebSocket] = set()


async def _broadcast_job(job: TransferJob) -> None:
    # Push one job snapshot to every connected WS client; drop dead sockets.
    payload = json.dumps({"type": "job", "job": job.model_dump(mode="json")})
    dead: list[WebSocket] = []
    for ws in list(_ws_clients):
        try:
            await ws.send_text(payload)
        except Exception:  # noqa: BLE001
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


# Register broadcast listener once
transfer_service.add_listener(_broadcast_job)


@router.get("/api/transfers", response_model=TransferListResponse)
async def list_transfers() -> TransferListResponse:
    # All jobs, newest first — used on page load before WS snapshot arrives.
    return TransferListResponse(jobs=transfer_service.list_jobs())


@router.post("/api/transfers", response_model=TransferJob)
async def create_transfer(body: TransferCreateRequest) -> TransferJob:
    # Enqueue a local-relay transfer (download to temp, then upload).
    try:
        job = await transfer_service.create_job(
            direction=body.direction,
            source_ids=body.source_ids,
            dest_parent_id=body.dest_parent_id,
            source_meta=body.source_meta,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job


@router.post("/api/transfers/{job_id}/cancel", response_model=TransferJob)
async def cancel_transfer(job_id: str) -> TransferJob:
    # Request cancel; a mid-flight download/upload finishes its current step first.
    try:
        return await transfer_service.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@router.post("/api/transfers/{job_id}/retry", response_model=TransferJob)
async def retry_transfer(job_id: str) -> TransferJob:
    # Re-queue a failed or cancelled job from the start.
    try:
        return await transfer_service.retry(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.websocket("/ws/transfers")
async def transfers_ws(websocket: WebSocket) -> None:
    # Live job stream: snapshot on connect, then per-job updates; ping on idle.
    await websocket.accept()
    _ws_clients.add(websocket)
    # send snapshot
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "snapshot",
                    "jobs": [j.model_dump(mode="json") for j in transfer_service.list_jobs()],
                }
            )
        )
        while True:
            # keep alive; client may send pings
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)
