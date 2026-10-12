## ADDED Requirements

### Requirement: Legacy guidance does not establish verified engineering evidence
Existing guideline publications, owner notes, drilling sheets and geometric rules SHALL retain their ordinary preliminary-guidance role outside the separate quarantine experiment. They SHALL NOT establish verified resistance, allowable span or anchorage solely by citation, thickness or bracket count. During an engineering turn, guideline search SHALL use engineering rights/applicability eligibility; an unreviewed legacy source SHALL yield metadata/no eligible evidence rather than its text. Foundation rollout SHALL NOT delete/rewrite legacy files, chunks or saved hardware inputs.

#### Scenario: Retailer bracket table cited
- **WHEN** a legacy bracket rule gives a count for a shelf
- **THEN** its layout guidance is not presented as verified shelf or wall-fixing capacity, including beyond its published table

#### Scenario: Guideline tool used for engineering
- **WHEN** an engineering turn calls guideline search for an unreviewed local PDF
- **THEN** no text from that source is returned to the model and the missing review is stated

#### Scenario: Ordinary guidance preserved
- **WHEN** a non-engineering turn uses an existing owner guideline note after foundation rollout
- **THEN** the ordinary guideline behaviour remains available and the foundation has not quarantined its stored content globally
