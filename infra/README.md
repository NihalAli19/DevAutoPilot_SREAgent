# Infra

Azure infrastructure notes and policies. **Free-tier / free-trial SKUs only** — never provision paid SKUs (see `AGENTS.md`). Set a **$0 spending cap** before provisioning.

## Targets

| Component | Service | Tier |
|:--|:--|:--|
| Backend hosting | Azure Container Apps | Free grant |
| API gateway | Azure API Management | Consumption (1M calls/mo free) |
| Frontend hosting | Azure Static Web Apps | Free |
| Database | Azure PostgreSQL Flexible | 12-mo free |
| Vector store | Azure AI Search | Free tier |
| Secrets | Azure Key Vault | ~$0 |
| Observability | Azure Monitor / App Insights | Free cap |

## Files

- `apim-policies.xml` — Azure API Management inbound policy stub (subscription keys, rate-limit, quota).

## TODO(plan: Phase 4)

- Bicep / Terraform for the free-tier resource group.
- Container Apps deploy workflow.
- Key Vault wiring and managed identity.
- Static Web Apps config for the frontend.
