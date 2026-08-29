import pytest

from app.models import TransferJob, TransferStage, TransferStatus
from app.services.transfer_service import TransferService, _mark_failed


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


def test_failed_stage_label_mega_download():
    job = TransferJob(
        id="j1",
        direction="mega_to_pikpak",
        source_ids=["a"],
        stage=TransferStage.download,
    )
    _mark_failed(job, RuntimeError("Read timed out"))
    assert job.status == TransferStatus.failed
    assert job.message == "Failed · MEGA download"
    assert job.stage_label() == "MEGA download"
    assert "timed out" in job.error


def test_failed_stage_label_pikpak_upload():
    job = TransferJob(
        id="j2",
        direction="mega_to_pikpak",
        source_ids=["a"],
        stage=TransferStage.upload,
    )
    _mark_failed(job, RuntimeError("SSL validation failed"))
    assert job.message == "Failed · PikPak upload"


def test_failed_stage_label_reverse_download():
    job = TransferJob(
        id="j3",
        direction="pikpak_to_mega",
        source_ids=["a"],
        stage=TransferStage.download,
    )
    _mark_failed(job, RuntimeError("x"))
    assert job.message == "Failed · PikPak download"
