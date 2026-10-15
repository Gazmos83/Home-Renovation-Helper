## ADDED Requirements

### Requirement: Render pod availability is shown on the developer panel
In pod mode, behind the developer gate, the Render Offload tab SHALL show:
- **Start history** from the recorded pod sessions, separately for the last 7 and the last 30 days:
  - the number of pod start attempts;
  - the share that started (the pod answered and was ready);
  - the median start-up time of the starts that succeeded;
  - how many times each GPU type was placed;
  - the number of failed starts.
- **Stock history** from the stock samples, for the same two periods:
  - the share of sample times at which at least one configured GPU type was in stock;
  - the share for each GPU type;
  - the number of samples;
  - the time of the last sample.
- A switch to turn stock sampling on or off. A change SHALL apply without a restart.

With no sessions or no samples in a period, the tab SHALL say so instead of showing a share. None of this SHALL appear on a homeowner route.

#### Scenario: Start history
- **WHEN** in the last 7 days four pods were attempted, three became ready with start-up times of 60, 90 and 150 seconds, and one failed to start
- **THEN** the 7-day start history shows 4 attempts, 75% started, a median start-up of 90 seconds, and 1 failed start

#### Scenario: Stock history
- **WHEN** in the last 7 days there were 100 sample times and at 62 of them at least one configured GPU type was in stock
- **THEN** the 7-day stock history shows 62% with at least one render GPU in stock, from 100 samples

#### Scenario: Nothing recorded yet
- **WHEN** sampling has just been switched on and no sample exists
- **THEN** the stock history says no samples yet

#### Scenario: Switching sampling off
- **WHEN** the developer switches stock sampling off
- **THEN** the next 15-minute interval stores no sample, and the switch shows off after a reload
