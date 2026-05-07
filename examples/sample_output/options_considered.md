# Options Considered

## Option 1: Event-Driven Azure Functions Pipeline

A serverless, event-driven architecture where a Workday webhook or scheduled poll publishes new hire events to Azure Service Bus, triggering a chain of Azure Functions that handle provisioning, checklist creation, and failure ticketing. A lightweight React SPA hosted on Azure Static Web Apps serves as the portal, backed by Azure Cosmos DB with multi-region write for data residency compliance.

**Key components:**

- Azure Service Bus (regional topics for AU/UK message routing)
- Azure Functions (serverless orchestration for provisioning, ticket creation, and checklist management)
- Azure Cosmos DB with multi-region write (AU East and UK South replicas with geo-fencing for data residency)
- Azure Static Web Apps (React SPA portal for new hires and managers)
- Azure API Management (unified API layer for Workday, Microsoft Graph, and ServiceNow integrations)
- Azure Immutable Blob Storage (append-only audit logs per region)

**Tradeoffs:** Pros: Fully serverless means near-zero operational overhead, ideal for a 3-engineer team. Event-driven design naturally decouples provisioning steps, making it resilient to downstream failures — a failed Graph API call doesn't block checklist creation. Cosmos DB's native multi-region capability makes data residency straightforward at the database level. Scales effortlessly for 500–1,000 hires/year. Cons: Azure Functions can suffer cold-start latency, though this is less critical for background provisioning than for portal UX. Cosmos DB is expensive relative to the modest data volume — you're paying for a globally distributed database to onboard ~1,000 people/year. Debugging distributed serverless chains across Service Bus and Functions can be challenging without strong observability investment. The team needs comfort with eventual consistency patterns. Workday integration may require a polling adapter if webhooks aren't available, adding complexity. Best for: Teams that want maximum scalability headroom with minimal infrastructure management and are comfortable with event-driven patterns.

**Suitability score:** 8/10

---

## Option 2: Durable Functions Orchestrator with Regional Deployments

Uses Azure Durable Functions to model the entire onboarding workflow as a single stateful orchestration per new hire, with explicit steps for provisioning, checklist tracking, and failure handling. Two independent regional deployments (AU and UK) each with their own Azure SQL Database ensure strict data residency. A shared API gateway routes new hire events to the correct regional stack based on location.

**Key components:**

- Azure Durable Functions (stateful workflow orchestrator with retry policies and human-interaction patterns)
- Azure SQL Database (one instance per region — AU East and UK South — for relational onboarding data)
- Azure Front Door (global entry point with geo-routing to regional API backends)
- Azure App Service or Static Web Apps (portal frontend with Entra ID authentication)
- Microsoft Graph API (Entra ID and M365 provisioning)
- Azure Table Storage or Append Blob (immutable regional audit logs)

**Tradeoffs:** Pros: Durable Functions gives a single, inspectable orchestration per new hire — the entire onboarding state machine (provision account → wait for confirmation → assign licenses → create checklist → track training) is visible as one workflow instance. Built-in retry, timeout, and human-interaction patterns handle provisioning failures gracefully and can escalate to ServiceNow automatically. Azure SQL is familiar, cost-effective at this scale, and supports rich querying for manager dashboards. Strict data residency is enforced architecturally via fully separate regional stacks — no risk of cross-region data leakage. Cons: Two independent deployments mean double the CI/CD pipelines, infrastructure-as-code, and monitoring configuration — significant overhead for 3 engineers. Schema migrations must be coordinated across regions. There's no single global view of onboarding status without a cross-region aggregation layer (which reintroduces residency concerns). Durable Functions have a learning curve and debugging orchestration replays can be unintuitive. Best for: Teams that want workflow visibility and explicit orchestration logic, and where strict architectural separation per region is preferred by compliance.

**Suitability score:** 7/10

---

## Option 3: Low-Code Power Platform with Azure Backend

Leverages Power Apps for the portal UI and Power Automate for workflow orchestration, minimising custom code. Workday triggers a Power Automate flow that provisions accounts via Microsoft Graph, creates checklists in Dataverse, and raises ServiceNow tickets on failure. Azure resources are used only where Power Platform cannot meet requirements — specifically, regional Azure SQL databases for data residency and Azure Functions for complex provisioning logic.

**Key components:**

- Power Apps (model-driven app for new hire checklist portal and manager dashboard)
- Power Automate (workflow orchestration with premium connectors for Workday, Graph API, and ServiceNow)
- Dataverse with Azure SQL regional backing stores (data residency enforcement for AU and UK)
- Azure Functions (provisioning logic requiring complex Graph API calls beyond Power Automate connector capabilities)
- Entra ID SSO (authentication for portal access)
- Azure Monitor + Dataverse audit tables (immutable logging of all provisioning actions)

**Tradeoffs:** Pros: Dramatically reduces development effort — Power Apps model-driven apps can deliver the portal UI in days, not weeks. Power Automate has pre-built connectors for Workday, Microsoft Graph, and ServiceNow, reducing integration code. HR team can potentially modify workflows and checklist templates without engineering involvement, freeing the 3-engineer team. Fastest time-to-value of any option. Cons: Data residency is the major challenge — Dataverse environments are region-locked but Power Platform's region model may not perfectly align with AU/UK residency requirements, potentially requiring complex Dataverse environment splitting or hybrid storage with Azure SQL. Power Automate has limited error handling and retry sophistication compared to Durable Functions. Premium connectors (Workday, ServiceNow) require Power Platform premium licensing, which adds recurring cost. Performance and customisability hit ceilings quickly — complex provisioning logic or custom UI requirements may force escape hatches into Azure Functions, creating a hybrid that's harder to reason about. Vendor lock-in to Power Platform is deeper than pure Azure PaaS. Audit logging in Dataverse is possible but less flexible than purpose-built immutable storage. Best for: Organisations that prioritise speed of delivery and want to empower non-developers, and where data residency can be confirmed to work within Power Platform's regional model.

**Suitability score:** 6/10

---
