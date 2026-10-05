## Purpose

Defines the backend service's operational contract: configuration from the environment with fail-fast validation, health reporting, which browser origins may call it, structured logging, a migration-owned schema that leaves the checkpointer's tables alone, and optional tracing that is never load-bearing.

## Requirements

### Requirement: Configuration is validated at startup
The service SHALL read every deployment-specific value from the process environment (or a local `.env` file) and SHALL refuse to start, with an error naming each offending variable, when a required value is absent or malformed. Required values: the database URL, the gateway credential, the owner's email and initial password, and the allowed browser origins. The service SHALL NOT fall back to a built-in default for any required value.

#### Scenario: All required configuration present
- **WHEN** the service starts with every required value set to a well-formed value
- **THEN** the service starts and logs a startup summary that reports configuration came from the environment

#### Scenario: Required configuration missing
- **WHEN** the service starts with the database URL unset
- **THEN** startup fails with a non-zero exit and an error naming `DATABASE_URL`

#### Scenario: Several values wrong at once
- **WHEN** the service starts with the gateway credential unset and an empty origin list
- **THEN** the single startup error names both variables

#### Scenario: Secrets are never echoed
- **WHEN** the service logs its startup summary
- **THEN** the gateway credential, the owner password, the Langfuse keys and any password embedded in the database URL are redacted

### Requirement: Health endpoint reports database reachability
The service SHALL expose an unauthenticated health endpoint that reports whether the process is running and whether its database accepts a trivial query, so "process down" and "process up, database down" are distinguishable.

#### Scenario: Service and database both healthy
- **WHEN** a client requests the health endpoint and the database accepts a trivial query
- **THEN** the response status is 200 and the body reports the database as reachable

#### Scenario: Database unreachable
- **WHEN** a client requests the health endpoint and the database refuses connections
- **THEN** the response status is 503 and the body reports the database as unreachable, without a stack trace or connection string

### Requirement: Cross-origin access is explicit and credentialed
Because the single-page application is served from another origin, the service SHALL permit cross-origin requests only from origins named in its configuration, SHALL permit credentials from those origins so the session cookie travels, and SHALL refuse to start when the configured origins are empty or contain the wildcard `*`.

#### Scenario: Request from a configured origin
- **WHEN** a browser sends a cross-origin request from a listed origin
- **THEN** the response permits that origin and permits credentials

#### Scenario: Request from an unconfigured origin
- **WHEN** a browser sends a cross-origin request from an origin not listed
- **THEN** the response grants that origin no access

#### Scenario: Wildcard origin configured
- **WHEN** the configured origins contain `*`
- **THEN** startup fails with an error stating that credentialed requests need explicit origins

### Requirement: Structured request logging
The service SHALL emit one machine-parseable log record per HTTP request carrying at least the method, path, status and elapsed duration, and SHALL log an unhandled error with the request path and error type while answering the caller with a generic 500 body that carries no detail.

#### Scenario: A request is served
- **WHEN** the service handles any HTTP request
- **THEN** exactly one structured record is emitted with method, path, status and duration

#### Scenario: A request raises an unhandled error
- **WHEN** a handler raises an unexpected error
- **THEN** a structured error record names the path and error type, and the response is a 500 whose body contains only a generic message

### Requirement: Schema is migration-owned and checkpointer tables are excluded
The database schema the application owns SHALL be created and upgraded only by ordered, reversible migrations. The schema owned by the conversation checkpointer SHALL be created by the checkpointer itself at startup and SHALL be excluded from migration authoring, so a generated migration never proposes creating, altering or dropping those tables.

#### Scenario: Applying migrations to an empty database
- **WHEN** migrations are applied to an empty database
- **THEN** every table and index the application owns is created, including the `vector` extension

#### Scenario: Migrations are reversible
- **WHEN** the newest migration is applied and then reverted
- **THEN** the schema returns to its prior state without manual intervention

#### Scenario: Checkpointer tables are not migration-owned
- **WHEN** a migration is generated against a database that also holds the checkpointer's tables
- **THEN** the generated migration contains no operation touching those tables

#### Scenario: Checkpointer set up at startup
- **WHEN** the service completes startup against a reachable database
- **THEN** the checkpointer's tables exist and the service holds a usable checkpointer

#### Scenario: Checkpointer setup fails
- **WHEN** the checkpointer cannot connect at startup
- **THEN** the service still starts, logs a warning, and any later turn that needs the checkpointer is refused with a stated reason

### Requirement: Optional tracing that never blocks a turn
When all three Langfuse values (host, public key, secret key) are set, the service SHALL run every agent turn with a tracing callback that records the graph's nodes, model calls and tool invocations as one trace tagged with the owner, session and, when present, project identifiers. When any value is unset, tracing SHALL be off and the startup summary SHALL say so. A tracing failure SHALL never change a turn's result.

#### Scenario: Tracing is configured
- **WHEN** all three Langfuse values are set and a turn runs
- **THEN** the run carries a tracing callback with the owner id and session id as trace metadata

#### Scenario: Tracing is not configured
- **WHEN** one or more Langfuse values are unset
- **THEN** the service starts, the startup summary reports tracing as off, and turns run with no tracing callback

#### Scenario: Langfuse is unreachable
- **WHEN** tracing is configured and the Langfuse endpoint cannot be reached
- **THEN** the turn is answered exactly as without tracing and the failure is logged once per process, without either key

#### Scenario: Personal data is masked
- **WHEN** a traced turn contains an email address
- **THEN** the trace carries a placeholder in its place
