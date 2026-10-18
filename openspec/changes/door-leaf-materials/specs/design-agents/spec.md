## ADDED Requirements

### Requirement: A revision names each door's material and says when the front layout changes
Wherever the application describes a door entry in words, including the revise confirmation, the Designer's summary of the active build and the import previews, it SHALL name each door whose material differs from the carcass, as "door <n> <slot>", beside its handle and slats.

A revise confirmation SHALL carry a line written by the application, not the model, for each module whose front layout the revision changes while the module has fronts both before and after; adding or removing all fronts is already stated by the fronts line. A front layout changes when:
- the number of front entries changes; or
- an entry's type or door count changes.

The line names the module, the layout before and the layout after. It says "side by side" for the doors of one entry and "stacked top to bottom" for separate entries. A revision that changes only an entry's materials, handle, slats or height SHALL carry no such line.

#### Scenario: One door's material changed
- **WHEN** the owner asks for the right door of `kommode` to be black and the Designer proposes `leaf_materials` {"2": "black_paint"} on the existing entry of two doors
- **THEN** the confirmation's fronts line names "door 2 black_paint" and the confirmation has no front-layout line

#### Scenario: Pair split into stacked entries
- **WHEN** a proposed revision replaces `kommode`'s one entry of two doors with two entries of one door each
- **THEN** the confirmation, before the owner answers, says that `kommode`'s front layout changes from 1 entry of 2 doors side by side to 2 entries stacked top to bottom

#### Scenario: Summary names the door materials
- **WHEN** the active build's latest version has `leaf_materials` on a door entry
- **THEN** the Designer's piece summary names each such door's slot

### Requirement: The Designer gives one door its own material without splitting the pair
The Designer's instruction SHALL say that a colour or material for some doors of an entry is set with that entry's `leaf_materials`, and that a pair or row of doors is never split into separate entries to give one door its own material, because separate entries stack top to bottom. When `leaf_materials` is refused, the Designer SHALL tell the owner the refusal in plain words and SHALL NOT change the front layout instead.

#### Scenario: Black right door asked for
- **WHEN** the owner of `lamellen-kommode` asks for the right door to be black with the slats kept
- **THEN** the Designer proposes the existing entry with `leaf_materials` for door 2 and the same door count, and the two doors stay side by side
