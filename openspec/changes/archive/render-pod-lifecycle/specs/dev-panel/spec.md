## MODIFIED Requirements

### Requirement: Render offload is managed from the developer panel
Behind the developer gate, the developer SHALL be able to:
- read whether offload is configured and in which mode. Fixed host shows host, port, user, remote Blender path and device. Pod mode shows the GPU types in priority order, image, network volume id, user, remote Blender path and device. Key file contents, known-hosts contents and the RunPod API key SHALL never be shown;
- test the connection. Fixed host, or a running pod, reports reachability, the remote Blender version and the GPU devices it lists. Pod mode with no pod running reports whether RunPod accepts the key and finds the network volume, and SHALL NOT create a pod;
- run the remote benchmark through the render guard, which in pod mode may create a pod;
- set the final target to `local` or `remote`;
- set an hourly rate in euros;
- in pod mode, read the pod's state: none, starting, running with the time it will be deleted, or a failed delete with its error;
- in pod mode, delete the running pod now. This SHALL be refused while a remote job is running;
- in pod mode, set the idle minutes, a whole number from 1 to 120, defaulting to 10;
- read the last twenty remote jobs with estimate, actual, transfer seconds, outcome and the euro estimate from the hourly rate;
- in pod mode, read the last twenty pod sessions with creation and deletion times, lifetime, jobs, outcome, and cost from RunPod's reported hourly price.

Setting the target to `remote` SHALL be refused while offload is not configured. A change SHALL apply to the next render without a restart.

#### Scenario: Remote target without configuration
- **WHEN** offload is not configured and the developer sets the final target to `remote`
- **THEN** the change is refused saying offload is not configured, and the target stays `local`

#### Scenario: Connection test
- **WHEN** the developer tests a reachable server running Blender 5.2.1 with one GPU
- **THEN** the response reports reachable, version 5.2.1 and the GPU's device name

#### Scenario: Connection test in pod mode with nothing running
- **WHEN** the mode is pod, no pod is running and the developer tests the connection
- **THEN** the response reports that RunPod accepts the key and the volume exists, and no pod is created

#### Scenario: Delete pod now
- **WHEN** a pod is idle and the developer chooses "Delete pod now"
- **THEN** the pod is deleted, its session is closed, and the state shows none

#### Scenario: Delete refused during a job
- **WHEN** a remote final is rendering and the developer chooses "Delete pod now"
- **THEN** the request is refused saying a render is running on the pod

#### Scenario: Idle minutes out of range
- **WHEN** the developer sets the idle minutes to 0
- **THEN** the change is refused and the idle minutes stay unchanged
