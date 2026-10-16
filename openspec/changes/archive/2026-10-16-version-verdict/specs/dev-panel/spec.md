## ADDED Requirements

### Requirement: Version verdicts are readable per slot and model
Behind the developer gate, the developer SHALL be able to read version-verdict counts grouped by the slot and model that produced each version: the number of `matches` and `mismatch` verdicts and the time of the latest note, and the notes of one group, newest first, each naming its piece and version. Versions with no recorded slot or model SHALL be grouped under no slot and no model. Reading verdicts SHALL NOT change routing or any setting. The developer route tree's Feedback page SHALL show these counts and notes beside the render ratings.

#### Scenario: Summary after three verdicts
- **WHEN** two versions made by the Designer were marked "Doesn't match" and one "Matches what I confirmed"
- **THEN** the Designer's model shows 1 matches and 2 mismatch, and selecting it lists the two notes newest first

#### Scenario: Older versions grouped as unknown
- **WHEN** `amesbury-wardrobe` v4, made before versions recorded their origin, is marked "Doesn't match"
- **THEN** it is counted in a row with no slot and no model

## MODIFIED Requirements

### Requirement: Memory settings are edited by the developer
The developer SHALL be able to read, set and reset the memory settings:
- compression:
  - recent inputs sent in full (0–20, default 5; 0 means the trigger alone decides);
  - trigger share of the usable context budget (50–100 %);
  - recent turns always kept (0–20);
  - note length (100–2000 tokens);
  - note headings and instructions (text up to 2000 characters);
  - tool-result cut length (0–2000 characters);
- saving: preferences from a brief saved or not (review confirmation is deferred);
- the conversation's slice: other builds as one line or hidden; preferences, latest review items, open version verdicts and open generator-extension requests included or left out; render ratings 0–10.

Each setting SHALL show its default, and resetting SHALL restore it. An out-of-range value SHALL be refused naming the field. The page SHALL also list the fixed rules no setting changes: rooms enter a conversation only by confirmation, nothing from another conversation is given, generator-extension requests are always saved, and the note's safety rules are composed in code. Changes SHALL apply from the next call, without a restart. The route SHALL sit behind the developer gate.

#### Scenario: Trigger lowered
- **WHEN** the developer sets the trigger share to 75 %
- **THEN** the setting is stored and the next call compresses at 75 % of the usable budget

#### Scenario: Out of range
- **WHEN** the developer sets recent turns always kept to 50
- **THEN** it is refused naming the field and the stored value is unchanged

#### Scenario: Recent inputs changed
- **WHEN** the developer sets recent inputs sent in full to 8
- **THEN** the setting is stored, the next call sends the last 8 owner inputs' exchanges in full, and older ones are replaced by the summary

#### Scenario: Recent inputs out of range
- **WHEN** the developer sets recent inputs sent in full to 21
- **THEN** it is refused naming the field and the stored value is unchanged

#### Scenario: Reset
- **WHEN** the developer resets the note length
- **THEN** it is 400 tokens again

#### Scenario: Panel disabled
- **WHEN** the panel is disabled and the memory route is called with a valid session
- **THEN** the response is 404

#### Scenario: Version verdicts left out
- **WHEN** the developer turns open version verdicts off
- **THEN** the setting is stored and the next call's context lists no verdicts

