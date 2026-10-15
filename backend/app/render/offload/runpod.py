"""The five RunPod REST calls pod mode needs (render-pod-lifecycle design decisions 2 and 3).

One fixed host, no redirects, a short timeout. The API key is read from its
`SecretStr` only to build the header, and never reaches an exception, a log line
or a record. A failure becomes `RunPodError` with a reason safe to show; response
bodies are only inspected, never logged.

The pod body is built only from constants and validated settings: the pod's name
is the app-owned `hra-render` (what the startup cleanup looks for), only SSH is
exposed, and the start command is a fixed string that installs the host key and
the authorised key kept on the network volume and runs `sshd`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

import httpx
from pydantic import SecretStr

RUNPOD_API: Final = "https://rest.runpod.io/v1"
TIMEOUT_SECONDS: Final = 15.0
POD_NAME: Final = "hra-render"
VOLUME_MOUNT: Final = "/workspace"
CONTAINER_DISK_GB: Final = 10

# Runs as the container's command. Everything it reads is on the network volume,
# put there once by the owner's setup script (scripts/runpod/setup_volume.sh).
START_COMMAND: Final = (
    "set -e; "
    # The image's missing system packages (Blender's libraries, sshd), saved once on the
    # volume so every new pod installs them offline in seconds.
    "if ls /workspace/hra/debs/*.deb >/dev/null 2>&1; then dpkg -i /workspace/hra/debs/*.deb >/dev/null; fi; "
    "mkdir -p /root/.ssh /run/sshd; "
    "install -m 600 /workspace/hra/ssh/ssh_host_ed25519_key /etc/ssh/ssh_host_ed25519_key; "
    "install -m 644 /workspace/hra/ssh/ssh_host_ed25519_key.pub /etc/ssh/ssh_host_ed25519_key.pub; "
    "install -m 600 /workspace/hra/ssh/authorized_keys /root/.ssh/authorized_keys; "
    "exec /usr/sbin/sshd -D -e -o HostKey=/etc/ssh/ssh_host_ed25519_key "
    "-o PasswordAuthentication=no -o KbdInteractiveAuthentication=no "
    "-o PermitRootLogin=prohibit-password"
)

KEY_REJECTED: Final = "RunPod rejected the API key; check RENDER_OFFLOAD_RUNPOD_API_KEY"
VOLUME_MISSING: Final = "the RunPod network volume was not found; check RENDER_OFFLOAD_RUNPOD_NETWORK_VOLUME_ID"
UNREACHABLE: Final = "RunPod could not be reached"
# Wordings seen for a create RunPod cannot place; any other refusal is reported with its status.
_NO_CAPACITY: Final = re.compile(
    r"no (longer any )?instances|not enough free|not available|unavailable", re.IGNORECASE
)


class RunPodError(Exception):
    """A RunPod call failed. `reason` is safe to show; `status` is the HTTP status, if any."""

    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


@dataclass(frozen=True, slots=True)
class PodInfo:
    id: str
    name: str
    status: str  # RUNNING, EXITED or TERMINATED
    public_ip: str | None
    ssh_port: int | None
    cost_per_hr: float | None
    gpu_type: str | None = None  # the type RunPod placed, once it says

    @property
    def reachable(self) -> bool:
        return bool(self.public_ip) and self.ssh_port is not None


@dataclass(frozen=True, slots=True)
class VolumeInfo:
    id: str
    data_center_id: str


def pod_body(*, gpu_types: Sequence[str], image: str, volume_id: str, data_center_id: str) -> dict[str, Any]:
    """The create request: constants and validated settings only. RunPod rents the first
    of `gpu_types` it can place, in this order (design decision 11)."""
    return {
        "name": POD_NAME,
        "gpuTypeIds": list(gpu_types),
        "gpuTypePriority": "custom",
        "gpuCount": 1,
        "cloudType": "SECURE",  # network volumes exist only in the Secure Cloud
        "networkVolumeId": volume_id,
        "volumeMountPath": VOLUME_MOUNT,
        "dataCenterIds": [data_center_id],
        "containerDiskInGb": CONTAINER_DISK_GB,
        "imageName": image,
        "ports": ["22/tcp"],
        "dockerStartCmd": ["bash", "-c", START_COMMAND],
    }


def _pod(raw: Any) -> PodInfo:
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
        raise RunPodError("RunPod returned a pod it could not describe")
    mappings = raw.get("portMappings")
    port = mappings.get("22") if isinstance(mappings, dict) else None
    cost = raw.get("costPerHr")
    address = raw.get("publicIp")
    gpu = raw.get("gpu") if isinstance(raw.get("gpu"), dict) else {}
    machine = raw.get("machine") if isinstance(raw.get("machine"), dict) else {}
    placed = gpu.get("id") or machine.get("gpuTypeId")
    return PodInfo(
        id=raw["id"],
        name=str(raw.get("name") or ""),
        status=str(raw.get("desiredStatus") or ""),
        public_ip=address if isinstance(address, str) and address else None,
        ssh_port=port if isinstance(port, int) and 1 <= port <= 65535 else None,
        cost_per_hr=float(cost) if isinstance(cost, int | float) and cost >= 0 else None,
        gpu_type=placed if isinstance(placed, str) and placed else None,
    )


class RunPodClient:
    def __init__(self, api_key: SecretStr, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._api_key = api_key
        self._transport = transport

    async def _request(
        self, method: str, path: str, *, params: dict[str, str] | None = None, body: dict | None = None
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        try:
            async with httpx.AsyncClient(
                base_url=RUNPOD_API,
                timeout=TIMEOUT_SECONDS,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = await client.request(method, path, params=params, json=body, headers=headers)
        except httpx.HTTPError as error:
            raise RunPodError(f"{UNREACHABLE} ({type(error).__name__})") from None
        if response.status_code == 401:
            raise RunPodError(KEY_REJECTED, status=401)
        return response

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            raise RunPodError("RunPod returned an answer that could not be read") from None

    async def get_network_volume(self, volume_id: str) -> VolumeInfo:
        response = await self._request("GET", f"/networkvolumes/{volume_id}")
        if response.status_code in (400, 404):
            raise RunPodError(VOLUME_MISSING, status=response.status_code)
        if response.status_code != 200:
            raise RunPodError(f"RunPod answered {response.status_code}", status=response.status_code)
        data = self._json(response)
        centre = data.get("dataCenterId") if isinstance(data, dict) else None
        if not isinstance(centre, str) or not centre:
            raise RunPodError("RunPod did not say which data centre holds the network volume")
        return VolumeInfo(id=volume_id, data_center_id=centre)

    async def create_pod(self, body: dict[str, Any], *, gpu_types: Sequence[str]) -> PodInfo:
        response = await self._request("POST", "/pods", body=body)
        if response.status_code in (200, 201):
            return _pod(self._json(response))
        if _NO_CAPACITY.search(response.text):
            wanted = list(gpu_types)
            reason = (
                f"no {wanted[0]} is free on RunPod right now"
                if len(wanted) == 1
                else f"none of {', '.join(wanted)} is free on RunPod right now"
            )
            raise RunPodError(reason, status=response.status_code)
        raise RunPodError(
            f"RunPod refused to create the render pod (answered {response.status_code})",
            status=response.status_code,
        )

    async def get_pod(self, pod_id: str) -> PodInfo | None:
        """The pod, or `None` when RunPod no longer knows it."""
        response = await self._request("GET", f"/pods/{pod_id}")
        if response.status_code in (400, 404):
            return None
        if response.status_code != 200:
            raise RunPodError(f"RunPod answered {response.status_code}", status=response.status_code)
        return _pod(self._json(response))

    async def delete_pod(self, pod_id: str) -> None:
        """Delete the pod; one RunPod no longer knows counts as deleted."""
        response = await self._request("DELETE", f"/pods/{pod_id}")
        if response.status_code in (200, 204, 404):
            return
        raise RunPodError(
            f"RunPod did not delete the render pod (answered {response.status_code})",
            status=response.status_code,
        )

    async def list_pods(self, name: str = POD_NAME) -> list[PodInfo]:
        """The account's pods carrying `name`, re-filtered here so no other pod is ever touched."""
        response = await self._request("GET", "/pods", params={"name": name})
        if response.status_code != 200:
            raise RunPodError(f"RunPod answered {response.status_code}", status=response.status_code)
        data = self._json(response)
        if not isinstance(data, list):
            raise RunPodError("RunPod returned a pod list it could not read")
        return [pod for pod in (_pod(item) for item in data) if pod.name == name]
