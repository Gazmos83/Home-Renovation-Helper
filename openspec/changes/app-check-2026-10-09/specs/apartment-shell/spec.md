## MODIFIED Requirements

### Requirement: Intake proposes a whole apartment from a plan
`record_plan` SHALL take an apartment name, its default heights and every room's outline and openings, validate each room by the room rules and the apartment by the overlap rule, and pause for the owner's `yes` with a summary listing each room's size and area, the openings, and every plausibility warning: a door outside 700–1000 mm wide, a window sill outside 700–1100 mm, a ceiling outside 2300–3200 mm, or a room area more than 5% from a printed area the call states. On `yes` the apartment and its rooms are written; on `no` nothing is written and the reason returns to Intake. A failing room or overlap SHALL be refused naming it with no pause.

When the house file already holds an apartment of that name, the plan read SHALL replace it:
- The summary SHALL say that the stored apartment is replaced.
- For each room in both, the summary SHALL show its stored size and its size as read now.
- It SHALL list as new each room the read adds.
- It SHALL list as removed each stored room the read does not name, with the pieces in it that become "No room" and its composition, if any, that is removed.

On `yes`, the apartment SHALL hold exactly the rooms of the read. Each removed room SHALL be deleted as a measured room delete deletes it: its pieces become unassigned, conversations that confirmed it lose their confirmed room, and its room composition and version folders are removed. Overlap SHALL be checked among the read's rooms only. A re-read SHALL be refused, with no pause, while a composition of a removed room or of the apartment has a build or render queued or running.

#### Scenario: Plan confirmed
- **WHEN** Intake proposes a two-room apartment from a blueprint and the owner answers `yes`
- **THEN** the apartment and both rooms are in the house file and the next turn's context names them

#### Scenario: Area does not match the plan
- **WHEN** a room's outline gives 30.1 m² and the call states the plan prints 32.3 m²
- **THEN** the preview carries a warning naming the room and both areas

#### Scenario: Plan read again
- **WHEN** `Wohnung` holds `Wohnen` 5200 × 4000 mm, `Küche` and `Bad`, and a new read names `Wohnen` at 5100 × 4000 mm and `Küche`
- **THEN** the summary says `Wohnung` is replaced, shows `Wohnen` as 5200 × 4000 stored and 5100 × 4000 read, and lists `Bad` as removed

#### Scenario: Removed room deleted on yes
- **WHEN** the owner answers `yes` to that summary and `Bad` held `towel-rack`
- **THEN** `Wohnung` holds only `Wohnen` and `Küche`, `Bad` is gone, and `towel-rack` has no room

#### Scenario: Re-read while a composition builds
- **WHEN** composition `Bad` is building and a re-read would remove `Bad`
- **THEN** the call is refused saying to wait until the build finishes, and nothing pauses or changes
