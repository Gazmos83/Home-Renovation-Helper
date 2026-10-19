## ADDED Requirements

### Requirement: Engineering ingestion runs as an unattended background job
Starting authorised ingestion from the Engineering Knowledge view or the command line SHALL start a background job and return at once with its run. The job SHALL keep running after the browser or terminal is closed and when the backend restarts. At most one ingestion job SHALL run at a time. A start SHALL be refused, with a stated reason, while another ingestion job runs or a headless render holds the render semaphore. While it runs, the job SHALL ask the operating system not to sleep or idle-suspend the laptop, and SHALL release that request when it ends, fails or is interrupted. The lid switch SHALL NOT be overridden. The view SHALL show the job's state, passages embedded out of the total, an estimated time left from the measured rate, and whether the laptop is being kept awake. A job whose progress heartbeat stops for longer than a fixed limit SHALL be shown as interrupted, with an action to resume it. Starting a job SHALL NOT grant, extend or skip any rights or review decision.

#### Scenario: Owner leaves a run overnight
- **WHEN** the owner starts ingestion of the Wood Handbook and closes the browser
- **THEN** the job continues, and the next morning the view shows it published with its block count, start and finish times

#### Scenario: Progress while running
- **WHEN** the owner opens the view during a run
- **THEN** it shows passages embedded out of the total and an estimated time left, updating without a page reload

#### Scenario: Second job refused
- **WHEN** an ingestion job is running and the owner starts another
- **THEN** the second start is refused and names the running job

#### Scenario: Job stopped by a restart
- **WHEN** the laptop restarts during a job
- **THEN** the view shows the job as interrupted with its progress, and Resume starts a new run that reuses the saved vectors

#### Scenario: Sleep inhibitor unavailable
- **WHEN** the system cannot provide a sleep inhibitor
- **THEN** the job still runs, and the view states that the laptop is not being kept awake
