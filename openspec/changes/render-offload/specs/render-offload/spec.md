## Purpose

Defines how a `final` render can run on the owner's rented GPU server over SSH instead of the laptop: how the server is configured and checked, how a remote job moves files and publishes like a local one, how it is estimated, and that it never falls back silently.

## ADDED Requirements

### Requirement: The render server is configured from settings and off by default
The service SHALL treat the render server as configured only when all of these are set: host, user, private key file, known-hosts file and remote Blender path. Port defaults to 22 and Cycles device to `OPTIX`. With any of them missing, offload SHALL be off and every render SHALL run locally as before. The key file and the known-hosts file SHALL exist and be readable at startup, otherwise startup SHALL fail naming the setting. The device SHALL be one of `OPTIX`, `CUDA` or `HIP`. No password SHALL be accepted, and no secret or key content SHALL appear in logs, traces, prompts, tool output or any response.

#### Scenario: Not configured
- **WHEN** the host is set but the key file is not
- **THEN** offload is off, the startup summary says so, and a `final` render runs locally

#### Scenario: Key file missing
- **WHEN** all values are set and the key file does not exist
- **THEN** startup fails naming the key-file setting

### Requirement: Only finals offload, and only when chosen
Only `final` renders SHALL run remotely, and only when offload is configured and the developer has set the final target to `remote`. The default target SHALL be `local`. Draft and preview renders, builds, screenshots and the local benchmark SHALL always run locally.

#### Scenario: Draft with target remote
- **WHEN** the target is `remote` and a `draft` turntable is requested
- **THEN** it runs on the laptop

#### Scenario: Final with target remote
- **WHEN** the target is `remote` and the owner approves a `final` turntable
- **THEN** it runs on the render server

### Requirement: The server is checked before approval and there is no fallback
Before a remote `final` is quoted, the service SHALL check within ten seconds that the server answers over SSH with the pinned host key and that its Blender reports version 5.2.1. When the check fails, the request SHALL be refused before any approval, with a reason saying the render server is unreachable or runs another Blender version, and suggesting the owner start it or switch finals to the laptop. It SHALL NOT run the render locally instead. A remote job that fails after approval SHALL be recorded as failed with its reason and SHALL NOT be retried locally.

#### Scenario: Server off
- **WHEN** the target is `remote`, the server does not answer, and a `final` turntable is requested
- **THEN** the request is refused saying the render server is unreachable, no approval is asked, and nothing runs locally

#### Scenario: Wrong Blender
- **WHEN** the server's Blender reports 4.5
- **THEN** the request is refused naming the version mismatch

#### Scenario: Host key changed
- **WHEN** the server presents a host key not in the known-hosts file
- **THEN** the check fails as unreachable and no file is uploaded

### Requirement: A remote job publishes exactly like a local one
An approved remote render SHALL:
1. upload the version's blend file (and, for a room render, the room document), together with the fixed generator files, to a new per-job folder on the server;
2. run the same generator with the ticket's frames, resolution and Cycles engine and the configured GPU device, bounded by the tier's timeout;
3. copy the output back into the local staging folder;
4. verify and publish it with the same checks and atomic rename as a local render.

The per-job folder on the server SHALL be removed after success, failure or timeout. No agent-written code SHALL be sent to the server, and no input SHALL reach a remote command except values produced by code.

#### Scenario: Final turntable on the server
- **WHEN** an approved `final` turntable runs remotely and completes
- **THEN** the version's `frames/` holds exactly 36 frames at 1500 × 1500, `viewer.html` names 36 frames, and the server's job folder is gone

#### Scenario: Missing frame after transfer
- **WHEN** the copied-back output lacks `frame_020.png`
- **THEN** the job fails naming `frame_020.png`, nothing is published, and the server's job folder is removed

#### Scenario: Timeout
- **WHEN** the remote run exceeds the tier's timeout
- **THEN** the remote process is stopped, the job fails stating the timeout, and the server's job folder is removed

### Requirement: Remote estimates come from a remote benchmark
A remote `final` estimate SHALL be `frames × megapixels × remote seconds-per-megapixel + remote transfer overhead`, from a stored remote benchmark. Without a remote benchmark, a remote `final` SHALL be refused saying the remote benchmark must be run first. The remote benchmark SHALL render one Cycles frame at one megapixel on the server only when the developer explicitly requests it. It SHALL pass through the render guard, and SHALL store the seconds per megapixel, the transfer overhead and when it was measured. The first approved remote `final` SHALL recalibrate the seconds per megapixel from its actual render time. The homeowner SHALL see the estimate as time on the render server, never a host name or a cost.

#### Scenario: Remote estimate
- **WHEN** the remote benchmark is 0.2 seconds per megapixel with 40 seconds of overhead and a `final` turntable is requested remotely
- **THEN** the estimate is 36 × 2.25 × 0.2 + 40 (about 56 seconds), worded as on the render server

#### Scenario: No remote benchmark
- **WHEN** offload is configured, the target is `remote` and no remote benchmark is stored
- **THEN** a `final` request is refused saying the remote benchmark must be run first
