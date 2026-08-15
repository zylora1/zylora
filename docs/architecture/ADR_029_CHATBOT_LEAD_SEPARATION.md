# ADR-029: Separate chatbot Q&A from Lead capture

Status: **Accepted**  
Date: **2026-08-13**

## Context

The original Phase 10 public contract allowed a chatbot conversation to invoke the same transactional
Lead service used by Website forms. That coupling made an informational Q&A interaction capable of
crossing the Lead consent boundary and indirectly causing credit deductions, analytics conversions,
email delivery, and WhatsApp delivery.

The product owner approved a focused change: the chatbot is an information assistant only, while the
published Website enquiry form is the sole anonymous Lead command surface.

## Decision

- Public chatbot routes can start a Website-scoped conversation and answer messages only.
- The chatbot prompt must use Website-scoped published knowledge, refuse unsupported claims, and must
  not solicit contact details, qualify prospects, promise follow-up, or trigger Lead side effects.
- The chatbot-specific Lead route and service command are removed.
- `LeadService` accepts only explicit `FORM` submissions. Historical `CHATBOT` source values and
  conversation `lead_id` data remain readable for backward compatibility; no destructive migration
  is performed.
- Published Websites reuse their validated `LEAD_FORM` component. One platform-authored visitor
  controller makes it eligible after at least ten visible seconds, defers while another modal or the
  chatbot is active, and uses session storage to cap automatic display after dismissal or success.
- Manual enquiry actions remain available immediately and do not transfer chatbot content into the
  form.
- Existing host resolution, Turnstile verification, Cloudflare rate limiting, idempotency, Lead
  credits, tenant association, analytics, email, WhatsApp, and Lead management remain on the form
  path.

## Consequences

Chatbot conversations can no longer create Leads or Lead notification work. The form is the explicit
consent boundary. Existing Lead records are preserved, and legacy source analytics may remain
readable, but all new Leads are form-attributed. No database migration is required.
