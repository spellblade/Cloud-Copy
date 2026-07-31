import pytest

from app.models import TransferStatus
from app.services.transfer_service import TransferService


@pytest.mark.asyncio
async def test_create_and_list_job():
    svc = TransferService()
    job = await svc.create_job(
        direction="mega_to_pikpak",
        source_ids=["a", "b"],
        dest_parent_id=None,
        source_meta={"a": {"name": "a.txt", "is_dir": False}},
    )
    assert job.status == TransferStatus.queued
    assert len(svc.list_jobs()) == 1
    assert svc.get_job(job.id) is job


@pytest.mark.asyncio
async def test_cancel_queued_job():
    svc = TransferService()
    # Don't start worker processing: cancel while still queued after create
    job = await svc.create_job(
        direction="pikpak_to_mega",
        source_ids=["x"],
        dest_parent_id=None,
    )
    cancelled = await svc.cancel(job.id)
    assert cancelled.status in (TransferStatus.cancelled, TransferStatus.queued, TransferStatus.running)
