"""render-pod-lifecycle: the RunPod REST client against an in-memory RunPod."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from pydantic import SecretStr

from app.render.offload.runpod import (
    KEY_REJECTED,
    POD_NAME,
    VOLUME_MISSING,
    RunPodClient,
    RunPodError,
    pod_body,
)
from tests.offload_fakes import FakeRunPod

KEY = "rpa_SECRETKEYVALUE"


def client(fake: FakeRunPod, key: str = KEY) -> RunPodClient:
    return RunPodClient(SecretStr(key), transport=fake.transport)


def run(coroutine):
    return asyncio.run(coroutine)


def body(**overrides: str) -> dict:
    values = {"gpu_types": ("NVIDIA GeForce RTX 4090",), "image": "runpod/base:0.6.2", "volume_id": "vol123",
              "data_center_id": "EU-RO-1"}
    return pod_body(**{**values, **overrides})


def test_the_pod_body_is_constants_and_settings_only() -> None:
    made = body()
    assert made["name"] == POD_NAME == "hra-render"
    assert made["gpuTypeIds"] == ["NVIDIA GeForce RTX 4090"] and made["gpuCount"] == 1
    assert made["gpuTypePriority"] == "custom"
    assert made["cloudType"] == "SECURE"
    assert made["networkVolumeId"] == "vol123" and made["dataCenterIds"] == ["EU-RO-1"]
    assert made["volumeMountPath"] == "/workspace"
    assert made["ports"] == ["22/tcp"]
    assert made["imageName"] == "runpod/base:0.6.2"
    assert made["dockerStartCmd"][:2] == ["bash", "-c"]
    assert "PasswordAuthentication=no" in made["dockerStartCmd"][2]
    assert "dpkg -i /workspace/hra/debs/*.deb" in made["dockerStartCmd"][2]  # offline, from the volume
    assert "env" not in made


def test_every_request_goes_to_runpod_with_the_bearer_key() -> None:
    fake = FakeRunPod()
    run(client(fake).get_network_volume("vol123"))
    [request] = fake.requests
    assert str(request.url) == "https://rest.runpod.io/v1/networkvolumes/vol123"
    assert request.headers["Authorization"] == f"Bearer {KEY}"


def test_the_volume_reports_its_data_centre() -> None:
    volume = run(client(FakeRunPod()).get_network_volume("vol123"))
    assert volume.data_center_id == "EU-RO-1"


def test_an_unknown_volume_is_named() -> None:
    with pytest.raises(RunPodError) as caught:
        run(client(FakeRunPod()).get_network_volume("other"))
    assert caught.value.reason == VOLUME_MISSING and caught.value.status == 404


def test_a_rejected_key_is_reported_without_the_key(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    with pytest.raises(RunPodError) as caught:
        run(client(FakeRunPod(), key="rpa_WRONGKEYVALUE").get_network_volume("vol123"))
    assert caught.value.reason == KEY_REJECTED
    assert "rpa_WRONGKEYVALUE" not in str(caught.value) and "rpa_WRONGKEYVALUE" not in caplog.text
    assert "rpa_" not in repr(caught.value.args)


def test_runpod_down_is_unreachable() -> None:
    with pytest.raises(RunPodError, match="RunPod could not be reached"):
        run(client(FakeRunPod(down=True)).get_network_volume("vol123"))


def test_create_returns_a_pod_that_is_not_yet_reachable() -> None:
    fake = FakeRunPod(ready_after=1)
    pod = run(client(fake).create_pod(body(), gpu_types=["NVIDIA GeForce RTX 4090"]))
    assert pod.name == "hra-render" and not pod.reachable
    assert json.loads(fake.requests[0].content)["cloudType"] == "SECURE"
    again = run(client(fake).get_pod(pod.id))
    assert again.reachable and again.public_ip == "203.0.113.7" and again.ssh_port == 10341
    assert again.cost_per_hr == 0.69


@pytest.mark.parametrize(
    "text",
    [
        "There are no longer any instances available with the requested specifications.",
        "create pod: There are no instances currently available",  # seen live 2026-10-15
    ],
)
def test_no_capacity_names_the_gpu(text: str) -> None:
    with pytest.raises(RunPodError) as caught:
        run(client(FakeRunPod(no_capacity=True, no_capacity_text=text)).create_pod(
            body(), gpu_types=["NVIDIA GeForce RTX 4090"]
        ))
    assert caught.value.reason == "no NVIDIA GeForce RTX 4090 is free on RunPod right now"


def test_a_gone_pod_reads_as_none_and_deletes_quietly() -> None:
    fake = FakeRunPod()
    assert run(client(fake).get_pod("missing")) is None
    run(client(fake).delete_pod("missing"))


def test_a_failed_delete_is_an_error() -> None:
    fake = FakeRunPod(delete_fails=1)
    pod_id = fake.add_pod("hra-render")
    with pytest.raises(RunPodError, match="did not delete"):
        run(client(fake).delete_pod(pod_id))
    run(client(fake).delete_pod(pod_id))
    assert fake.deleted == [pod_id]


def test_the_list_holds_only_app_named_pods() -> None:
    fake = FakeRunPod()
    mine = fake.add_pod("hra-render")
    fake.add_pod("someone-else")
    pods = run(client(fake).list_pods())
    assert [pod.id for pod in pods] == [mine]
    assert fake.requests[0].url.params["name"] == "hra-render"


def test_with_several_types_none_free_names_them_all() -> None:
    fake = FakeRunPod(stock=set())
    with pytest.raises(RunPodError) as caught:
        run(client(fake).create_pod(
            body(gpu_types=("NVIDIA RTX A4500", "NVIDIA GeForce RTX 5090")),
            gpu_types=["NVIDIA RTX A4500", "NVIDIA GeForce RTX 5090"],
        ))
    assert caught.value.reason == "none of NVIDIA RTX A4500, NVIDIA GeForce RTX 5090 is free on RunPod right now"


def test_the_types_go_to_runpod_in_order_and_the_placed_one_is_read() -> None:
    fake = FakeRunPod(stock={"NVIDIA GeForce RTX 5090"})
    pod = run(client(fake).create_pod(
        body(gpu_types=("NVIDIA RTX A4500", "NVIDIA GeForce RTX 5090")),
        gpu_types=["NVIDIA RTX A4500", "NVIDIA GeForce RTX 5090"],
    ))
    assert fake.created[0]["gpuTypeIds"] == ["NVIDIA RTX A4500", "NVIDIA GeForce RTX 5090"]
    assert fake.created[0]["gpuTypePriority"] == "custom"
    assert pod.gpu_type == "NVIDIA GeForce RTX 5090"


# --- live stock (render-gpu-availability) ------------------------------------------------------------

A4500, R4090, R5090 = "NVIDIA RTX A4500", "NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 5090"


def test_stock_is_read_per_type_in_the_data_centre() -> None:
    fake = FakeRunPod(catalog={R4090: {"EU-RO-1": "LOW"}, R5090: {"US-IL-1": "HIGH"}, A4500: {"EU-RO-1": "SOLD"}})
    levels = run(client(fake).gpu_stock([A4500, R4090, R5090, "NVIDIA B200"], "EU-RO-1"))
    # 4090 listed here; 5090 only elsewhere; A4500 with an unknown level; B200 not in the catalog.
    assert levels == {A4500: "NONE", R4090: "LOW", R5090: "NONE", "NVIDIA B200": "NONE"}
    [request] = fake.requests
    assert str(request.url).startswith("https://api.runpod.io/v2/catalog/gpus?")
    assert dict(request.url.params) == {"include": "AVAILABILITY", "product": "POD", "cloud": "SECURE"}
    assert request.headers["Authorization"] == f"Bearer {KEY}"


@pytest.mark.parametrize(
    ("fake", "reason"),
    [
        (FakeRunPod(catalog_status=500), "RunPod answered 500"),
        (FakeRunPod(catalog_times_out=True), "RunPod could not be reached"),
    ],
)
def test_a_failed_stock_read_is_an_error_without_the_key(fake: FakeRunPod, reason: str) -> None:
    with pytest.raises(RunPodError) as caught:
        run(client(fake).gpu_stock([A4500], "EU-RO-1"))
    assert caught.value.reason.startswith(reason) and "rpa_" not in caught.value.reason


def test_a_rejected_key_on_the_catalog_is_named() -> None:
    with pytest.raises(RunPodError) as caught:
        run(client(FakeRunPod(), key="rpa_WRONGKEYVALUE").gpu_stock([A4500], "EU-RO-1"))
    assert caught.value.reason == KEY_REJECTED
