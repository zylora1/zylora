# Zylora V2 security model

Status: **Phase 0 threat model and control baseline frozen**

## Security objectives

1. A User cannot read or alter another User's Websites, assets, domains, Leads, analytics, billing,
   chatbot data, FAISS indexes, payments, exports, or settings.
2. Only one isolated Super Admin identity can perform platform operations, and every sensitive action
   is attributable and audited.
3. Browser/provider claims cannot grant ownership, entitlements, payments, credits, or publish state.
4. Stored Template/Website content cannot execute unapproved code or exfiltrate platform data.
5. Retried/concurrent operations cannot duplicate paid access, ownership, Leads, credits, routes, or
   deployments.
6. Compromise or outage of one optional provider degrades safely without exposing unrelated data.

## Threat model

Relevant actors include anonymous abuse bots, malicious customer Website visitors, authenticated
Users attempting horizontal escalation, compromised User sessions, attackers targeting Super Admin,
malicious uploaded content/Templates, forged provider webhooks, supply-chain compromise, and operators
making accidental high-impact changes.

High-value assets are credentials/session tokens, Super Admin access, personal Lead/conversation data,
payment/invoice evidence, ownership state, deployment/domain control, private assets/exports, AI
provider keys, and FAISS knowledge indexes.

Trust boundaries are browser-to-Web/API, customer Website-to-public API, provider-to-webhook, API-to-
DB/Redis/storage, worker-to-internal services, build/render sandbox-to-platform, and Admin-to-sensitive
operations.

## Authentication

### Email and password

- Passwords use current secure Argon2id parameters calibrated in production and encoded with algorithm
  metadata for rehash-on-login. Password length policy favors long passphrases and rejects known
  compromised values when an approved privacy-preserving service is configured.
- Signup persists an inactive account and verification challenge atomically. Codes are random,
  expire, are single-use, attempt-limited, securely digested, generation-scoped, and never logged.
- Resend applies visible cooldown, IP/account/device limits, invalidates older live generations, and
  avoids account-enumeration differences.
- Password reset uses random single-use token digests, short expiry, rate limits, session revocation,
  auth-epoch rotation, and security notification.

### Google OAuth

- Authorization uses state, nonce, PKCE where applicable, exact redirect URI, minimal scopes, secure
  transaction cookie/server record, and allowlisted post-login redirect.
- Callback verifies issuer, audience/client, signature/JWKS, nonce/state, time claims, provider subject,
  and verified email. User creation/account linking occurs in one transaction.
- Cancellation, denial, invalid callback, duplicate email, and provider outage leave no half-created
  active account. Successful provider identity proof does not trigger redundant Zylora OTP.

### Sessions

- Opaque high-entropy session tokens are stored only as hashes server-side and sent in `Secure`,
  `HttpOnly`, host-only, appropriate `SameSite` cookies.
- User and Admin have different cookie names, paths/hosts, audiences, idle/absolute lifetimes, and CSRF
  contexts. Session IDs rotate at authentication, privilege/security events, and risk escalation.
- Every request checks revocation, expiry, account status, audience, and auth epoch. Users can view and
  revoke devices/sessions; password/security changes can revoke all.
- Sensitive cookies never enter JavaScript/localStorage. Responses containing private data use
  `no-store`; private/admin pages use `noindex`.

## Super Admin isolation

Super Admin uses `admin.zylora.com` or an equivalently isolated route enforced by trusted host routing,
not a navigation toggle. The account is the sole `SUPER_ADMIN`; production readiness rejects zero or
multiple active rows. Controls include stronger password policy, short sessions, session/device
review, reauthentication for destructive/commercial actions where justified, brute-force defense,
WAF/rate limits, suspicious-login alerts, immutable audit, and network/access controls appropriate to
deployment.

A six-digit email OTP is not required every login. If stronger factors are later approved, WebAuthn/
phishing-resistant MFA is preferred and requires an ADR; it does not create more roles.

## CSRF, origin, CORS, and browser policy

- State-changing cookie-auth requests require a per-session CSRF token (synchronizer or signed
  double-submit design), exact Origin/Referer allowlist, and non-simple content type.
- CORS is deny-by-default and lists exact trusted origins; credentials never combine with wildcard
  origin. Public site endpoints have purpose-specific origin/host/rate controls rather than broad CORS.
- CSP is nonce/hash based, with no `unsafe-eval`, minimal approved third-party origins, framed preview
  isolation, `frame-ancestors`, and report monitoring. Security headers include HSTS after domain
  readiness, `nosniff`, Referrer-Policy, Permissions-Policy, and appropriate COOP/resource policies.
- Template previews and customer content render in a constrained origin/sandbox boundary so content
  cannot inherit Portal/Admin authority.

## Authorization and tenant isolation

HTTP routers call `AuthorizationService`/owner-scoped repositories. A resource ID is always resolved
with authenticated subject and current ownership in the same query/transaction. Child resources join
through Website ownership; clients never supply authoritative `owner_user_id` or tenant scope.

Rules:

- deny by default;
- `USER` can act only on the current owned resource and allowed state;
- `SUPER_ADMIN` endpoints use separate handlers and audit sensitive access/mutations;
- workers receive narrow job identity and re-resolve current authorization/state rather than inheriting
  stale browser claims;
- signed public site tokens map server-side to one active deployment/Website and rotate on transfer,
  unpublish, or compromise;
- object keys, FAISS paths, provider IDs, and database IDs alone never authorize access.

Automated IDOR matrices mutate every identifier across two Users and include list/search/count/export
side channels. Optional RLS is defense in depth after connection context is proven, never the sole
control.

## Abuse and cost controls

Rate limiting layers IP/network, account, session/device, site token, resource, and global provider
budgets. Sensitive endpoints use progressive delay/temporary lock and adaptive challenge. Alternate
auth, resend, reset, OAuth callback, AI editing, chatbot, Lead submission, uploads, ZIP, Template search,
domain verification, analytics ingestion, and public APIs receive distinct policies.

Production must fail safely when authoritative rate-limit state is unavailable: expensive/sensitive
commands may reject temporarily; public read traffic may use bounded local fallback. Limits return
actionable cooldown without revealing whether an account exists.

AI/embedding work has per-User/site quotas, maximum prompt/document/patch sizes, concurrency limits,
timeouts, provider budgets, cancellation, usage records, and circuit breakers. Model output remains
untrusted data.

## Input, output, and content safety

- Pydantic/request schemas reject unknown command fields, oversize bodies, invalid Unicode/control
  characters, and type coercions that weaken intent.
- ORM parameters prevent SQL injection; raw SQL is reviewed and parameterized.
- User-visible content is escaped by default. Structured rich text uses an allowlisted AST and mature
  sanitizer. No stored arbitrary HTML/script/event handlers/CSS.
- URLs are normalized and restricted by scheme/host/purpose. Server-side fetches block loopback,
  private/link-local/cloud-metadata ranges, redirects to disallowed destinations, DNS rebinding, large
  responses, and unsupported MIME—preventing SSRF.
- Errors expose stable codes and correlation IDs, not stack traces, SQL, filesystem paths, provider
  payloads, or existence of unauthorized objects.

## Upload and asset security

Uploads use authenticated signed intents bound to User/Website, expected maximum bytes and type, short
expiry, and unique object key. Completion rechecks byte count, magic/MIME, extension, dimensions,
decoder safety, malware result, checksum, and authorization before activation.

Images are decoded/re-encoded, metadata stripped where appropriate, and variants generated in bounded
workers. Archives are rejected for ordinary assets. SVG is disallowed initially or sanitized with a
strict reviewed policy in a later ADR. Private assets stay private; public publication copies only
approved processed variants to immutable public keys.

## Template, renderer, and build isolation

Template schema forbids executable scripts, arbitrary imports, raw CSS/HTML, unrestricted iframes,
and remote data loaders. Registry components are source-reviewed platform code. Validation/build runs
with no production credentials, read-only source, bounded CPU/memory/time/file count, isolated scratch,
restricted network, and output scanning.

Preview origins cannot access User/Admin cookies. Export generation uses server-created normalized
paths, blocks traversal/absolute paths/symlinks/device names, limits compression ratio/entry count,
scans output, and verifies the manifest contains no secrets or cross-Website data.

## Payment and webhook security

- Raw webhook bytes are bounded and signature-verified before business parsing.
- Provider event/payment IDs are unique and replay protected; signature timestamp windows apply where
  provider semantics permit.
- Local payable amount, currency, purpose, owner, and metadata must match trusted provider evidence.
- Browser callbacks are never payment proof. Reconciliation is server-to-provider and audited.
- Paid capabilities derive only from committed trusted states; duplicate/out-of-order/conflicting
  events are idempotent or quarantined.
- Secret keys are server-only, environment-separated, rotated through secret management, and redacted
  structurally from logs.

## FAISS and chatbot isolation

Every extraction/chunk/index/query carries server-resolved Website, owner, published version, and index
identity. Manifest and DB relationships must match; artifact checksums and embedding dimension/model
are verified before load. The query service accepts no index path or owner from the caller and performs
no global fallback.

Chat prompts delimit retrieved content as untrusted, prohibit tool/provider secret access, and enforce
output/content policy. Prompt injection cannot expand retrieval scope. Conversations and Lead context
follow consent/retention rules. Tests include malicious content explicitly asking for another Website's
data and path/manifest substitution.

## Secrets and cryptography

Secrets live in a managed secret store or approved local development mechanism, never Git, database
business settings, browser bundles, logs, ZIPs, screenshots, or generated docs. Production validates
minimum entropy, rejects defaults/debug auth, and supports versioned rotation with overlap where needed.

Use maintained platform/library primitives for password hashing, token generation, HMAC, encryption,
TLS, and signature verification. Application-level encryption uses envelope/key-version metadata and
authenticated encryption; no custom cryptography. Encryption keys and data backups have separate
access controls.

## Logging, audit, and privacy

Structured logs use request/correlation/job IDs and safe categorical fields. A centralized redaction
layer removes cookies, authorization, passwords, OTPs, reset/session tokens, OAuth codes/tokens,
payment credentials/raw sensitive payloads, Lead message bodies where unnecessary, signed URLs, and
secrets.

Immutable audit captures actor, action, resource, redacted old/new values, reason, time, IP, and
correlation for ownership, commercial configuration, credits, Template lifecycle, campaign/Blog send,
account administration, payments/exports/subscriptions, and exceptional access. Audit integrity and
retention are monitored; audit is not an unrestricted copy of personal data.

Consent categories distinguish essential, analytics, and marketing. Transactional email is separate
from marketing suppression. Data retention/deletion follows the model in `DATA_MODEL.md`; account
export cannot provide deployable Website source for free.

## Dependency and supply-chain controls

- Lockfiles and exact production resolution are committed; automated dependency/license/vulnerability
  scans run in CI.
- Base images are pinned by digest for releases, minimally privileged, scanned, and rebuilt for fixes.
- CI uses least-privilege short-lived credentials, protected environments, artifact provenance, and
  no secrets on untrusted pull-request jobs.
- Migrations/build outputs are reviewed artifacts. Production deploys only from passing protected
  commits and verifies health before promotion.

## Network and runtime hardening

- TLS everywhere; database/Redis/storage are private-network or tightly allowlisted.
- Containers/processes run non-root, read-only filesystem where practical, bounded resources, dropped
  capabilities, dedicated scratch, and separate Web/API/worker identities.
- Database roles separate migration, application, read-only operations, and backup duties. API cannot
  bypass audit/ledger protections casually.
- Internal worker endpoints use mTLS or rotated service identity and network policy.
- WAF/bot protection complements—not replaces—application authorization/rate limits.

## Security test gates

Before release, automated/manual coverage includes:

- unauthorized/expired/revoked User and Admin sessions, cookie audience confusion, CSRF and CORS;
- horizontal access across Website, version, asset, domain, deployment, Lead, analytics, billing,
  export, chatbot, and FAISS resources;
- brute force, resend/reset/OAuth alternative paths, account enumeration, lock recovery;
- stored/reflected XSS, HTML/CSS/script injection, unsafe URL/redirect, SSRF and CSP;
- malicious MIME/polyglot/oversize/decompression/upload, Template component, renderer sandbox, ZIP
  traversal/symlink/bomb/secrets;
- webhook signature, replay, duplicate/out-of-order/conflict, wrong amount/currency/purpose;
- concurrent publish, transfer, subdomain, Lead/credit, export, and admin catalog operations;
- prompt injection and cross-Website retrieval/index artifact substitution;
- secret/log/bundle/export scans and dependency/container scans.

P0/P1 findings block phase/release completion. Fixes add regression tests at the canonical boundary.

## Security incident priorities

1. Contain affected credentials/routes/access epochs without deleting evidence.
2. Preserve audit/provider/log evidence with privacy controls.
3. Revoke/rotate sessions, tokens, provider keys, object URLs, and public site tokens as scoped.
4. Restore known-good code/data/config and verify invariants.
5. Notify affected parties according to applicable policy/law without unsupported claims.
6. Complete root-cause analysis and regression controls before normal operation.
