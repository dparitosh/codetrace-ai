# Contributing to CodeTrace AI

Use the [installation guide](README.md) and [test guide](docs/testing.md). Python
3.10+ and Node 24 are the recommended development runtimes. Install from the
committed npm lockfile; do not bypass dependency checks with force/legacy peers.

## Development workflow

1. Create a feature branch from the intended base and inspect existing changes.
2. Keep endpoints, secrets, limits and provider profiles in central configuration.
   Never commit `.env.local`, tokens, runtime databases or generated results.
3. Add regression coverage for changed behavior, especially provenance, endpoint
   validation, expiry, optimistic concurrency, truncation and uncertain writes.
4. Run the checks in [testing.md](docs/testing.md). Record which external services
   were actually tested; mocks and SQLite do not establish vendor/PostgreSQL compatibility.
5. Update the relevant maintained documentation. Describe the concrete problem,
   resulting behavior, verification and remaining limitations in the pull request.

Keep the active local-first API independent of optional legacy persistence and
unmounted integrations. New provider capabilities need bounded responses,
explicit configuration and failure states. Treat labels, source content, remote
RDF and AI output as untrusted data. Never substitute generated sample records
for actual build, test, security or traceability evidence.

In-app decisions concern a snapshot. They do not provide independent reviewer
authentication or replace repository code review.
