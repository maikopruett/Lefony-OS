# SDK accounts and local project links

The matching account endpoints and database migrations are deployed. Real GitHub
authorization, macOS Keychain storage and separate-process account/owned-app reads
have passed with the source SDK. The public Linux x86-64 bundle includes account
commands and passes local Secret Service tests under emulation. Real Linux OAuth,
the older macOS download and native clean-host acceptance remain separate. The [publication candidate](PUBLISHING.md)
now provides folder build/ARM testing, offline `publish --dry-run`, explicit
publication, resumable uploads, reviewable listing pull/merge and browser conflict
resolution, metadata-only `listing push`, and explicit `apps withdraw APP_ID`.
See the publishing guide for saved operation status/resume and revision rules.

## Sign in

```sh
lefony-sdk login
lefony-sdk whoami
lefony-sdk apps list
lefony-sdk apps show my-app
lefony-sdk logout
```

`login` prints a browser URL and an eight-character code. Sign into GitHub on
that page, then enter the code from your terminal and choose **Connect SDK**.
The terminal confirms the account after it receives the authorization. Use
`--no-browser` to copy the URL yourself, or `--label "Laptop SDK"` to name the
session in the website's **Manage SDK access** page. Requests expire after ten
minutes. Ctrl-C attempts to cancel the request, including an issued session
whose response was lost. If cancellation cannot be confirmed, the command
points to the website access page.

The website reuses its GitHub authorization-code flow with S256 PKCE and no
repository scope. Its stable `github:<numeric-id>` identity is shared by browser
and SDK operations, including after a GitHub username change. The SDK receives
a Lefony store credential, with `store:read` and `store:publish` scopes, valid for
30 days. There is no automatic extension; sign in again after expiry. It grants
no GitHub repository access, firmware operation or calculator connection.

Credentials use macOS Keychain, Windows Credential Manager or Linux Secret
Service through `keyring==25.7.0`. Source-tool users install the repository
development requirements (or `keyring==25.7.0` in their SDK Python environment).
Linux additionally requires a running, unlocked Secret Service. Commands fail
clearly when platform storage is unavailable; there is no plaintext file
fallback. Backend plugins/configuration cannot select a different token store.
Other SDK commands, including offline project creation, do not load account
credentials. Native host credential-store qualification is still pending.

SDK credentials are not stored in projects, passed as shell arguments, printed,
or included in source bundles. Each HTTPS store origin has its own credential
entry. Signing into another account replaces the active credential and revokes
the previous session when reachable. A failed previous-session revocation is
reported with the website recovery link. `logout` revokes the remote credential
before removing its local copy; a network failure leaves it available for retry.
An expired/revoked credential is removed when authentication returns 401.

The website's **Manage SDK access** page lists up to 20 active sessions and can
revoke one or all of them. Revoking all also cancels approved sign-ins that have
not issued a credential. Browser logout and SDK logout are separate operations.
Apps, releases and installed copies remain present after session revocation.

## Find and link projects

`apps list` follows every owned-app page, including apps without a local folder,
unpublished drafts, failed submissions, hidden listings and withdrawn apps.
`apps show` retrieves the complete paginated release history and publication
states. It never substitutes the public catalog for the owned library.

```sh
lefony-sdk --project ./my-app project link my-app
lefony-sdk project list
lefony-sdk --project ./my-app project unlink
```

Linking verifies current server ownership and requires `app.json` to contain
the same app ID. It does not rewrite source or reserve a new store app. A local
`.lefony/store.json` records schema, origin, account ID and app ID; it contains
neither credentials nor an absolute path. A conflicting existing link must be
explicitly unlinked first. `project unlink` works offline.

The first link also records `.lefony/store-base.json` with the exact listing content and observed
revision. Repeating link does not refresh it. Successful publication records its
own commit revision; updates stop if later website changes made that baseline
stale. Inspect `apps show APP_ID` and reconcile changes before replacing a link.

`project list` shows remembered local folders for the active account/origin and
marks missing or unlinked folders. Absolute locations exist only in the private
host index under Application Support, Local AppData or XDG state storage. They
are never sent to the store. Signing in on another computer retrieves owned
store apps, not local source folders. Links do not authorize a mutation: the
server checks the active account again for every store operation.

## Development endpoint and protocol

Account commands accept `--store-origin https://your-development-store` and an
optional `--store-ca-file` for a controlled TLS endpoint. An exact HTTPS origin
is required. Default HTTPS uses the host's native certificate store through
pinned `truststore`; an explicit CA file replaces system trust for that context
without changing the host's certificate store. Certificate and hostname checks
stay enabled; redirects are rejected before credentials could be forwarded.
Ordinary JSON requests are limited to 16 KiB, upload creation to 64 KiB,
listing edits to 8 MiB, upload chunks to 256 KiB and responses to 1 MiB. Each
request runs in a disposable process with a parent-enforced 20-second deadline,
including process startup, DNS, certificate setup/verification, uploads and the
complete response. A separate bounded IPC exchange keeps blocked pipe transfers
off the supervising thread. Deadline or Ctrl-C cleanup terminates and reaps that
worker; bounded cleanup joins can add up to one second. No request credentials
are placed in process arguments or temporary files.

The transport never retries a request. A failed mutation may already have reached
the store: inspect the saved publication/listing/withdrawal attempt before an
explicit resume. Truncated fixed-length responses are rejected even if their
received prefix contains valid JSON. The sign-in loop retains its ten-minute
polling deadline and server backoff; an in-flight request or remote cancellation
can each take its own request deadline. Cancellation after receiving an
authorization ticket still attempts to revoke that exact ticket. Certificate
configuration is checked when a network request starts, so offline commands and
an empty local account do not start a worker.

The browser authorization handshake is a Lefony session protocol, not a GitHub
device grant. The client creates a random 256-bit credential and sends only its
SHA-256 digest when starting a request. The service returns a public request ID
and short comparison code. The browser never receives the credential. The
terminal must prove possession in TLS POST polls, while the signed-in browser
must submit the short code through the same-origin decision endpoint. Issuance
and grant consumption are atomic. Repeating a poll after a lost response returns
the same session and expiry; it does not mint another credential. The database
stores credential/code digests, not their plaintext.

| Endpoint under `/api/store` | Access and purpose |
| --- | --- |
| `POST /sdk/authorizations` | CLI; starts a ten-minute request |
| `GET /sdk/authorize?id=…` | Browser sign-in/approval page; request ID only |
| `POST /sdk/authorizations/ID/decision` | Browser cookie + exact origin + short code |
| `POST /sdk/authorizations/ID/poll` or `/cancel` | CLI credential proof; minimum five-second poll interval |
| `GET /sdk/me` | Scoped SDK bearer credential; current identity/expiry |
| `GET /sdk/apps` and `/sdk/apps/ID` | Scoped credential; 50 entries per page, `after` cursor |
| `POST /sdk/logout` | Idempotent credential revocation |
| `GET /sdk/access` | Browser session-management page |
| `DELETE /sdk/access/SESSION_ID` or `/all` | Browser cookie + exact origin; owner-only revocation |

SDK endpoints reject ambient browser cookies/origins. Browser management keeps
the existing origin/cookie controls; SDK credentials do not authenticate review,
builder, installer or browser-session endpoints. Login and code entry are rate
limited, and an account may have at most 20 active SDK sessions.

Implementation references: [GitHub OAuth](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps),
[platform credential storage](https://keyring.readthedocs.io/en/latest/), and
[D1 transaction batches](https://developers.cloudflare.com/d1/worker-api/d1-database/).
Local tests use synthetic accounts, in-memory credential storage and a controlled
GitHub endpoint. They do not prove real GitHub configuration or native keychain
behavior on every supported host.
