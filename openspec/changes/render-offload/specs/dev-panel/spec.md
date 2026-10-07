## ADDED Requirements

### Requirement: Render offload is managed from the developer panel
Behind the developer gate, the developer SHALL be able to:
- read whether offload is configured (host, port, user, remote Blender path and device shown; key file and known-hosts contents never shown);
- test the connection, reporting reachability, the remote Blender version and the GPU devices it lists;
- run the remote benchmark through the render guard;
- set the final target to `local` or `remote`;
- set an hourly rate in euros;
- read the last twenty remote jobs with estimate, actual, transfer seconds, outcome and the euro estimate from the hourly rate.

Setting the target to `remote` SHALL be refused while offload is not configured. A change SHALL apply to the next render without a restart.

#### Scenario: Remote target without configuration
- **WHEN** offload is not configured and the developer sets the final target to `remote`
- **THEN** the change is refused saying offload is not configured, and the target stays `local`

#### Scenario: Connection test
- **WHEN** the developer tests a reachable server running Blender 5.2.1 with one GPU
- **THEN** the response reports reachable, version 5.2.1 and the GPU's device name
