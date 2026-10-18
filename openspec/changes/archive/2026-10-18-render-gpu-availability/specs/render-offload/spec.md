## ADDED Requirements

### Requirement: A remote final with no render GPU in stock is refused before approval
In pod mode with no pod running, the check before a remote `final` is quoted SHALL also read RunPod's live pod stock (Secure Cloud) for each configured GPU type in the network volume's data centre. If every configured type reads `NONE` there, or is not listed for that data centre, the request SHALL be refused before any approval. The reason SHALL name the GPU types and the data centre, and suggest trying later or switching finals to the laptop. `LOW`, `MEDIUM` and `HIGH` SHALL count as in stock. If the stock read fails or does not answer within the check's ten seconds, the check SHALL NOT refuse on stock; the render goes on to approval and the create decides. The stock read SHALL create nothing and bill nothing. With a pod already running, stock SHALL NOT be read.

#### Scenario: Nothing in stock
- **WHEN** the GPU types are RTX A4500 and RTX 4090, the volume is in EU-RO-1, both read `NONE` there, and a remote `final` is requested
- **THEN** the request is refused before approval, saying none of RTX A4500 and RTX 4090 is in stock in EU-RO-1 right now, and no pod is created

#### Scenario: One type in stock
- **WHEN** the RTX A4500 reads `NONE` and the RTX 4090 reads `LOW` in EU-RO-1
- **THEN** the check passes and the quote is shown for approval

#### Scenario: Stock read fails
- **WHEN** the stock read answers 500 or times out
- **THEN** the check does not refuse on stock, and the quote is shown for approval

#### Scenario: Pod running
- **WHEN** a pod is running and a second final is requested
- **THEN** no stock is read and the pod is reused

### Requirement: GPU stock is sampled and kept for 90 days
In pod mode, while stock sampling is on, the service SHALL read the same live stock every 15 minutes. Each time, it SHALL store one record per configured GPU type: the time, the data centre, the GPU type and its level (`NONE` when not listed for that data centre). A failed read SHALL store nothing and SHALL be retried at the next interval. Records older than 90 days SHALL be removed. Sampling SHALL be on by default and switchable by the developer. It SHALL run only in pod mode, SHALL stop when the app stops, and SHALL never create or change anything on RunPod.

#### Scenario: A sample
- **WHEN** sampling is on, the GPU types are RTX A4500 and RTX 4090, and the read shows the RTX 4090 `LOW` in EU-RO-1 and the RTX A4500 not listed there
- **THEN** two records are stored: RTX 4090 `LOW` and RTX A4500 `NONE`, both for EU-RO-1

#### Scenario: Sampling off
- **WHEN** the developer has switched sampling off
- **THEN** no stock is read in the background and no record is stored

#### Scenario: Old records
- **WHEN** a record is 91 days old
- **THEN** it is removed
