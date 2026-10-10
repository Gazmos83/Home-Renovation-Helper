## ADDED Requirements

### Requirement: The Designer may put fronts on a folded carcass
The Designer's instructions SHALL say that a module with `side_folds` may carry overlay fronts and adjustable shelves, that those fronts follow the folded opening (an n-gon when the outline is not a rectangle), and that dividers on a folded module are still not expressible. Bevels SHALL stay unexpressible.

#### Scenario: Instructions allow fronts on a fold
- **WHEN** the Designer's instructions are loaded
- **THEN** they name `side_folds` together with fronts and adjustable shelves, and they still name dividers as not expressible on a fold

#### Scenario: A panel bend is side_folds
- **WHEN** the Designer's instructions are loaded
- **THEN** they say a bend in a carcass side is the field `side_folds`, that the Designer must never tell the owner there is no field for a bend angle, and that the field applies to the module the owner named (its id from the piece summary)
