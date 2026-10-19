## ADDED Requirements

### Requirement: An estimate can be read without starting a render
The service SHALL offer an owner-gated read of a render's estimate for a built room version, given a kind and a tier. It SHALL validate the tier, the kind and the stored benchmark exactly as a render request does, and SHALL return the estimate in human terms with the tier. It SHALL NOT start a process, mark anything queued, issue an approval token or a ticket, or record a run. The same refusals as for a render request SHALL apply: a raw frame or resolution value, an unknown tier, a missing benchmark, or a version that is not built. A render started afterwards SHALL still pass the guard on its own.

#### Scenario: Draft estimate read
- **WHEN** the benchmark is 2.5 seconds per megapixel and the estimate of a `draft` turntable of room `Hall` v3 is read
- **THEN** about 19 seconds is returned with the tier `draft`, and no render is queued

#### Scenario: Estimate without a benchmark
- **WHEN** no benchmark is stored and an estimate is read
- **THEN** it is refused stating that the benchmark must be run first

#### Scenario: Raw values refused
- **WHEN** an estimate is read with a frame count instead of a tier
- **THEN** it is refused and nothing is computed
