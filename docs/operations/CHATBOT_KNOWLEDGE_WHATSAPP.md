# Chatbot knowledge and Twilio WhatsApp operations

Status: repository implementation complete; external providers disabled by default

Architecture decision: `docs/architecture/ADR_028_CHATBOT_KNOWLEDGE_TWILIO.md`

## Boundaries

- Each knowledge source, chunk, index generation, conversation, and Lead is scoped by Website and
  owner. No global user FAISS index exists.
- PostgreSQL and private object storage are authoritative. Worker disks and Redis are not.
- Public visitors can ask questions and receive generated answers; they cannot download source
  documents or discover object keys, database IDs, embeddings, or signed URLs.
- Uploaded text is untrusted data. It is never treated as model policy or executable content.
- WhatsApp sends business-owner Lead alerts only. This release does not implement inbound WhatsApp
  chat or visitor marketing.

## Server configuration

All values are server-only. Keep secrets in the deployment secret manager and never use a
`NEXT_PUBLIC_` prefix.

| Variable | Safe default | Required to enable |
| --- | --- | --- |
| `KNOWLEDGE_INGESTION_ENABLED` | `false` | `true` only after storage, worker, scanner, and AI checks |
| `KNOWLEDGE_MAX_FILE_BYTES` | `15728640` | deployment limit |
| `KNOWLEDGE_MAX_DOCUMENTS_PER_WEBSITE` | `25` | product/plan limit |
| `KNOWLEDGE_MAX_EXTRACTED_CHARACTERS` | `500000` | extraction bound |
| `KNOWLEDGE_MAX_PDF_PAGES` | `300` | PDF bound |
| `KNOWLEDGE_MAX_DOCX_ENTRIES` | `2000` | archive-entry bound |
| `KNOWLEDGE_MAX_DOCX_UNCOMPRESSED_BYTES` | `52428800` | archive-expansion bound |
| `DOCUMENT_SCANNER_PROVIDER` | `test` locally | `clamav` in staging/production |
| `CLAMAV_HOST`, `CLAMAV_PORT` | local placeholders | reachable private scanner |
| `CHATBOT_EMBEDDING_MODEL` | configured model | approved model |
| `CHATBOT_EMBEDDING_DIMENSION` | `1536` | exact provider dimension |
| `CHATBOT_GENERATION_MODEL` | configured model | approved model |
| `CHATBOT_RETRIEVAL_LIMIT` | `4` | bounded 1-10 |
| `CHATBOT_RELEVANCE_THRESHOLD` | `0.2` | staged relevance calibration |
| `CHATBOT_MAX_CONTEXT_CHARACTERS` | `12000` | bounded retrieved context |
| `CHATBOT_CHUNK_CHARACTERS` | `900` | section chunk ceiling |
| `WHATSAPP_ENABLED` | `false` | `true` only after Twilio readiness |
| `TWILIO_ACCOUNT_SID` | empty | secret-manager reference |
| `TWILIO_AUTH_TOKEN` | empty | secret-manager reference |
| `TWILIO_WHATSAPP_FROM` | empty | approved sender, unless Messaging Service is used |
| `TWILIO_MESSAGING_SERVICE_SID` | empty | optional alternative sender boundary |
| `TWILIO_LEAD_TEMPLATE_CONTENT_SID` | empty | approved Lead Content SID |
| `TWILIO_TEST_TEMPLATE_CONTENT_SID` | empty | approved test Content SID |
| `TWILIO_STATUS_CALLBACK_BASE_URL` | empty | public API HTTPS origin, without route suffix |

Knowledge ingestion additionally requires `STORAGE_PROVIDER=s3`, valid private S3-compatible
credentials, `AI_PROVIDER=openai`, and `OPENAI_API_KEY`. The Settings model rejects enabled
staging/production configurations that use memory storage, the test scanner, missing provider
credentials, missing Twilio fields, or a non-HTTPS callback.

## Twilio template contract

The Lead template uses Content variables:

1. Website display name, at most 120 characters.
2. Lead name, at most 120 characters.
3. Lead email or `Not provided`, at most 200 characters.
4. Whitespace-normalized Lead enquiry, at most 500 characters.

The test template accepts the same four positions. Template wording and translations are managed in
Twilio Content Template infrastructure; application code sends the approved Content SID and does
not reproduce business-initiated template text. Approval of a test template does not prove that a
production sender is onboarded.

Configure Twilio's Message status callback as:

`https://<public-api-host>/api/v1/webhooks/twilio/whatsapp/status`

The application validates `X-Twilio-Signature` with Twilio's official validator against the exact
configured public URL plus request query and form parameters. The callback base must match what
Twilio signs. Do not derive it from `Host`, `Forwarded`, or `X-Forwarded-*` headers.

## Document sequence

```text
authenticated upload
  -> owner/Website lock and document-count check
  -> extension + MIME + signature + archive + size validation
  -> generated private object key
  -> KnowledgeSource(UPLOADED) + ID-only outbox event
  -> SCANNING
  -> PROCESSING (extract paragraphs/pages/headings/tables)
  -> READY + private extracted artifact
  -> new index generation REQUESTED
  -> EXTRACTING -> EMBEDDING -> BUILDING -> VALIDATING
  -> atomic ACTIVE pointer swap
```

Retryable scanner outages return the source event to `PENDING` with bounded exponential backoff.
Malformed, infected, unreadable, or unsafe documents become `FAILED` with a safe code/message.
Manual retry increments the source version. Deletion immediately hides the source, asynchronously
removes original/extracted objects, and builds a replacement index without the deleted source.

Image-only PDFs do not invoke OCR. They fail with `No machine-readable text was found in this PDF.`
Legacy DOC, HTML, JavaScript, executables, arbitrary archives, encrypted DOCX, macro/ActiveX,
embedded objects, path traversal entries, invalid UTF-8, and zero-byte files are rejected.

## Query sequence and recovery

```text
trusted published Website resolution
  -> active website/owner/index verification
  -> query embedding model/dimension check
  -> checksum-verified FAISS artifact (bounded process cache)
  -> top-k retrieval + relevance threshold
  -> bounded untrusted context
  -> constrained generation
  -> grounded answer or stable insufficient-knowledge fallback
```

The cache key includes Website ID, active index ID, and checksum. A new generation cannot reuse a
stale artifact. While a replacement is `INDEXING`, the previous active index remains queryable. A
failed replacement restores chatbot state to `ACTIVE` when the prior pointer exists. A late older
generation is marked `SUPERSEDED` instead of replacing a newer generation.

For recovery:

1. Inspect KnowledgeSource, ChatbotKnowledgeIndex, and OutboxEvent safe states; do not inspect raw
   customer text unless an approved incident procedure requires it.
2. Restore scanner/storage/provider reachability.
3. Retry a FAILED source through the owner endpoint, or enqueue a new index generation from the
   canonical Website/source metadata.
4. Verify manifest website, owner, Website version, source versions, model, dimension, checksum,
   chunk count, and a smoke search before activation.
5. Let object lifecycle remove unreferenced failed-generation artifacts; never adopt them manually.

## Lead and WhatsApp sequence

```text
Lead transaction commits
  -> exactly one Lead credit debit
  -> in-app notification + analytics
  -> owner email intent
  -> entitled WhatsApp quota reservation + WhatsApp outbox intent
  -> worker creates/fetches idempotent notification
  -> Twilio accepted Message SID -> SENT
  -> signed callbacks -> DELIVERED -> READ
```

Email and WhatsApp use separate durable intents. A Twilio outage cannot roll back the Lead or email
intent. Retryable Twilio/network failures use persisted attempts and backoff; terminal failures
become `FAILED` with safe details. Duplicate worker delivery reuses the notification idempotency
key. Duplicate callbacks reuse a digest; lower-ranked out-of-order states cannot move delivery
backward.

Phone numbers are normalized to E.164, encrypted at rest, and exposed only as a last-four mask.
Enabling requires explicit owner consent and the existing `whatsapp_monthly_notifications`
entitlement. Quota reservation remains the canonical notification quota ledger operation.

## Staging activation

1. Apply migrations through `20260823_0018` and confirm exactly one Alembic head.
2. Provision private versioned object storage and lifecycle rules for unreferenced artifacts.
3. Deploy and health-check ClamAV on a private network path.
4. Configure approved embedding/generation models and secrets; keep ingestion disabled.
5. Deploy API, worker, and Celery beat. Confirm chatbot and Lead-channel dispatch schedules.
6. Complete Twilio account and WhatsApp sender onboarding/registration.
7. Create and obtain approval for Lead and test Content templates; record their Content SIDs.
8. Configure the public HTTPS callback origin and Twilio status callback route.
9. Add secrets/configuration, still with both feature flags false, and deploy.
10. Set `KNOWLEDGE_INGESTION_ENABLED=true` and `WHATSAPP_ENABLED=true` in staging only.
11. Run `npm run chatbot-whatsapp:preflight:staging` and API readiness.
12. Upload TXT, Markdown, textual PDF, and DOCX fixtures; verify READY, source attribution, deletion,
    failed rebuild preservation, and two-Website isolation.
13. Send the explicitly requested test notification to an authorized staging number. Verify Message
    SID and signed SENT/DELIVERED/READ callbacks. This is not production readiness by itself.
14. Submit a staging Lead and verify Lead persistence, one credit debit, email intent, WhatsApp
    quota reservation, one notification, and safe behavior during a forced Twilio failure.

## Production activation

1. Review staging evidence, approved sender/template status, retention, privacy, rate limits, alerts,
   and rollback ownership.
2. Apply the migration with both feature flags false; deploy API/worker/beat and verify readiness.
3. Configure production-only secrets, approved Content SIDs, sender or Messaging Service, and the
   production HTTPS callback origin.
4. Enable document ingestion for a controlled internal account and run
   `npm run chatbot-whatsapp:preflight:production`.
5. Verify one production document lifecycle and RAG query without customer-sensitive test data.
6. Enable WhatsApp for a controlled entitled owner who explicitly consents; send one opt-in test.
7. Verify the Twilio Message SID and signed callback lifecycle, then enable the wider entitlement
   rollout through the existing plan data.
8. Monitor outbox age, scan/index failures, no-context rate, provider failures, callback rejection,
   quota invariants, duplicate suppression, latency, and storage growth.

## Rollback

- Set `WHATSAPP_ENABLED=false` to stop provider sends and make the webhook unavailable. Leads and
  email continue. Do not delete notification evidence.
- Set `KNOWLEDGE_INGESTION_ENABLED=false` to stop new uploads. Existing active indexes remain
  queryable while the API deployment remains compatible.
- Roll back application code only to a version compatible with migration 0017. Do not downgrade a
  shared production database while rows exist without an approved data-retention plan.
- If a new index is bad, keep or restore the prior active pointer through the audited domain
  recovery procedure; never overwrite FAISS files in place.

## Observability and privacy

Safe events include `knowledge.uploaded`, scan/index state and failure codes, `chatbot.query`,
`chatbot.no_context`, `whatsapp.enqueued`, send outcome, callback outcome, and invalid signature.
Logs and traces must never contain document bodies, complete prompts, embedding vectors, phone
numbers, Lead enquiry text, object keys, Twilio Auth Token, OpenAI key, or signed URLs. Operational
dashboards expose counts/states only; Super Admin does not browse customer document content.

Live provider tests are opt-in operations. Repository tests use fakes and must never be pointed at a
paid or production Twilio account.
