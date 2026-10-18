## ADDED Requirements

### Requirement: A room render started in a thread is followed and points to its result
When a specialist's tool starts a render of a room or apartment composition in a thread, the service SHALL record it against that thread. While it is queued or running, the thread's progress SHALL report `rendering`. A recorded render SHALL count only while that composition version's status shows it queued or running, so a record left behind by a failed process never keeps the thread rendering. The record SHALL be removed when the render's notice is posted.

The notice of a finished room render SHALL name the composition and version, and say that it can also be found on the Rooms page, for example "The draft turntable of wohnen version 11 is ready. You can also find it on the Rooms page." It SHALL store the composition and version. When the thread is read, the notice SHALL carry a link to its result: a turntable's viewer, labelled "Open the turntable viewer", or a still's image, labelled "Open the still". Each link uses the composition's file route, and is included only while its file exists. A failed room render's notice SHALL carry no link. A notice posted before this requirement SHALL carry none.

#### Scenario: Room render followed
- **WHEN** the owner asks in the Murphy bed conversation for a draft turntable of the Wohnen composition and it is running
- **THEN** that thread's progress reports `rendering`

#### Scenario: Stale record ignored
- **WHEN** a recorded room render's composition version shows no queued or running render
- **THEN** the thread's progress does not report `rendering` for it

#### Scenario: Turntable ready with a link
- **WHEN** the draft turntable of `wohnen` version 11 finishes
- **THEN** the thread holds a notice saying "The draft turntable of wohnen version 11 is ready. You can also find it on the Rooms page." with a link "Open the turntable viewer" to `/compositions/wohnen/versions/11/files/viewer.html`

#### Scenario: Still ready with a link
- **WHEN** the draft still of `wohnen` version 11 finishes
- **THEN** its notice carries a link "Open the still" to `/compositions/wohnen/versions/11/files/still.png`

#### Scenario: File gone
- **WHEN** `wohnen` version 11 is deleted after its notice was posted
- **THEN** reading the thread shows the notice with no link

#### Scenario: Failed room render
- **WHEN** a room turntable started in a conversation fails
- **THEN** its notice says it did not finish and carries no link
