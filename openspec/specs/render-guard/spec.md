## Purpose

Defines the gate every Blender render passes through: tiers fixed by configuration, a required tier with no raw knobs, an estimate from a benchmarked first frame shown before every run, explicit approval for the expensive tier, a record of what was estimated and what it cost, and one Blender process at a time.

## Requirements

### Requirement: Render tiers come from configuration
The service SHALL read exactly three render tiers from its render configuration — `draft`, `preview` and `final` — each fixing a frame count, a square resolution and an engine, and SHALL refuse to start when a tier is missing, duplicated, carries an unknown key, or names an engine the pinned Blender does not offer. The shipped values are `draft` 12 frames at 600 × 600 on Eevee, `preview` 24 frames at 1000 × 1000 on Eevee, and `final` 36 frames at 1500 × 1500 on Cycles.

#### Scenario: The shipped tiers load
- **WHEN** the service starts with the shipped render configuration
- **THEN** the three tiers are available with the frame counts, resolutions and engines above, and the startup summary lists them

#### Scenario: A tier is missing
- **WHEN** the render configuration omits `preview`
- **THEN** startup fails with an error naming `preview`

#### Scenario: An unknown tier is requested
- **WHEN** a render is requested with tier `ultra`
- **THEN** the request is refused naming `ultra` and listing the three tiers

### Requirement: The tier is required and raw values are refused
Every request to render SHALL carry a tier and nothing that would set a frame count, resolution or engine directly. A request that omits the tier, or that names `frames`, `resolution`, `width`, `height`, `samples` or `engine`, SHALL be refused by the name of the offending field before any Blender process starts.

#### Scenario: No tier
- **WHEN** a render is requested without a tier
- **THEN** the request is refused stating that a tier is required

#### Scenario: Raw frame count alongside a tier
- **WHEN** a render is requested with tier `draft` and `frames: 100`
- **THEN** the request is refused naming `frames`, and no process is started

#### Scenario: Engine override
- **WHEN** a render is requested with tier `draft` and `engine: CYCLES`
- **THEN** the request is refused naming `engine`

### Requirement: An estimate is shown before every run
Before any guarded render runs, the service SHALL compute `seconds ≈ frames × megapixels × engine_multiplier × benchmark_seconds_per_megapixel` from the tier and the stored benchmark, and SHALL report it in human terms (seconds under a minute, otherwise minutes, rounded) together with the tier, frame count and resolution. Without a stored benchmark the render SHALL be refused with a message saying the benchmark must be run first.

#### Scenario: Draft estimate
- **WHEN** the benchmark is 2.5 seconds per megapixel and a `draft` turntable is requested
- **THEN** the reported estimate is derived from 12 × 0.36 × 1 × 2.5 (about 11 seconds) and the run proceeds

#### Scenario: Final estimate uses the Cycles multiplier
- **WHEN** the benchmark is 2.5 seconds per megapixel, the Cycles multiplier is 30, and a `final` turntable is requested
- **THEN** the reported estimate is derived from 36 × 2.25 × 30 × 2.5 (about 101 minutes)

#### Scenario: No benchmark yet
- **WHEN** no benchmark has been stored and a `draft` render is requested
- **THEN** the request is refused stating that the benchmark must be run first, and no process is started

### Requirement: A first-launch benchmark calibrates the estimate
The service SHALL provide a benchmark that renders one Eevee frame of a reference package at one megapixel, measures the elapsed seconds, and stores the result as the benchmark seconds-per-megapixel together with when it was measured. The benchmark SHALL run only on an explicit request from the owner (never automatically at startup), SHALL be re-runnable, and SHALL replace the previous value when re-run. The Cycles multiplier SHALL default to 30 and SHALL be recalculated from the actual duration of the first approved `final` render.

#### Scenario: First benchmark
- **WHEN** the owner requests the benchmark and the frame renders in 2.4 seconds
- **THEN** the stored benchmark is 2.4 seconds per megapixel with a timestamp, and the frame image is kept under the render root's `benchmark` folder

#### Scenario: Startup does not benchmark
- **WHEN** the service starts with no benchmark stored
- **THEN** no Blender process runs and the startup summary reports the benchmark as missing

#### Scenario: Cycles multiplier calibrated by the first final
- **WHEN** the Cycles multiplier is the default and a `final` render completes with an actual duration
- **THEN** the multiplier is replaced by the actual seconds divided by (frames × megapixels × benchmark seconds-per-megapixel), and later `final` estimates use it

### Requirement: The final tier requires explicit approval
A `final` render SHALL NOT start until the owner approves it after seeing the estimate. Inside an agent graph the guard SHALL pause the run (an interrupt) carrying the estimate; over HTTP the first request SHALL answer with "approval required", the estimate and an approval token, and a second request carrying that token and the literal word `yes` SHALL start the run. Any other answer, a missing token, an unknown token or a token for a different package SHALL be refused, and a token SHALL be usable once.

#### Scenario: Final over HTTP, approved
- **WHEN** the owner requests a `final` turntable and then approves with the returned token and `yes`
- **THEN** the first response carries the estimate and the token and starts nothing, and the second response starts the run

#### Scenario: Final over HTTP, declined
- **WHEN** the owner answers the approval request with `no`
- **THEN** the run is refused, the token is discarded, and no process is started

#### Scenario: Final inside a graph
- **WHEN** a graph node calls the guard with tier `final`
- **THEN** the run interrupts with the estimate before any process starts, and resumes only on `yes`

#### Scenario: Draft and preview need no approval
- **WHEN** a `draft` or `preview` render is requested
- **THEN** the run starts after the estimate is reported, with no approval step

### Requirement: Tier, estimate and actual are recorded
For every guarded render the service SHALL emit a structured log record at start carrying the package, version, kind, tier, frame count, resolution, engine and estimated seconds, and one at finish carrying the actual seconds and outcome. When tracing is configured the same values SHALL be recorded as an event in the trace; a tracing failure SHALL never affect the render.

#### Scenario: A draft completes
- **WHEN** a `draft` turntable finishes
- **THEN** the finish record names the package, version, tier `draft`, the estimated and actual seconds and outcome `succeeded`

#### Scenario: Tracing off
- **WHEN** tracing is not configured and a render runs
- **THEN** the structured records are emitted and nothing is sent anywhere else

### Requirement: One Blender process at a time
The service SHALL run at most one Blender process at a time across builds, benchmarks and renders. A second request SHALL be accepted and queued, and its recorded status SHALL show it waiting until the first completes.

#### Scenario: Two renders requested back to back
- **WHEN** two `draft` renders are requested within the same second
- **THEN** both are accepted, their processes never overlap, and the second's status reads `queued` until the first finishes

### Requirement: No render without the guard
A Blender process that renders an Eevee or Cycles frame SHALL only ever be launched with an authorisation the guard issued for that request. The launcher SHALL refuse to start such a process without one, and this refusal SHALL be covered by a test. Package builds and Workbench progress screenshots are not renders in this sense and need no tier.

#### Scenario: Launcher called without authorisation
- **WHEN** code attempts to launch a render process without a guard-issued authorisation
- **THEN** the launch is refused and no process starts

#### Scenario: Authorisation is single-use
- **WHEN** an authorisation that already ran is presented again
- **THEN** the launch is refused

### Requirement: A render names its source and a detail render is final only
Every render request SHALL render either the version's built model or its detail-pass copy; the built model is the default. A request for the detail copy SHALL be refused unless:
- the tier is `final`; otherwise the refusal says a detail render is final only and progress is checked with a screenshot;
- the detail copy exists;
- the render is of the piece alone, not placed in a room.

A guard authorisation SHALL match the source it was issued for. An authorisation for the built model SHALL NOT launch a render of the detail copy, nor the reverse. A detail render SHALL follow the same estimate, approval, record and one-process rules as any `final` render.

#### Scenario: Draft detail render refused
- **WHEN** a detail render is requested at tier `draft`
- **THEN** it is refused saying a detail render is final only, and no process starts

#### Scenario: Final detail render approved
- **WHEN** a detail turntable is requested at tier `final` and the owner answers `yes` to the estimate
- **THEN** one render of `detail/detail.blend` runs with 36 frames at 1500 × 1500 on Cycles

#### Scenario: Ticket for the wrong source
- **WHEN** an authorisation issued for the built model is presented to launch a detail render of the same version
- **THEN** the launch is refused and no process starts
