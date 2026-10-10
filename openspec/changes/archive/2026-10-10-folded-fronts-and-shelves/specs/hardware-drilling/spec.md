## ADDED Requirements

### Requirement: Drilling on a folded side names the split boards
When a module has `side_folds` and adjustable shelves or hinged doors, the drilling list SHALL name the cut-list side-board rows of that module, not `{module}-side`.

Shelf-pin holes SHALL be listed on each side board's inner face:
- an unfolder side: the same columns and hole heights as today, measured from that board's bottom end;
- a folded side along height: holes whose height is below `from_mm` on the lower board, from that board's bottom end; holes at or above `from_mm` on the upper board, from that board's lower end along the slope;
- a folded side along depth: the same split onto the front and back boards, measured from each board's front end.

Hinge cups SHALL stay on the door row, measured from the door's bottom end as today. Each mounting plate SHALL be listed on the side board that holds that hinge's height (lower or upper, or front or back), with a note when that board is the sloped piece.

A module with no `side_folds` SHALL give the same drilling entries as before.

#### Scenario: Pin holes on the split left side
- **WHEN** the 800 × 2000 × 400 mm cabinet has a left height fold from 1100 mm and adjustable shelves, and the shelf-pin data sheet gives every value
- **THEN** the drilling list names `cabinet-side-left-lower`, `cabinet-side-left-upper` and `cabinet-side-right`, and has no `cabinet-side` row

#### Scenario: Hinge plates on the sloped board
- **WHEN** that cabinet has two hinged doors and a left height fold from 1100 mm, and a hinge above 1100 mm
- **THEN** that hinge's mounting plate is listed on `cabinet-side-left-upper` with a note that it sits on the sloped board

#### Scenario: Unfolder module unchanged
- **WHEN** a module with no `side_folds` has adjustable shelves
- **THEN** its shelf-pin entry still names `{module}-side`
