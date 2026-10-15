## MODIFIED Requirements

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

### Requirement: A render names its source and a detail render is final only
Every render request SHALL render the version's built model, its detail-pass copy, or a restyle of the built model; the built model is the default. A request for the detail copy SHALL be refused unless:
- the tier is `final`; otherwise the refusal says a detail render is final only and progress is checked with a screenshot;
- the detail copy exists;
- the render is of the piece alone, not placed in a room;
- it is a still, or it runs on the render server. A detail turntable that would run on the laptop SHALL be refused, saying that on the laptop a detail render is a still and that a detail turntable runs only on the render server.

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
- **THEN** it is refused before any approval, saying that on the laptop a detail render is a still and a detail turntable runs only on the render server, and no process starts

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

## ADDED Requirements

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
