variable "name" {
  description = "Logical name prefix used for the Entra External ID app registrations."
  type        = string
}

variable "api_identifier_uri" {
  description = "Optional identifier URI for the API application. Defaults to api://<name>-api."
  type        = string
  default     = null
  nullable    = true
}

variable "frontend_hostname" {
  description = "Optional production hostname for the React SPA. When set, https://<hostname> is added as a redirect URI."
  type        = string
  default     = null
  nullable    = true
}

variable "owner_object_ids" {
  description = "Optional extra Entra object IDs that should co-own both app registrations and service principals."
  type        = set(string)
  default     = []
}

variable "sign_in_audience" {
  description = "Supported account types for the app registrations."
  type        = string
  default     = "AzureADMyOrg"

  validation {
    condition = contains(
      [
        "AzureADMyOrg",
        "AzureADMultipleOrgs",
        "AzureADandPersonalMicrosoftAccount",
        "PersonalMicrosoftAccount",
      ],
      var.sign_in_audience,
    )
    error_message = "sign_in_audience must be a valid Microsoft Entra supported account type."
  }
}

variable "spa_redirect_uris" {
  description = "Redirect URIs for the React SPA. Leave empty to use localhost:5173 plus the optional frontend hostname."
  type        = set(string)
  default     = []
}

variable "social_identity_providers" {
  description = "Manual configuration placeholders for supported social identity providers in the external tenant."
  type = object({
    email_password = object({
      enabled            = bool
      email_verification = bool
    })
    google = object({
      enabled                   = bool
      client_id                 = string
      client_secret_secret_name = string
    })
    github = object({
      enabled                   = bool
      client_id                 = string
      client_secret_secret_name = string
    })
  })
  default = {
    email_password = {
      enabled            = true
      email_verification = true
    }
    google = {
      enabled                   = false
      client_id                 = ""
      client_secret_secret_name = "external-id-google-client-secret"
    }
    github = {
      enabled                   = false
      client_id                 = ""
      client_secret_secret_name = "external-id-github-client-secret"
    }
  }
}

variable "user_flows" {
  description = "Manual configuration placeholders for External ID user flows and MFA requirements."
  type = object({
    sign_up_sign_in = object({
      name               = string
      identity_providers = set(string)
      attributes         = set(string)
    })
    password_reset = object({
      name    = string
      enabled = bool
    })
    mfa = object({
      enabled = bool
      methods = set(string)
    })
  })
  default = {
    sign_up_sign_in = {
      name               = "B2C_1_signupsignin"
      identity_providers = ["email_password", "google", "github"]
      attributes         = ["displayName", "givenName", "surname"]
    }
    password_reset = {
      name    = "B2C_1_passwordreset"
      enabled = true
    }
    mfa = {
      enabled = true
      methods = ["email_otp", "sms"]
    }
  }
}

variable "tags" {
  description = "Tags applied to resources created by the module. Kept for interface consistency with other modules."
  type        = map(string)
  default     = {}
}
