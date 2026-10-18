## ADDED Requirements

### Requirement: The Cut list marks hardware the model does not show
The Cut list tab SHALL mark a hardware row with `*` after its item when its `shown` is less than its quantity, or when its quantity is unknown and its `shown` is 0. A row with some pieces shown SHALL add "(n of m shown)". When any row is marked, a legend under the hardware table SHALL read "* not shown in the model". A version whose `spec.json` hardware has no `shown` SHALL mark no row and show no legend. The tab SHALL pass a recorded browser check before it counts as done.

#### Scenario: Unshown line marked
- **WHEN** the owner opens the Cut list of a version whose `murphy-mechanism` row has quantity 1 and `shown` 0
- **THEN** the row reads "Vertical Murphy bed mechanism … *" and the legend "* not shown in the model" is shown

#### Scenario: Partly shown
- **WHEN** a hinge row has quantity 24 and `shown` 16
- **THEN** the row is marked `*` with "(16 of 24 shown)"

#### Scenario: Fully shown, no mark
- **WHEN** every hardware row's `shown` equals its quantity
- **THEN** no row is marked and no legend is shown

#### Scenario: Older version
- **WHEN** the owner opens a version built before hardware was drawn
- **THEN** no row is marked and no legend is shown
