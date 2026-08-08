# Entitlements, pricing, and payment boundary

Status: **Frozen; production payment provider intentionally unselected**

## Canonical rule chain

```text
Structured WebsiteVersion
        ↓
WebsiteRequirementService
        ↓
RequirementSet + evidence
        ↓
EntitlementService against effective PlanCatalog
        ↓
Eligibility for all four Plans + exact reasons
        ↓
PlanRecommendationService
        ↓
Existing Subscription reuse OR eligible choice/upgrade
        ↓
Trusted Payment/Subscription state
        ↓
PublishEligibilityService
```

Frontend and workers consume this evaluated result. They do not implement plan-name branches,
recalculate price, or override ineligibility.

## Capability registry

Entitlement keys are versioned definitions, not arbitrary admin strings. Each definition specifies
type, unit, comparison rule, safe default, requirement extractor, display copy, and compatibility
behavior. Initial conceptual keys include:

- `max_pages` (integer maximum);
- `can_publish` (boolean);
- `can_use_custom_domain` (boolean);
- `can_use_advanced_carousel`, `can_use_advanced_animation`, and other registered component
  capabilities (boolean);
- `included_lead_credits` (integer grant policy, separate from live ledger balance);
- bounded operational limits such as storage or AI usage only when explicitly product-approved.

Missing capability defaults fail closed for paid/sensitive behavior and produce an operator-visible
configuration error. Capability names are not rendered as plan names and never encode ordering.

## Requirements

`WebsiteRequirementService` receives immutable WebsiteVersion and exact component registry version.
It deterministically computes counts and capabilities with evidence paths, for example:

```json
{
  "registry_version": "1.0.0",
  "website_version_id": "…",
  "requirements": {
    "page_count": 7,
    "custom_domain": true,
    "capabilities": ["advanced_carousel"]
  },
  "evidence": [
    {"key": "page_count", "value": 7, "paths": ["/pages"]},
    {"key": "advanced_carousel", "value": true, "paths": ["component_gallery"]}
  ],
  "checksum": "…"
}
```

Stored Template requirements are advisory/cache only. Publish recomputes from the selected immutable
WebsiteVersion so a client cannot omit a feature.

## Eligibility

Eligibility applies each registered requirement to each of exactly four plans in the effective
catalog. It returns:

- `eligible` boolean;
- every stable reason code and human-safe explanation;
- current value, allowed value, and evidence where safe;
- whether current subscription already satisfies the plan;
- evaluation inputs, versions, checksum, and expiry.

Ineligible plans stay visible, greyed and unselectable. Examples:

- `PAGE_LIMIT_EXCEEDED`: “This Website has 7 pages; this plan allows up to 5.”
- `CUSTOM_DOMAIN_NOT_INCLUDED`: “This plan supports a Zylora subdomain, not a custom domain.”
- `COMPONENT_NOT_INCLUDED`: names the relevant customer-facing feature.

Plan recommendation selects the lowest-cost/smallest-capability eligible option by explicit catalog
policy, with deterministic tie breakers and an explanation. Recommendation never makes an ineligible
plan selectable and never optimizes secretly for revenue.

## Exactly four plans

Commercial editing uses immutable `PlanCatalog` snapshots. A catalog becomes publishable only when:

- it has slots 1 through 4 exactly once;
- each visible plan has valid display content, price(s), currency/interval, and required entitlement
  keys;
- prices have no overlapping effective ranges;
- capability types match the registry;
- at least one plan can satisfy the platform baseline and catalog consistency checks;
- any removal/change impact on current subscriptions is explained and migration behavior defined.

Publishing the new catalog is an atomic pointer/effective-time switch. No request can observe three or
five plans during an admin edit. Plan names, prices, entitlements, and order remain data—not source
constants.

## Subscription reuse and change

The effective User subscription is resolved from trusted local state and its immutable catalog/plan
snapshot. If its entitlements meet current Website requirements, publish proceeds without showing
pricing. If not, evaluation returns only valid upgrade choices while displaying all four plans and
their reasons.

Downgrade/cancellation behavior does not break a current live Website silently. A commercial policy
must define end-of-period effects, grace state, User notification, and any controlled unpublish
workflow. The implementation never immediately destroys customer content.

## Price snapshots

Every checkoutable record stores:

- local payable ID/type and owner;
- catalog/plan/price or platform-setting version;
- amount minor, currency, interval, quantity, discount/tax inputs and computed totals;
- human-facing line description;
- created/effective times.

Checkout adapters receive this server-generated snapshot. Webhook handling compares provider evidence
against it. Later admin changes affect only future purchases and do not mutate subscriptions, invoices,
payments, or ExportPurchases already created.

## Payment port

The provider-neutral application interface is intentionally small:

```python
class PaymentProvider(Protocol):
    def create_checkout(self, request: CheckoutRequest) -> CheckoutSession: ...
    def verify_payment(self, reference: ProviderPaymentReference) -> VerifiedPayment: ...
    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> VerifiedWebhook: ...
    def reconcile(self, reference: ProviderPaymentReference) -> VerifiedPayment: ...
    def refund(self, request: RefundRequest) -> VerifiedRefund: ...  # only if supported
```

Application types contain exact money, local payable metadata, stable idempotency key, return URLs
from allowlisted server configuration, and provider evidence hashes. Provider SDK objects never leak
into domain tables, API responses, or unrelated modules.

## Provider selection gate

Phase 0 does not approve a payment provider. V1's provider code and environment names do not confer
approval. Before a production adapter is implemented, a recorded decision must specify:

- supported countries, currencies, recurring billing and tax/invoice responsibilities;
- checkout/authentication UX, capture/settlement semantics, and refund support;
- signing algorithm, raw webhook requirements, event ID behavior, replay window, and IP/network advice;
- idempotency semantics, API timeout/retry contract, rate limits, and reconciliation endpoints;
- secret rotation, sandbox/staging separation, monitoring, support escalation, and data retention;
- legal/commercial approval and operational owner.

Until then, only a deterministic in-process test adapter may model scenarios. It must be impossible to
enable in production, and it never presents static fake data as persistence.

## Trusted payment processing

1. Server creates the local payable and Payment in `CREATED` from current backend data.
2. Adapter creates checkout using a stable idempotency key; local state moves to `PENDING`.
3. Browser return is informational only and displays pending/reconciliation state.
4. Signed webhook or explicit server verification supplies provider evidence.
5. Service verifies signature/raw body, event uniqueness, provider payment/order/customer, expected
   amount/currency, purpose metadata, and allowed transition.
6. In one transaction it records event evidence, advances Payment/payable/subscription state, audits,
   and emits an outbox event.
7. Duplicates return the original processing outcome. Ambiguity schedules reconciliation.
8. Capability becomes available only from the committed trusted local terminal state.

Webhook endpoints never trust parsed body before signature verification, callback query parameters,
client status flags, screenshots, or merely existing provider order IDs.

## Replay and conflict handling

- Unique provider event ID blocks duplicate event processing.
- Raw body hash and signature timestamp detect altered/replayed payloads.
- Provider payment ID is bound to one local payable and expected purpose.
- Terminal state transitions are monotonic unless an explicit refund/dispute path exists.
- A conflicting terminal event is quarantined for reconciliation; it does not guess.
- Reconciliation reads provider state and records new evidence rather than overwriting prior events.
- Entitlement grants and export generation have their own unique idempotency keys so a duplicated
  trusted payment cannot grant twice or generate uncontrolled artifacts.

## Website ZIP export

Export price is a versioned Super-Admin platform setting with amount, currency, active/effective time.
Creating an ExportPurchase snapshots price and exact WebsiteVersion. Payment purpose is `EXPORT` and
is cryptographically/provider-metadata bound to that purchase.

Generation checks again that:

- Payment is trusted paid and matches purchase amount/currency;
- requestor remains current owner or an approved post-transfer policy explicitly applies;
- WebsiteVersion/checksum matches purchase;
- no ready unexpired artifact already exists;
- generator and schema versions are supported.

Account/privacy export has no Payment or ExportPurchase relationship and uses a separate generator and
storage prefix. Its schema prohibits deployable files.

## Failure behavior

- Provider unavailable before checkout: payable remains retryable; no capability.
- Browser returns but webhook delayed: UI shows pending and offers bounded reconcile; no capability.
- Duplicate webhook: original result returned; no duplicate invoice/entitlement/export.
- Webhook verified but notification fails: commercial state remains correct; notification retries.
- DB fails after provider capture before commit: reconciliation finds the provider payment using local
  idempotency/reference and completes once.
- Refund: access consequences follow explicit product policy and state machine; history is retained.

## Required automated tests

- four-plan catalog validation and atomic switch;
- requirement extraction fixtures and evidence;
- every entitlement operator/type, missing keys, and boundary values;
- deterministic recommendation and existing subscription reuse;
- price snapshot immutability;
- frontend success/callback spoof attempts;
- invalid signature, wrong amount/currency/purpose, event replay, duplicate webhook, reordered events,
  conflicting terminal events, timeout, and reconciliation;
- concurrent webhook/reconcile and duplicate entitlement/export grants;
- failed payment prevents ZIP generation/download;
- account export cannot reference ExportPurchase, Website ZIP generator, or deployable manifest.
