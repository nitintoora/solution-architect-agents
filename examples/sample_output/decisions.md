# Architecture Decision Records

## ADR-001: Single compute deployment with regional data isolation

**Context:** Data residency requires AU data in AU and UK data in UK. The team has only 3 engineers, making dual full-stack deployments expensive to maintain.

**Decision:** Deploy a single set of compute resources (Azure Functions, Static Web Apps) with separate Azure SQL databases and blob storage accounts per region. Route data operations based on the employee's region attribute.

**Reasoning:** This gives equivalent data residency guarantees at the storage layer — where data actually resides — without doubling CI/CD pipelines, monitoring, and schema migrations. Compute is stateless and processes data transiently; the compliance requirement is about where data is stored and persisted, not where a serverless function temporarily processes a message.

**Alternatives considered:** Fully independent regional stacks (AU and UK) with separate Function Apps, databases, and pipelines, Single global database with row-level region tagging (rejected: violates data residency)

---

## ADR-002: Durable Functions for workflow orchestration

**Context:** Onboarding is a multi-step, stateful workflow with dependencies between steps, retry requirements, and the need for failure escalation to ServiceNow. The team needs to debug production issues quickly.

**Decision:** Use Azure Durable Functions to model each new hire's onboarding as a single orchestration instance with explicit activity functions for each step.

**Reasoning:** Durable Functions provide built-in state management, retry policies, timeout handling, and fan-out/fan-in patterns. Each orchestration instance is inspectable, showing exactly which step succeeded or failed. This is far easier to debug than correlating events across a chain of independent functions and message queues. The learning curve is justified by the operational benefits for a small team.

**Alternatives considered:** Loosely coupled Azure Functions chained via Service Bus topics, Power Automate workflows with premium connectors, Azure Logic Apps with built-in connectors

---

## ADR-003: Azure SQL Database over Cosmos DB

**Context:** The data model is relational (employees, checklists, tasks, training records with foreign key relationships). Scale is modest at 500–1,000 new hires per year.

**Decision:** Use Azure SQL Database (one per region) as the primary data store.

**Reasoning:** Azure SQL is significantly cheaper than Cosmos DB at this scale (estimated <$50/month per region vs. hundreds for Cosmos DB). The data is naturally relational and benefits from joins for manager dashboard queries. Azure SQL supports rich querying without requiring denormalisation. Cosmos DB's multi-region write capability, while elegant, is overkill for this volume and adds eventual consistency complexity the team doesn't need.

**Alternatives considered:** Azure Cosmos DB with multi-region write and geo-fencing, Dataverse (Power Platform), Azure Table Storage

---

## ADR-004: Workday polling over webhook-driven ingestion

**Context:** Workday must trigger the onboarding workflow. Workday supports both REST APIs for polling and configurable notifications, but webhook availability and reliability varies by tenant configuration.

**Decision:** Start with a timer-triggered Azure Function polling Workday's REST API every 15 minutes, with the architecture designed to swap in webhook-triggered ingestion later without downstream changes.

**Reasoning:** Polling is simpler to implement, test, and debug. The Service Bus decouples ingestion from orchestration, so switching from polling to webhooks only changes the ingestion function — no downstream impact. For 2–4 new hires per day, 15-minute polling latency is acceptable and still enables same-day onboarding. Webhook integration can be added as an optimisation once the core system is stable.

**Alternatives considered:** Workday webhook to HTTP-triggered Function, Workday Integration Cloud connector to Service Bus, Azure Data Factory Workday connector

---

## ADR-005: Immutable Append Blob Storage for audit logs

**Context:** All provisioning actions must be captured in an immutable audit log for compliance. Retention period needs clarification but must support extended retention.

**Decision:** Write audit logs to Azure Append Blob Storage in each region with legal hold and immutability policies enabled.

**Reasoning:** Append Blobs are purpose-built for append-only workloads. Azure's immutability policies (WORM) with legal hold ensure logs cannot be modified or deleted, satisfying compliance requirements. Cost is negligible at this volume. Logs can be queried via Azure Data Explorer or exported to Log Analytics if richer querying is needed. This is simpler and cheaper than database-based audit tables, which require additional hardening to prevent modification.

**Alternatives considered:** Azure SQL audit tables with triggers preventing modification, Azure Monitor / Log Analytics workspace, Dedicated audit database with append-only stored procedures

---

## ADR-006: React SPA on Azure Static Web Apps for the portal

**Context:** New hires, managers, and HR need a web portal for checklist management and status visibility. The team is small and needs to minimise frontend infrastructure overhead.

**Decision:** Build a React single-page application hosted on Azure Static Web Apps, authenticated via Entra ID using MSAL.js.

**Reasoning:** Azure Static Web Apps provides built-in Entra ID authentication integration, global CDN, automatic SSL, and CI/CD from GitHub — eliminating frontend infrastructure management entirely. React is widely known and easy to hire for. A responsive web app satisfies both desktop and mobile access without building a native app. The backend API functions can be colocated in the same Static Web Apps resource, simplifying deployment.

**Alternatives considered:** Power Apps model-driven app, Blazor WebAssembly on Azure App Service, Server-rendered ASP.NET Core MVC on App Service

---
