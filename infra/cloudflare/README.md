# Cloudflare security boundary

This Terraform root creates the production Turnstile widget, Cloudflare Managed
and OWASP WAF rules, method restrictions, and route-specific rate limits. It
does not contain credentials and intentionally does not output the Turnstile
secret because Terraform state contains sensitive provider material.

Use Terraform 1.14.6 and Cloudflare provider 5.22.0. Supply `CLOUDFLARE_API_TOKEN`,
`TF_VAR_account_id`, `TF_VAR_zone_id`, and `TF_VAR_turnstile_domains` through the
deployment secret manager. The token needs the minimum account Turnstile Sites
write and zone WAF write/read permissions. Store state in an encrypted remote
backend with access logging and locking; never commit a `.tfstate` file.

Run `terraform init`, `terraform fmt -check`, `terraform validate`, inspect
`terraform plan`, then apply through the production deployment workflow. After
apply, place the public site key in `TURNSTILE_SITE_KEY` and retrieve the secret
directly into `TURNSTILE_SECRET_KEY`. Do not copy the secret into a frontend
environment variable, issue tracker, log, or Terraform output.

The rate-limit rules include authenticated AI Builder generation commands and status/artifact
polling. Application responses under `/api/v1/` remain `private, no-store`; validate the live
zone separately because static Terraform checks do not prove deployment.
