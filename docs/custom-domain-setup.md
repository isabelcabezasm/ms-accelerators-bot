# Custom Domain Configuration via Azure Front Door

This guide explains how to bind a custom domain to the Accelerators Finder
application through Azure Front Door.

## Prerequisites

- Azure Front Door module deployed (Phase 0)
- Access to DNS management for your domain
- Static Web Apps and Container Apps deployed

## Configuration

### 1. Add Custom Domain in `terraform.tfvars`

```hcl
front_door_custom_domains = {
  "primary" = {
    host_name            = "accelerators.example.com"
    dns_zone_id          = "/subscriptions/.../resourceGroups/.../providers/Microsoft.Network/dnsZones/example.com"
    tls_certificate_type = "ManagedCertificate"   # Azure-managed, auto-renewed
    minimum_tls_version  = "TLS12"
  }
}

# Restrict API CORS to your custom domain
front_door_cors_allowed_origin = "https://accelerators.example.com"
```

### 2. Configure DNS

Create a CNAME record pointing to the Front Door endpoint:

```
accelerators.example.com  CNAME  <your-endpoint>.z01.azurefd.net
```

> **Note:** If using an apex/root domain, use an ALIAS record instead of
> CNAME (supported by Azure DNS zones).

### 3. Domain Validation

After applying Terraform, Azure Front Door will provision the TLS
certificate. This requires domain ownership validation:

1. Check the `custom_domain_validation_tokens` output from Terraform
2. Create a `_dnsauth.accelerators` TXT record with the validation token
3. Wait for certificate provisioning (can take up to 8 hours)

```bash
terraform output -json | jq '.custom_domain_validation_tokens'
```

### 4. Verify

After provisioning completes:

```bash
# Frontend should be accessible
curl -I https://accelerators.example.com

# API should be accessible at /api path
curl https://accelerators.example.com/api/healthz

# CORS headers should be present for SWA origin
curl -H "Origin: https://accelerators.example.com" \
     -I https://accelerators.example.com/search
```

## Architecture

```
                     ┌─────────────────────────┐
                     │   Azure Front Door       │
User ──► DNS ──►    │   (TLS termination)      │
                     │                          │
                     │   ┌───────────────────┐  │
                     │   │ WAF + Rate Limit  │  │
                     │   └───────────────────┘  │
                     │                          │
                     │   ┌─────────┐ ┌───────┐ │
                     │   │ /api/*  │ │  /*   │ │
                     │   └────┬────┘ └───┬───┘ │
                     └────────┼──────────┼─────┘
                              │          │
                    ┌─────────▼──┐  ┌────▼────────┐
                    │ Container  │  │ Static Web  │
                    │ Apps (API) │  │ Apps (SPA)  │
                    └────────────┘  └─────────────┘
```

## Routing Rules

| Pattern        | Origin         | Notes                        |
|---------------|----------------|------------------------------|
| `/api/*`      | Container Apps | API backend                  |
| `/chat`       | Container Apps | Chat endpoint                |
| `/search`     | Container Apps | Search endpoint              |
| `/healthz`    | Container Apps | Health check                 |
| `/assets/*`   | Static Web Apps| Cached static files          |
| `/*`          | Static Web Apps| SPA fallback (React Router)  |

## CORS Configuration

The Front Door CORS rule set restricts API responses to only include
`Access-Control-Allow-Origin` for the configured SWA origin. This prevents
other domains from making authenticated API calls.

Allowed methods: `GET, POST, DELETE, OPTIONS`
Allowed headers: `Authorization, Content-Type`

## TLS Certificate

Azure Front Door managed certificates are:
- Automatically provisioned after domain validation
- Auto-renewed before expiration
- TLS 1.2 minimum enforced
