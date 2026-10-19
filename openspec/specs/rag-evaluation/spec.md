# rag-evaluation Specification

## Purpose
Measures the quality of the application's retrieval and of the answers built from it with standard Ragas metrics over a hand-written golden set. Produces a dated report that serves as the course's AI evaluation evidence.

## Requirements

### Requirement: Golden set is hand-written, validated and split
The evaluation SHALL read a checked-in golden set. Each entry SHALL have a stable question ID, the question, a reference answer, at least one expected passage, the retrieval path (`catalog`, `guideline` or `engineering`), and a split (`dev` or `held_out`). An expected passage SHALL be named by a key that survives a re-ingest of unchanged content: the page URL and chunk position for catalogue and guideline passages, and the version and block for engineering evidence. The run SHALL validate the whole set before any retrieval or model call. It SHALL refuse a malformed set and name the entry and field, and it SHALL refuse unknown fields by name. It SHALL refuse an expected passage ID that is missing from the database it reads, naming the question, so that a re-ingest that changed IDs is caught instead of scored as a miss. Only the `held_out` split SHALL appear in the report's headline scores. The `dev` split SHALL be reported separately, marked as used for tuning.

#### Scenario: Unknown field refused
- **WHEN** a golden-set entry carries a field `expected_price`
- **THEN** the run stops before any model call and names the entry and `expected_price`

#### Scenario: Stale passage ID refused
- **WHEN** an entry expects a passage ID that is no longer in the database after a re-ingest
- **THEN** the run stops before any model call and names the question and the missing ID

#### Scenario: Headline uses held-out only
- **WHEN** the set holds 10 dev and 20 held-out questions
- **THEN** the headline scores are computed from the 20 held-out questions, and the dev scores appear in a separate, labelled section

### Requirement: Retrieval and answers are evaluated as the application runs them
For each question, the evaluation SHALL call the application's retrieval for that question's path with the arguments and defaults its agent tool uses. For engineering, this includes the remote-use boundary. It SHALL NOT change retrieval parameters, thresholds, instructions or model routing for the run. For every path, the run SHALL score ID-based context recall and precision, which make no model call, and model-judged context precision and recall against the reference answer. For `catalog` and `guideline` questions, it SHALL also produce an answer with the Researcher's routed model and instructions, given the retrieved passages wrapped exactly as the agent tool wraps them. It SHALL score that answer's faithfulness to those passages, its relevance to the question, and its factual correctness against the reference answer. Engineering answers are composed by code from cited evidence, so they SHALL NOT receive answer metrics, and the report SHALL say so. If retrieval returns nothing, the run SHALL record zero recall and score the answer metrics on the answer as returned. It SHALL NOT skip the question.

#### Scenario: Retrieval misses
- **WHEN** retrieval returns no passage for a question that has two expected passage IDs
- **THEN** that question's ID-based context recall is 0, and the question is still counted in the averages

#### Scenario: No tuning during the run
- **WHEN** an evaluation run completes
- **THEN** the retrieval limit, relevance thresholds and model routing in effect are the same as before the run

### Requirement: The judge goes through the gateway under its own per-run cap
Model-judged metrics SHALL use one judge model, named in the eval configuration, that is a registry slug. The judge SHALL be called through the application's OpenRouter gateway with that slug's generation profile. An unknown slug or a gateway configuration error SHALL stop the run before scoring and name the slug. Each run SHALL have a token ceiling from the eval configuration. It SHALL cover every model call the run makes, both Researcher answers and judge calls. Before each call, the tokens recorded so far in the run, taken from the usage the gateway reports, plus the call's output cap SHALL be compared with the ceiling. A call that would exceed it SHALL be refused, and the answers or metrics it served SHALL be recorded as "not scored: budget". The run SHALL NOT count against or change any agent's daily ceiling. The gateway credential SHALL NOT appear in the report, logs or traces.

#### Scenario: Ceiling reached midway
- **WHEN** the run's token ceiling is reached after 18 of 30 questions have model-judged scores
- **THEN** the remaining model-judged metrics are recorded as "not scored: budget", the ID-based metrics are still computed for all 30, and the report states the ceiling and the tokens used

#### Scenario: Unregistered judge refused
- **WHEN** the eval configuration names a judge slug that is not in the registry
- **THEN** the run stops before any judge call and names the slug

#### Scenario: Agent budgets untouched
- **WHEN** an evaluation run spends judge tokens
- **THEN** no agent slot's daily token usage changes

### Requirement: Passages reach the judge only within remote-use rights
A passage SHALL be sent to the judge only if it could be sent to a remote model in the application itself, including engineering rights permitting remote model use. Every passage SHALL be sent inside the application's untrusted-content delimiters. A question whose retrieved passages include one without remote-use rights SHALL get only the ID-based metrics, and the report SHALL list it with the reason. Reference passages SHALL NOT be sent to the judge.

#### Scenario: Local-only engineering passage
- **WHEN** an engineering question retrieves a block whose rights do not permit remote model use
- **THEN** no judge call carries that block's text, and the report lists the question as ID-metrics only, citing remote-use rights

### Requirement: Dated report and score traces without passage text
Each run SHALL write a Markdown report in the repository's evals folder, named by the run date. The report SHALL contain the headline score per metric and per retrieval path, a per-question table, the judge slug, the embedding model, the golden-set size per split, the tokens used against the ceiling, and every question or metric left unscored with its reason. A second run on the same date SHALL NOT overwrite an earlier report. Scores SHALL be sent to Langfuse as numeric scores keyed by run and question ID, without passage text, question text or answer text. If Langfuse is unavailable, the run SHALL log that and still write the report. The run SHALL make no writes to the application database.

#### Scenario: Langfuse down
- **WHEN** Langfuse is unreachable during a run
- **THEN** the report is written in full, and the log records that the scores were not sent

#### Scenario: Two runs on one day
- **WHEN** a report for today already exists and the evaluation runs again
- **THEN** the new report is written under a distinct name, and the earlier one is unchanged

#### Scenario: No engineering text in traces
- **WHEN** scores for engineering questions are sent to Langfuse
- **THEN** each trace carries only the run ID, question ID, metric name and value
