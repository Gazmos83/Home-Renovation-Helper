## ADDED Requirements

### Requirement: The Pieces page shows a built version's assembly steps
On the Pieces page, a built version SHALL offer an "Assembly" dropdown that lists the `assembly` steps of the version's own `spec.json`, in their stored order. Each step SHALL show its number as two digits, its title and its body, exactly as stored. A built version whose `spec.json` holds no steps SHALL say "This version lists no assembly steps." A version that is not built SHALL offer no Assembly dropdown. A failed read of `spec.json` SHALL show its reason inside the dropdown. When the dropdown lists steps, it SHALL offer "Download assembly (PDF)". The PDF SHALL be made in the browser from the listed steps, titled with the piece and version, hold every step's number, title and body in order, and be saved as `<piece>-v<N>-assembly.pdf`. A failure to make the PDF SHALL be shown next to the action. The dropdown SHALL NOT show a model name, prompt, token count or cost. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Built version with steps
- **WHEN** the owner shows built `hall-bench` v2 on the Pieces page, whose `spec.json` holds six assembly steps ending in "Install"
- **THEN** its Assembly dropdown lists steps 01 to 06 in order, with step 06 titled "Install" and its body "Position, level and fix the build in place."

#### Scenario: Built version without steps
- **WHEN** a built version's `spec.json` has no `assembly` field or an empty one
- **THEN** its Assembly dropdown says "This version lists no assembly steps."

#### Scenario: Download the steps as a PDF
- **WHEN** the owner opens the Assembly dropdown of `hall-bench` v2 and presses "Download assembly (PDF)"
- **THEN** a file `hall-bench-v2-assembly.pdf` is saved. It is titled "hall-bench – version 2 – Assembly" and holds steps 01 to 06 with their titles and bodies. No request is sent to the server for it.

#### Scenario: No steps, no download
- **WHEN** a built version's `spec.json` holds no assembly steps
- **THEN** its Assembly dropdown offers no PDF download

#### Scenario: Version not built
- **WHEN** the owner shows `hall-bench` v3, which failed to build
- **THEN** no Assembly dropdown is offered for v3
