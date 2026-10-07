## MODIFIED Requirements

### Requirement: One Blender process at a time
The service SHALL run at most one Blender process at a time on the laptop, across builds, benchmarks, local renders and live-socket commands. It SHALL also run at most one remote render job at a time on the render server. The two machines are independent: a local process may run while a remote job runs. A second request for the same machine SHALL be accepted and queued, and its recorded status SHALL show it waiting until the first completes.

#### Scenario: Two renders requested back to back
- **WHEN** two `draft` renders are requested within the same second
- **THEN** both are accepted, their processes never overlap, and the second's status reads `queued` until the first finishes

#### Scenario: Local draft during a remote final
- **WHEN** a remote `final` turntable is running and the owner requests a `draft` still of another piece
- **THEN** the draft runs on the laptop without waiting for the remote job

#### Scenario: Two remote finals
- **WHEN** a second remote `final` is approved while one is running
- **THEN** it is queued until the first remote job finishes

### Requirement: Tier, estimate and actual are recorded
For every guarded render the service SHALL emit a structured log record at start, carrying the package, version, kind, tier, frame count, resolution, engine, target (`local` or `remote`) and estimated seconds. It SHALL emit one at finish carrying the actual seconds and outcome, and for a remote job the transfer seconds. When tracing is configured, the same values SHALL be recorded as an event in the trace. A tracing failure SHALL never affect the render.

#### Scenario: A draft completes
- **WHEN** a `draft` turntable finishes
- **THEN** the finish record names the package, version, tier `draft`, target `local`, the estimated and actual seconds and outcome `succeeded`

#### Scenario: Tracing off
- **WHEN** tracing is not configured and a render runs
- **THEN** the structured records are emitted and nothing is sent anywhere else

#### Scenario: A remote final completes
- **WHEN** an approved remote `final` turntable finishes
- **THEN** the finish record names target `remote` with the actual and transfer seconds
