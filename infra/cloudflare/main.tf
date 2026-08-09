locals {
  authentication_paths = [
    "/api/v1/auth/signup",
    "/api/v1/auth/login",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/resend-verification",
    "/api/v1/auth/password-reset/request",
    "/api/v1/auth/password-reset/confirm",
    "/api/v1/auth/google/start",
    "/api/v1/admin/auth/login",
  ]
  auth_path_expression = join(" ", [for path in local.authentication_paths : format("%q", path)])
}

resource "cloudflare_turnstile_widget" "authentication" {
  account_id      = var.account_id
  domains         = var.turnstile_domains
  mode            = "managed"
  name            = var.turnstile_widget_name
  clearance_level = "no_clearance"
  ephemeral_id    = false
  offlabel        = false
  region          = "world"
}

resource "cloudflare_ruleset" "managed_waf" {
  zone_id     = var.zone_id
  name        = "Zylora managed application protections"
  description = "Cloudflare Managed and OWASP Core rulesets for public Zylora traffic"
  kind        = "zone"
  phase       = "http_request_firewall_managed"

  rules = [
    {
      action      = "execute"
      expression  = "true"
      description = "Cloudflare Managed Ruleset"
      enabled     = true
      action_parameters = {
        id = "efb7b8c949ac4650a09736fc376e9aee"
      }
    },
    {
      action      = "execute"
      expression  = "true"
      description = "Cloudflare OWASP Core Ruleset"
      enabled     = true
      action_parameters = {
        id = "4814384a9e5d4991b9815dcfc25d2f1f"
        overrides = {
          sensitivity_level = "medium"
        }
      }
    },
  ]
}

resource "cloudflare_ruleset" "custom_waf" {
  zone_id     = var.zone_id
  name        = "Zylora application boundary rules"
  description = "Reject invalid methods and common secret/scanner probes before origin"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  rules = [
    {
      action      = "block"
      expression  = "(http.request.uri.path in {${local.auth_path_expression}} and http.request.method ne \"POST\")"
      description = "Authentication command routes accept POST only"
      enabled     = true
    },
    {
      action      = "block"
      expression  = "http.request.uri.path in {\"/.env\" \"/.git/config\" \"/wp-login.php\" \"/xmlrpc.php\"}"
      description = "Block secret and commodity scanner probes"
      enabled     = true
    },
  ]
}

resource "cloudflare_ruleset" "rate_limits" {
  zone_id     = var.zone_id
  name        = "Zylora abuse-sensitive route limits"
  description = "Independent IP and data-center counters for auth, forms, leads, chatbot, AI editing, and public APIs"
  kind        = "zone"
  phase       = "http_ratelimit"

  rules = [
    {
      action      = "block"
      expression  = "http.request.uri.path in {${local.auth_path_expression}}"
      description = "Authentication and verification commands: 10 requests per minute"
      enabled     = true
      ratelimit = {
        characteristics     = ["cf.colo.id", "ip.src"]
        period              = 60
        requests_per_period = 10
        mitigation_timeout  = 600
      }
    },
    {
      action      = "block"
      expression  = "http.request.uri.path eq \"/api/v1/auth/google/callback\""
      description = "OAuth callback: 20 requests per minute"
      enabled     = true
      ratelimit = {
        characteristics     = ["cf.colo.id", "ip.src"]
        period              = 60
        requests_per_period = 20
        mitigation_timeout  = 600
      }
    },
    {
      action      = "block"
      expression  = "starts_with(http.request.uri.path, \"/api/v1/public/contact\") or starts_with(http.request.uri.path, \"/api/v1/public/leads\") or starts_with(http.request.uri.path, \"/api/v1/chatbot\") or starts_with(http.request.uri.path, \"/api/v1/leads\")"
      description = "Public forms, chatbot, and lead capture: 20 requests per minute"
      enabled     = true
      ratelimit = {
        characteristics     = ["cf.colo.id", "ip.src"]
        period              = 60
        requests_per_period = 20
        mitigation_timeout  = 600
      }
    },
    {
      action      = "block"
      expression  = "http.request.method eq \"POST\" and ends_with(http.request.uri.path, \"/editor/ai-edits\")"
      description = "Authenticated AI editing: 10 plans per minute per visitor IP"
      enabled     = true
      ratelimit = {
        characteristics     = ["cf.colo.id", "ip.src"]
        period              = 60
        requests_per_period = 10
        mitigation_timeout  = 300
      }
    },
    {
      action      = "block"
      expression  = "http.request.method eq "POST" and starts_with(http.request.uri.path, "/api/v1/templates/") and ends_with(http.request.uri.path, "/instantiate")"
      description = "Template Draft instantiation: 10 requests per minute"
      enabled     = true
      ratelimit = {
        characteristics     = ["cf.colo.id", "ip.src"]
        period              = 60
        requests_per_period = 10
        mitigation_timeout  = 600
      }
    },
    {
      action      = "block"
      expression  = "http.request.method eq "GET" and starts_with(http.request.uri.path, "/api/v1/templates")"
      description = "Published Template catalogue and previews: 90 requests per minute"
      enabled     = true
      ratelimit = {
        characteristics     = ["cf.colo.id", "ip.src"]
        period              = 60
        requests_per_period = 90
        mitigation_timeout  = 60
      }
    },
    {
      action      = "block"
      expression  = "starts_with(http.request.uri.path, \"/api/v1/public/\")"
      description = "General public API ceiling: 120 requests per minute"
      enabled     = true
      ratelimit = {
        characteristics     = ["cf.colo.id", "ip.src"]
        period              = 60
        requests_per_period = 120
        mitigation_timeout  = 60
      }
    },
  ]
}
