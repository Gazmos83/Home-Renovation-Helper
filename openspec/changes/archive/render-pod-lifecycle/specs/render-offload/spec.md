## MODIFIED Requirements

### Requirement: The render server is configured from settings and off by default
The service SHALL support two offload modes:
- **Fixed host:** configured only when host, user, private key file, known-hosts file and remote Blender path are all set.
- **RunPod pod:** configured only when a RunPod API key, a network volume id, one or more GPU types in priority order (at most five) and a container image are set, together with user, private key file, known-hosts file and remote Blender path. No host or port is set in this mode; they come from the running pod.

Setting both a host and the RunPod values SHALL fail startup, naming the conflict. Port defaults to 22 and Cycles device to `OPTIX`. With neither mode complete, offload SHALL be off and every render SHALL run locally as before. The key file and the known-hosts file SHALL exist and be readable at startup, otherwise startup SHALL fail naming the setting. The device SHALL be one of `OPTIX`, `CUDA` or `HIP`. No password SHALL be accepted. No secret, API key or key content SHALL appear in logs, traces, prompts, tool output or any response.

#### Scenario: Not configured
- **WHEN** the host is set but the key file is not
- **THEN** offload is off, the startup summary says so, and a `final` render runs locally

#### Scenario: Key file missing
- **WHEN** all values are set and the key file does not exist
- **THEN** startup fails naming the key-file setting

#### Scenario: Pod mode configured
- **WHEN** the RunPod API key, network volume id, GPU types, image, user, key file, known-hosts file and Blender path are set and no host is set
- **THEN** offload is on in pod mode, and the startup summary names the mode and the GPU types in order but not the key

#### Scenario: Both modes set
- **WHEN** a host and a RunPod API key are both set
- **THEN** startup fails saying only one offload mode may be configured

### Requirement: The server is checked before approval and there is no fallback
Before a remote `final` is quoted, the service SHALL check within ten seconds that the server can be used:
- **Fixed host, or pod mode with a pod running:** the server SHALL answer over SSH with the pinned host key, and its Blender SHALL report version 5.2.1.
- **Pod mode with no pod running:** the RunPod API SHALL accept the key and report the configured network volume. No pod SHALL be created, and nothing billable SHALL start, before approval.

When the check fails, the request SHALL be refused before any approval, with a reason saying the render server is unreachable, runs another Blender version, or that RunPod or its volume is unavailable. The reason SHALL suggest a fix or switching finals to the laptop. It SHALL NOT run the render locally instead. A remote job that fails after approval SHALL be recorded as failed with its reason and SHALL NOT be retried locally. This includes a pod that cannot be created or does not answer in time.

#### Scenario: Server off
- **WHEN** the mode is fixed host, the target is `remote`, the server does not answer, and a `final` turntable is requested
- **THEN** the request is refused saying the render server is unreachable, no approval is asked, and nothing runs locally

#### Scenario: Wrong Blender
- **WHEN** the server's Blender reports 4.5
- **THEN** the request is refused naming the version mismatch

#### Scenario: Host key changed
- **WHEN** the server presents a host key not in the known-hosts file
- **THEN** the check fails as unreachable and no file is uploaded

#### Scenario: Pod mode, nothing running
- **WHEN** the mode is pod, no pod is running, RunPod accepts the key and reports the volume, and a `final` turntable is requested
- **THEN** the quote is shown for approval and no pod has been created

#### Scenario: RunPod rejects the key
- **WHEN** the mode is pod, no pod is running, and RunPod answers 401
- **THEN** the request is refused saying RunPod rejected the API key, without showing the key, and no approval is asked

### Requirement: Remote estimates come from a remote benchmark
A remote `final` estimate SHALL be `frames × megapixels × remote seconds-per-megapixel + remote transfer overhead`, from a stored remote benchmark. In pod mode with no pod running, the estimate SHALL also add the pod start-up time: the last measured time from creation until SSH answered, or 180 seconds before any measurement. Without a remote benchmark, a remote `final` SHALL be refused saying the remote benchmark must be run first. The remote benchmark SHALL render one Cycles frame at one megapixel on the server only when the developer explicitly requests it. It SHALL pass through the render guard, and SHALL store the seconds per megapixel, the transfer overhead and when it was measured. The first approved remote `final` SHALL recalibrate the seconds per megapixel from its actual render time, excluding start-up. The homeowner SHALL see the estimate as time on the render server, never a host name or a cost.

#### Scenario: Remote estimate
- **WHEN** the remote benchmark is 0.2 seconds per megapixel with 40 seconds of overhead and a `final` turntable is requested remotely with a server already answering
- **THEN** the estimate is 36 × 2.25 × 0.2 + 40 (about 56 seconds), worded as on the render server

#### Scenario: Estimate with start-up
- **WHEN** the same benchmark is stored, the mode is pod, no pod is running, and the last start-up took 150 seconds
- **THEN** the estimate is about 206 seconds, worded as on the render server

#### Scenario: No remote benchmark
- **WHEN** offload is configured, the target is `remote` and no remote benchmark is stored
- **THEN** a `final` request is refused saying the remote benchmark must be run first

## ADDED Requirements

### Requirement: In pod mode a pod is created on demand
In pod mode, an approved remote render (a `final` or the remote benchmark) SHALL use the running pod when there is one. Otherwise it SHALL create one pod of the first configured GPU type that RunPod can place, trying them in the configured order, with the configured image, with the network volume attached and only SSH exposed, under a fixed app-owned name. It SHALL then wait until the pod reports a public address and SSH port and answers SSH with the pinned host key. If RunPod has not given the pod an address and SSH port within 3 minutes of its creation, the start SHALL fail saying RunPod did not start the pod, and the pod SHALL be deleted. The whole wait SHALL be bounded by a start-up limit of 10 minutes. After that, it SHALL check Blender 5.2.1 and run the remote job as in fixed-host mode. At most one pod SHALL exist at a time. Each pod session SHALL record the GPU type the pod actually got. A pod that cannot be created, for example because none of the configured GPU types is free in the volume's data centre, or that does not answer within the limit, SHALL fail the job with that reason and SHALL be deleted. The measured start-up time SHALL be stored.

#### Scenario: First final of a session
- **WHEN** no pod is running and the owner approves a remote `final` turntable
- **THEN** one pod is created with the network volume, the render runs on it once SSH answers, and the start-up time is stored

#### Scenario: Second final reuses the pod
- **WHEN** a pod is running from a final three minutes ago and a second final is approved
- **THEN** no new pod is created and the render runs on the running pod

#### Scenario: No GPU free
- **WHEN** RunPod refuses to create the pod because none of the configured GPU types is available
- **THEN** the job fails naming the GPU types and saying none is free on RunPod right now, nothing runs locally, and no pod is left

#### Scenario: First choice sold out
- **WHEN** the GPU types are RTX A4500 then RTX 5090, no RTX A4500 is free and an RTX 5090 is
- **THEN** the pod is created with an RTX 5090, and its session records the RTX 5090

#### Scenario: RunPod never starts the pod
- **WHEN** the pod is created but RunPod gives it no address or SSH port for 3 minutes
- **THEN** the job fails saying RunPod did not start the render pod, the pod is deleted, and its session records `start_failed` after about 3 minutes, not 10

#### Scenario: Pod never answers
- **WHEN** the pod is created but SSH does not answer within 10 minutes
- **THEN** the job fails stating the start-up timeout and the pod is deleted

### Requirement: An idle pod is deleted
In pod mode, the service SHALL delete the pod once the idle time has passed since the last remote job ended. The default idle time is 10 minutes. A job that starts during the idle time SHALL cancel the deletion, and its end SHALL start a new idle time. The pod SHALL NOT be deleted while a remote job is running. After a delete, the service SHALL confirm through the RunPod API that the pod is gone. A failed delete SHALL be retried every minute and reported on the developer panel until it succeeds. Each pod session SHALL be recorded with its creation and deletion times, RunPod's reported hourly price, its jobs and its outcome.

#### Scenario: Idle deletion
- **WHEN** a remote final ends at 14:00 and no other remote job starts
- **THEN** the pod is deleted at 14:10 and its session records a lifetime ending at 14:10

#### Scenario: Job during idle time
- **WHEN** a remote final ends at 14:00 and another starts at 14:06 and ends at 14:12
- **THEN** the pod is not deleted at 14:10 and is deleted at 14:22

#### Scenario: Delete fails
- **WHEN** the RunPod API returns an error to the delete
- **THEN** the delete is retried a minute later and the developer panel shows the pod as still running with the error

### Requirement: A pod never outlives the app
At startup in pod mode, the service SHALL list the account's pods and delete any that carry the app-owned name, recording them as orphaned. On a normal shutdown it SHALL delete its running pod, waiting at most 30 seconds. Pods without the app-owned name SHALL NOT be touched.

#### Scenario: Restart after a crash
- **WHEN** the app starts and RunPod lists one app-named pod and one other pod
- **THEN** the app-named pod is deleted and recorded as orphaned, and the other pod is left alone

#### Scenario: Shutdown with a pod running
- **WHEN** the app shuts down normally while a pod is idle
- **THEN** the pod is deleted before the process exits
