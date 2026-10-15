## ADDED Requirements

### Requirement: The Lighting specialist offers the detail render's choices
When the owner asks for a final image of the detail pass, the Lighting & materials specialist SHALL render a detail still unless the owner asks for a turntable. When the owner asks for a detail turntable, the specialist SHALL offer the choices in plain words before asking for it:
- a detail still now;
- the turntable on the laptop, with its estimate;
- the turntable on the render server, when finals go there.

The render itself SHALL still wait for the owner's typed `yes` to the approval with its warnings. The specialist SHALL NOT pass frames, resolution or engine.

#### Scenario: Turntable asked for
- **WHEN** the owner writes "make a turntable of the lit version" and finals run on the laptop
- **THEN** the reply offers a detail still now or the laptop turntable with its estimate, and no render starts until the owner chooses and answers `yes`

#### Scenario: Final image without a kind
- **WHEN** the owner writes "render the final image"
- **THEN** a detail still is proposed for approval
