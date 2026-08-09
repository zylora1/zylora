output "turnstile_site_key" {
  description = "Public site key to configure as TURNSTILE_SITE_KEY."
  value       = cloudflare_turnstile_widget.authentication.sitekey
}

# The secret is intentionally not output. Retrieve it securely from Cloudflare
# and inject it directly into the server-side secret manager.
