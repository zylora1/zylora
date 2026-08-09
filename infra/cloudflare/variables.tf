variable "account_id" {
  description = "Cloudflare account ID. Pass with TF_VAR_account_id; never commit it with credentials."
  type        = string
  sensitive   = true
}

variable "zone_id" {
  description = "Cloudflare zone ID for the Zylora production domain."
  type        = string
  sensitive   = true
}

variable "turnstile_domains" {
  description = "Exact User and isolated Super Admin hostnames authorized by the widget."
  type        = list(string)

  validation {
    condition     = length(var.turnstile_domains) == 2 && alltrue([for host in var.turnstile_domains : !strcontains(host, "*")])
    error_message = "Provide exactly two non-wildcard domains: User Web and Super Admin Web."
  }
}

variable "turnstile_widget_name" {
  description = "Human-readable widget name."
  type        = string
  default     = "Zylora production authentication"
}
