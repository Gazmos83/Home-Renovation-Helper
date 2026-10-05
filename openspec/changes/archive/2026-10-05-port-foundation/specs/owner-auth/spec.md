## Purpose

Defines the single-owner sign-in: one account created from configuration, an HttpOnly session cookie, sign-in, sign-out and who-am-I, and the two gates (owner and developer) that every later route depends on. There is no registration, no role model and no passcode header.

## ADDED Requirements

### Requirement: One owner account from configuration
On startup the service SHALL ensure exactly one owner account exists, created from the configured owner email and initial password when the account table is empty. The password SHALL be stored only as an argon2 hash and never logged. When an account already exists, the configured password SHALL NOT overwrite the stored hash, so a password changed later survives restarts.

#### Scenario: First start
- **WHEN** the service starts against a database with no account
- **THEN** one account with the configured email exists afterwards and its password verifies against the configured value

#### Scenario: Later start
- **WHEN** the service starts and an account already exists with a different password hash
- **THEN** the stored hash is unchanged

#### Scenario: Weak configured password
- **WHEN** the configured initial password is shorter than ten characters
- **THEN** startup fails with an error naming `OWNER_PASSWORD`

### Requirement: Cookie sign-in and sign-out
`POST /auth/login` SHALL verify the email and password with a constant-time comparison against the stored hash (or a dummy hash when the email is unknown), SHALL issue an opaque random token stored only as a hash with an expiry that slides on use, and SHALL set it as an HttpOnly, SameSite=Lax cookie. `POST /auth/logout` SHALL revoke the session named by the cookie and clear the cookie, succeeding silently without one. `GET /auth/me` SHALL return the signed-in owner's id and email, or 401.

#### Scenario: Successful sign-in
- **WHEN** the owner posts the correct email and password
- **THEN** the response sets an HttpOnly session cookie and the token is stored only as a hash

#### Scenario: Wrong password
- **WHEN** a caller posts the correct email with a wrong password
- **THEN** the response is 401 with a generic message that does not say which field was wrong

#### Scenario: Unknown email
- **WHEN** a caller posts an email that is not the owner's
- **THEN** the response is the same 401 as for a wrong password, after the same work

#### Scenario: Sign-out
- **WHEN** the owner posts to logout with a valid cookie
- **THEN** the session is revoked, the cookie is cleared and a later request with the old cookie is refused

#### Scenario: Who am I
- **WHEN** a request with a valid cookie asks for the current account
- **THEN** the response carries the owner's id and email and nothing else

#### Scenario: Expired session
- **WHEN** a request carries a cookie whose session expiry has passed
- **THEN** the request is refused as not signed in

### Requirement: Owner gate
The service SHALL expose a single dependency that every homeowner route depends on. It SHALL admit a request only when a valid, unexpired, unrevoked session cookie is present, SHALL refuse every other request with 401 and one fixed message, and SHALL resolve the owner from the cookie alone, never from a request body, header or model output.

#### Scenario: Valid cookie
- **WHEN** a gated route is called with a valid session cookie
- **THEN** the route runs with the owner resolved from the session

#### Scenario: No cookie
- **WHEN** a gated route is called without a session cookie
- **THEN** the response is 401 with the fixed refusal message

#### Scenario: Owner named in the body is ignored
- **WHEN** a gated route is called without a cookie but with an owner identifier in the body
- **THEN** the response is 401 and nothing is read on that owner's behalf

### Requirement: Developer gate
Routes under `/admin` SHALL depend on a stricter dependency that requires a valid owner session **and** the developer panel to be enabled by configuration. When the panel is disabled, those routes SHALL answer 404 so the homeowner surface shows no sign of them.

#### Scenario: Panel enabled
- **WHEN** the developer panel is enabled and the owner calls an `/admin` route with a valid cookie
- **THEN** the route runs

#### Scenario: Panel disabled
- **WHEN** the developer panel is disabled and the owner calls an `/admin` route with a valid cookie
- **THEN** the response is 404

#### Scenario: Not signed in
- **WHEN** the developer panel is enabled and an `/admin` route is called without a cookie
- **THEN** the response is 401 with the owner gate's refusal message

### Requirement: Sign-in attempts are bounded and logged
Sign-in attempts SHALL be rate-limited per address and email and every sign-in, failed attempt and sign-out SHALL be recorded in the structured logs without the password.

#### Scenario: Repeated failures
- **WHEN** more failed sign-ins than the configured limit arrive within the window
- **THEN** further attempts are refused with 429 until the window passes

#### Scenario: Password never logged
- **WHEN** any auth route logs its event
- **THEN** the record carries the email and outcome but no password
