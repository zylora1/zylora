# Phase 4 Template platform verification

The Phase 4 gate covers both catalogue governance and the authoritative instantiation amendment.

## Automated coverage

- document schema, registry, checksum stability, executable-content rejection, requirement
  recomputation, Page hierarchy, cycle/missing-parent/multiple-home rejection;
- raster-only upload MIME enforcement, decode/verify/re-encode, metadata stripping, immutable keys,
  SVG/archive/polyglot rejection;
- signed opaque cursor tampering and filter binding;
- PostgreSQL Template create → validate → approve → publish → public catalogue/preview → deprecate;
- current-validation enforcement and published-only reads;
- 30-page Template validation and instantiation into three Drafts across two Users;
- multiple Drafts, fresh Page IDs, parent remapping, nested path resolution, exactly one home,
  source immutability, cross-User isolation, cross-Website parent rejection, cycle rejection, and
  database duplicate-home rejection;
- User and Super Admin host isolation, catalogue search/filter, sandboxed responsive preview,
  selection → Draft list, lifecycle UI, desktop/mobile Chromium, and accessibility scans.

No test creates a plan, subscription, payment, collaborator, or published Website. This is an
acceptance condition rather than missing setup.

## Visual sampling

The representative Haven Health preview is sampled at desktop, 768px tablet, and mobile browser
projects. The preview iframe has an empty sandbox permission set and an embedded deny-by-default
CSP. Browser assertions confirm both cookie and local-storage access raise a security error.

The Super Admin lifecycle is sampled on desktop and mobile with measured API state only. Empty and
loading states remain honest; the UI does not fabricate published Templates or Drafts.
