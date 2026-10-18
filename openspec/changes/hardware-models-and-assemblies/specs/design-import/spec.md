## ADDED Requirements

### Requirement: An import points mechanism lines to the fold-down bed
When an imported design's hand-written line reads as a fold-down bed mechanism (a catalog `matches` phrase of `fold-bed-vertical`) and the design carries no `fold_bed`, the preview SHALL keep the line and warn that it is not drawn and can be written as a `fold_bed`. It SHALL NOT convert it. The import template's guide SHALL describe `fold_bed`, and say its mechanism is illustrative.

#### Scenario: Murphy mechanism warned
- **WHEN** the murphy-bed design is imported with its `murphy-mechanism` line and no `fold_bed`
- **THEN** the line is kept, and the preview warns it can be written as a `fold_bed`
