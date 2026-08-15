# ADR 028: Website-scoped document RAG and Twilio WhatsApp lead notifications

Status: accepted

Date: 2026-08-13

Authority: the user-approved Twilio WhatsApp, RAG chatbot, and knowledge-document amendment

## Context

Phase 10 already established one Chatbot per Website, website/owner-scoped FAISS metadata and
chunks, durable index artifacts, the canonical Lead transaction, notification quotas, and
outbox/Celery delivery. The approved amendment adds private customer documents and business-owner
WhatsApp alerts without introducing another chatbot, vector database, Lead store, billing counter,
job system, or portal.

## Decision

- `KnowledgeSource` is PostgreSQL-authoritative and belongs to one Website and its current owner.
  Original and extracted artifacts use private object storage under generated website/owner/source
  keys. Original filenames are display metadata only and are never filesystem paths.
- Upload requests validate extension, MIME, signatures, size, decoding, DOCX archive expansion,
  active content, and filename safety, then store privately and commit an ID-only outbox event.
  Scanner, extraction, embedding, and rebuild work runs in the existing worker.
- Website content and READY document sections are chunked with source metadata. Embeddings use the
  existing provider boundary. Each generation builds a new website/owner-scoped FAISS artifact,
  verifies model, dimension, checksum, and searchability, then atomically swaps the active pointer.
- PostgreSQL metadata, published Website versions, original documents, and extracted artifacts are
  authoritative. FAISS is reproducible and durable, never authoritative local process state. API
  processes keep only a bounded cache keyed by Website, active index, and checksum.
- Rebuilds are zero-downtime: an old active index remains queryable while the Chatbot is INDEXING.
  Failed rebuilds restore ACTIVE when an old pointer exists, and a late older generation cannot
  replace a newer active generation.
- Public and owner-preview questions use the same `ChatbotService`. Retrieved text is untrusted
  data inside a constrained prompt. Low-relevance retrieval returns the stable grounded fallback.
  Source references expose titles/page numbers or public page paths, never object keys or IDs.
- The existing Lead transaction remains canonical. It commits the Lead, one Lead-credit debit,
  analytics, in-app notification, email intent, and any entitled WhatsApp quota reservation before
  provider delivery. Twilio failure can never roll back or erase the Lead.
- `WhatsAppProvider` isolates provider behavior. `TwilioWhatsAppProvider` sends approved Content
  SIDs with bounded variables and WhatsApp E.164 addresses. Durable notification rows and outbox
  jobs enforce idempotency, bounded retry, safe errors, and Message SID persistence.
- Owner phone numbers are normalized, encrypted, hashed for duplicate detection, and masked in API
  responses. Enabling requires entitlement and explicit consent. The setting is user-level and is
  managed inside the existing Website editor, not a separate dashboard.
- The callback URL is derived only from configured public HTTPS origin and the fixed route. Official
  Twilio signature validation runs against the exact URL and all form parameters; forwarded headers
  are not trusted. Callback events are deduplicated and monotonic.

## Consequences

Knowledge ingestion and WhatsApp remain disabled by default. Production activation requires S3-
compatible private storage, ClamAV, the approved embedding/generation provider, a running Celery
worker/beat, Twilio sender onboarding, approved Content templates, secrets, and a public HTTPS
callback. Tests use deterministic embeddings, a test scanner, and fake providers and cannot be
interpreted as evidence of live Twilio or Meta approval.
