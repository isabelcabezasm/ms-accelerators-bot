# Entra External ID module

This module provisions the two Microsoft Entra app registrations the solution needs inside an **existing** Entra External ID tenant:

- `*-spa` for the React + Vite frontend
- `*-api` for the FastAPI backend

It also standardizes the API scope, app roles, and the manual configuration values for identity providers and user flows.

## What Terraform automates

- SPA app registration with SPA redirect URIs
- API app registration with `access_as_user` exposed scope
- App roles on the API app registration:
  - `user`
  - `admin`
- Service principals for both applications
- Placeholder configuration values for:
  - Email/password sign-in
  - Google federation
  - GitHub federation
  - Sign-up/sign-in flow
  - Password reset flow
  - MFA policy expectation

## What remains manual

Tenant creation is still a manual portal step for this project.

1. Create the Entra External ID tenant in the Microsoft Entra admin center.
2. Switch your Azure CLI / Terraform authentication context into that external tenant.
3. Run Terraform from `infra/` so the app registrations are created in the correct tenant.
4. In **External Identities** > **All identity providers**, configure:
   - Email with password
   - Google (using the client ID and secret referenced by this module's placeholder values)
   - GitHub (using the client ID and secret referenced by this module's placeholder values)
5. In **External Identities** > **User flows**, create and attach flows using the module outputs / variables as the source of truth:
   - `B2C_1_signupsignin` (or your overridden name)
   - `B2C_1_passwordreset` (or your overridden name)
6. Enable MFA in the sign-up/sign-in experience with the configured methods (`email_otp`, `sms` by default).
7. Add the SPA application to the sign-up/sign-in and password reset flows.
8. Grant admin consent for the SPA to call the API scope.
9. Assign the `admin` app role only to trusted operators. Treat `user` as the baseline role in application code unless you later enforce explicit role assignments for every customer.

## Inputs that matter most

- `frontend_hostname` or `spa_redirect_uris` for the React SPA redirect URIs
- `api_identifier_uri` if you do not want the default `api://<name>-api`
- `social_identity_providers` for Google/GitHub placeholder metadata
- `user_flows` for the user flow names and MFA settings you want documented

## Validation

```bash
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
```
