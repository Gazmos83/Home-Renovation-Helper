"""The live Blender socket client (photoreal-detail)."""

from __future__ import annotations

import asyncio

import pytest

from app.live.socket_client import (
    BLENDER_BUSY,
    NOT_OPEN,
    AddonError,
    LiveBlender,
    LiveRefused,
)
from tests.live_helpers import FakeAddon, sync


def ok(result):
    return {"status": "success", "result": result}


@sync
async def test_a_command_returns_the_result():
    addon = await FakeAddon(lambda command: ok({"executed": True, "result": "hi\n"})).start()
    try:
        client = LiveBlender("127.0.0.1", addon.port, semaphore=asyncio.Semaphore(1))
        result = await client.command("execute_code", {"code": "print('hi')"})
    finally:
        await addon.stop()
    assert result == {"executed": True, "result": "hi\n"}
    assert addon.received == [{"type": "execute_code", "params": {"code": "print('hi')"}}]


@sync
async def test_an_addon_error_is_raised_with_its_message():
    addon = await FakeAddon(lambda command: {"status": "error", "message": "Code execution error: boom"}).start()
    try:
        client = LiveBlender("127.0.0.1", addon.port, semaphore=asyncio.Semaphore(1))
        with pytest.raises(AddonError) as caught:
            await client.command("execute_code", {"code": "x"})
    finally:
        await addon.stop()
    assert caught.value.message == "Code execution error: boom"


@sync
async def test_connection_refused_says_blender_is_not_open():
    probe = await FakeAddon(lambda command: ok(None)).start()
    port = probe.port
    await probe.stop()
    client = LiveBlender("127.0.0.1", port, semaphore=asyncio.Semaphore(1))
    with pytest.raises(LiveRefused) as caught:
        await client.command("ping")
    assert caught.value.reason == NOT_OPEN


@sync
async def test_refused_while_a_headless_job_holds_the_semaphore():
    addon = await FakeAddon(lambda command: ok(None)).start()
    semaphore = asyncio.Semaphore(1)
    try:
        client = LiveBlender("127.0.0.1", addon.port, semaphore=semaphore)
        async with semaphore:
            with pytest.raises(LiveRefused) as caught:
                await client.command("ping")
    finally:
        await addon.stop()
    assert caught.value.reason == BLENDER_BUSY
    assert addon.received == []


@sync
async def test_a_headless_job_waits_while_a_command_holds_the_lock():
    release = asyncio.Event()
    started = asyncio.Event()

    async def slow(command):
        started.set()
        await release.wait()
        return ok("done")

    addon = await FakeAddon(slow).start()
    semaphore = asyncio.Semaphore(1)
    headless_ran = asyncio.Event()

    async def headless():
        async with semaphore:
            headless_ran.set()

    try:
        client = LiveBlender("127.0.0.1", addon.port, semaphore=semaphore)
        live = asyncio.create_task(client.command("execute_code", {"code": "x"}))
        await started.wait()
        job = asyncio.create_task(headless())
        await asyncio.sleep(0.05)
        assert not headless_ran.is_set()
        release.set()
        assert await live == "done"
        await job
    finally:
        await addon.stop()
    assert headless_ran.is_set()


@sync
async def test_a_slow_script_times_out_and_releases_the_lock():
    async def never(command):
        await asyncio.sleep(1.5)

    addon = await FakeAddon(never).start()
    semaphore = asyncio.Semaphore(1)
    try:
        client = LiveBlender("127.0.0.1", addon.port, semaphore=semaphore, timeout=0.2)
        with pytest.raises(LiveRefused) as caught:
            await client.command("execute_code", {"code": "x"})
    finally:
        await addon.stop()
    assert "did not answer" in caught.value.reason
    assert not semaphore.locked()


@sync
async def test_a_large_answer_in_several_reads_is_assembled():
    big = "x" * 200_000
    addon = await FakeAddon(lambda command: ok(big)).start()
    try:
        client = LiveBlender("127.0.0.1", addon.port, semaphore=asyncio.Semaphore(1))
        assert await client.command("get_scene_info") == big
    finally:
        await addon.stop()
