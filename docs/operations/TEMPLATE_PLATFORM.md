# Template platform operations

Run `npm run seed:templates` after migrations and after an active Super Admin exists. The seed is
idempotent: it creates the curated identities only when absent and uses the same validate, approve,
and publish domain service as the Admin API. It never creates an account or bypasses validation.

Template raster assets require configured S3-compatible object storage. Uploads accept only PNG,
JPEG, or WebP, enforce byte/pixel limits, decode and verify the raster, strip metadata through a
fresh WebP encoding, and store at a checksum-derived immutable key. SVG, HTML, archives, invalid
base64, polyglots, and failed images are rejected before storage. No real credentials belong in the
repository.

Cloudflare production configuration has separate IP/data-center counters:

- `GET /api/v1/templates*`: 90 requests/minute for catalogue/detail/preview reads;
- `POST /api/v1/templates/*/instantiate`: 10 requests/minute with a 10-minute mitigation window.

The instantiation route additionally requires an active User session, exact User origin, JSON
content type, and the session-bound CSRF token. It does not use Turnstile because it is a normal
authenticated product command. Apply `infra/cloudflare` with production account/zone credentials,
then smoke-test both counters in Cloudflare Security Events before launch.
