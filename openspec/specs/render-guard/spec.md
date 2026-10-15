## Purpose

Defines the gate every Blender render passes through: tiers fixed by configuration, a required tier with no raw knobs, an estimate from a benchmarked first frame shown before every run, explicit approval for the expensive tier, a record of what was estimated and what it cost, and one Blender process at a time.

## Requirements

### Requirement: Render tiers come from configuration
The service SHALL read exactly two render tiers from its render configuration, `draft` and `final`. Each tier fixes a frame count, a square resolution and an engine. The service SHALL refuse to start when a tier is missing, duplicated, carries an unknown key, or names an engine the pinned Blender does not offer. A configuration that still names `preview`, or any other tier, SHALL be refused as an unknown tier. The shipped values are `draft` 12 frames at 800 × 800 on Eevee and `final` 36 frames at 1500 × 1500 on Cycles.

#### Scenario: The shipped tiers load
- **WHEN** the service starts with the shipped render configuration
- **THEN** the two tiers are available with the frame counts, resolutions and engines above, and the startup summary lists them

#### Scenario: A tier is missing
- **WHEN** the render configuration omits `final`
- **THEN** startup fails with an error naming `final`

#### Scenario: Preview left in the configuration
- **WHEN** the render configuration still defines `preview`
- **THEN** startup fails naming `preview` as an unknown tier and listing `draft` and `final`

#### Scenario: An unknown tier is requested
- **WHEN** a render is requested with tier `ultra`
- **THEN** the request is refused naming `ultra` and listing the two tiers

#### Scenario: Preview requested
- **WHEN** a render is requested with tier `preview`
- **THEN** the request is refused naming `preview` and listing `draft` and `final`, and no process starts

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
- **THEN** the reported estimate is derived from 12 × 0.64 × 1 × 2.5 (about 19 seconds) and the run proceeds

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
- **WHEN** a `draft` render is requested, and later a render at the removed tier `preview`
- **THEN** the draft starts after the estimate is reported, with no approval step, and the `preview` request is refused as an unknown tier

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

### Requirement: No render without the guard
A Blender process that renders an Eevee or Cycles frame SHALL only ever be launched with an authorisation the guard issued for that request. The launcher SHALL refuse to start such a process without one, and this refusal SHALL be covered by a test. Package builds and Workbench progress screenshots are not renders in this sense and need no tier.

#### Scenario: Launcher called without authorisation
- **WHEN** code attempts to launch a render process without a guard-issued authorisation
- **THEN** the launch is refused and no process starts

#### Scenario: Authorisation is single-use
- **WHEN** an authorisation that already ran is presented again
- **THEN** the launch is refused

### Requirement: A render names its source and a detail render is final only
Every render request SHALL render the version's built model, its detail-pass copy, or a restyle of the built model; the built model is the default. A request for the detail copy SHALL be refused unless:
- the tier is `final`; otherwise the refusal says a detail render is final only and progress is checked with a screenshot;
- the detail copy exists;
- the render is of the piece alone, not placed in a room.

A detail still or turntable MAY run on the laptop or on the render server, wherever finals run. A detail render SHALL be a still unless a turntable is asked for.

A request for a restyle SHALL be refused at tier `final`, saying a restyle is a concept picture. It SHALL be refused when it is not a turntable, saying a restyle is a draft turntable. It SHALL name the one variant it is for.

A guard authorisation SHALL match the source it was issued for. An authorisation for the built model SHALL NOT launch a render of the detail copy or a restyle, nor the reverse, and a restyle authorisation SHALL NOT launch any variant but the one it was issued for. A detail render SHALL follow the same estimate, approval, record and one-process rules as any `final` render. A restyle SHALL follow the same estimate, record and one-process rules as any `draft` render.

#### Scenario: Draft detail render refused
- **WHEN** a detail render is requested at tier `draft`
- **THEN** it is refused saying a detail render is final only, and no process starts

#### Scenario: Final detail render approved
- **WHEN** finals run on the laptop, a detail still is requested at tier `final` and the owner answers `yes` to the estimate
- **THEN** one render of `detail/detail.blend` runs on the laptop: one frame at 1500 × 1500 on Cycles

#### Scenario: Local detail turntable refused
- **WHEN** finals run on the laptop and a detail turntable is requested at tier `final`
- **THEN** it is not refused: the approval shows the estimate with the long-render and laptop-busy warnings, nothing starts before `yes`, and on `yes` one render of `detail/detail.blend` runs on the laptop with 36 frames at 1500 × 1500 on Cycles

#### Scenario: Detail turntable on the render server
- **WHEN** finals go to the render server, a detail turntable is requested at tier `final` and the owner answers `yes` to the estimate
- **THEN** one render of `detail/detail.blend` runs on the render server with 36 frames at 1500 × 1500 on Cycles

#### Scenario: Ticket for the wrong source
- **WHEN** an authorisation issued for the built model is presented to launch a detail render of the same version
- **THEN** the launch is refused and no process starts

#### Scenario: Restyle at final refused
- **WHEN** a restyle is requested at tier `final`
- **THEN** it is refused saying a restyle is a concept picture, and no process starts

#### Scenario: Restyle still refused
- **WHEN** a restyle still is requested at tier `draft`
- **THEN** it is refused saying a restyle is a draft turntable, and no process starts

#### Scenario: Ticket for a restyle used for another variant
- **WHEN** an authorisation issued for the variant `walnut` is presented to launch `sage-green`
- **THEN** the launch is refused and no process starts

### Requirement: Renders recorded at the removed preview tier read as draft
Renders, render runs and render notices recorded before `preview` was removed SHALL be relabelled `draft` when the service is upgraded: stored records by the database upgrade, render files by the first start after it. That covers the tier stored for each render run, each thread notice and its wording, and the tier recorded in each version's and each variant's render files. After the upgrade, no stored render SHALL name `preview`. Variant folder names SHALL stay as they are. Running the relabel again SHALL change nothing.

#### Scenario: Old run relabelled
- **WHEN** the database holds a render run at tier `preview` and is upgraded
- **THEN** that run reads tier `draft`, and its rating and comment are unchanged

#### Scenario: Old notice relabelled
- **WHEN** a thread holds the notice "The preview turntable of hall-bench version 2 is ready." and the database is upgraded
- **THEN** the notice reads tier `draft` with the text "The draft turntable of hall-bench version 2 is ready.", and its Review button reads "Review draft revision 2"

#### Scenario: Render files relabelled
- **WHEN** a version's render record and a variant's `scene.json` name tier `preview` and the upgraded service starts
- **THEN** both name tier `draft`, the variant keeps its folder name, and no image is changed

#### Scenario: Upgrade run twice
- **WHEN** the relabel has run and runs again
- **THEN** nothing changes

### Requirement: A long render is approved with its time and the laptop's wait
When a render that needs approval is quoted above 20 minutes, its approval SHALL carry a long-render warning, wherever the approval is asked: in a conversation, at a graph interrupt, or over HTTP. The warning SHALL state:
- the estimate in hours and minutes;
- that the estimate is rough until the first `final` calibrates the Cycles multiplier;
- that heavy lighting can make it longer.

For a detail turntable, the warning SHALL also say that a single detail still (with its estimate) is much faster, and so is the render server when one is configured. When the render would run on the laptop, the approval SHALL also say that it holds the laptop's one Blender process for that time, so builds, drafts and the live detail pass wait behind it. A render quoted at 20 minutes or less SHALL be approved as before, without these warnings.

#### Scenario: Local detail turntable warned
- **WHEN** the benchmark is 5.031 seconds per megapixel, the Cycles multiplier is 30, finals run on the laptop and a detail turntable is requested
- **THEN** the approval states about 3 h 24 min, that it is rough until the first final calibrates it and lighting can make it longer, that a detail still takes about 6 minutes, and that builds, drafts and the live detail pass wait behind it

#### Scenario: Short final not warned
- **WHEN** a `final` still is quoted at 6 minutes
- **THEN** its approval shows the estimate with no long-render or laptop-busy warning

#### Scenario: Remote long render
- **WHEN** a `final` turntable quoted above 20 minutes is asked to run on the render server
- **THEN** its approval carries the long-render warning and no laptop-busy warning

### Requirement: A final runs for up to six hours
A `final` render SHALL be stopped when it runs longer than 36 times the Blender timeout (6 hours at the 600-second default), on the laptop and on the render server, and SHALL fail stating the timeout. A `draft` keeps its own limit.

#### Scenario: Shipped final limit
- **WHEN** the service starts with the shipped render configuration and the default Blender timeout
- **THEN** a `final` render is allowed 21 600 seconds before it is stopped
