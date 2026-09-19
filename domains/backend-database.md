# Backend database

Trigger: A backend contract, retry, transaction or schema migration change.

1. Map API and schema contracts, authorization/tenant boundaries, units and errors. Exercise public behavior at its actual seam. Use a disposable database only when the behavior includes persistence.

2. When persistence or retries are involved, verify transaction rollback and crash/partial-failure behavior; repeat requests to check idempotency. Test conflicting payloads for a reused idempotency key and relevant concurrent calls.

3. For migrations, identify old/new readers and writers, backward compatibility, rollback/recovery and data-loss risk. Use query plans and representative data for performance conclusions.

Stop: Migration ownership or destructive intent unclear; production access required; relevant database/concurrency behavior untested.

Output: add the relevant checks, identities and evidence to the parent skill handoff; record missing capabilities in limitations. This procedure supplies requirements, not an installed tool or tested execution adapter.
