## Problem statement

Employee onboarding currently takes 3–5 days and requires manual coordination across HR, IT, and hiring managers. This creates delays in productivity for new hires and places repetitive operational burden on a small engineering team. The business needs an internal portal that automates account provisioning, centralises the onboarding checklist for new hires, and gives managers real-time visibility into onboarding progress.

## Stakeholders

- **HR team** — initiates and manages onboarding workflows in Workday; responsible for compliance and training completion tracking
- **IT / Engineering team (3 engineers)** — builds and maintains the portal; manages account provisioning across M365 and Entra ID; handles provisioning failures
- **Hiring managers** — need visibility into onboarding status for their new hires; responsible for role-specific onboarding tasks
- **New hires** — primary end-users of the portal; need a single place to view and complete their onboarding checklist
- **IT service desk (ServiceNow operators)** — receive and triage auto-generated tickets for provisioning failures
- **Compliance / Data governance** — accountable for data residency enforcement (AU/UK) and audit log retention [NEEDS CLARIFICATION: Is there a dedicated compliance officer or team, or does this responsibility sit within HR or IT?]

## Success criteria

- Standard-role onboarding is completed within the same business day, reduced from the current 3–5 day average
- New hire accounts are automatically provisioned in Microsoft 365 and Entra ID upon onboarding initiation from Workday, with no manual IT intervention for standard roles
- 100% of account provisioning actions (success and failure) are captured in an immutable audit log
- Provisioning failures automatically generate a ServiceNow incident ticket without manual intervention
- New hires have a single portal view showing all outstanding onboarding tasks, including mandatory training modules
- Hiring managers can view real-time onboarding status for each of their new hires
- Mandatory training module completion is tracked and recorded per new hire
- Australian employee data is stored and processed in Australia; UK employee data is stored and processed in the UK

## Constraints

- **Data residency** — AU employee data must remain in Australian infrastructure; UK employee data must remain in UK infrastructure. This is a hard compliance requirement.
- **Team capacity** — only 3 engineers available; solution must favour managed/PaaS services over self-hosted infrastructure to minimise operational overhead
- **Cloud ecosystem** — existing Azure tenancy; solution should stay within the Azure ecosystem where possible
- **Integration dependencies** — must integrate with Workday (HR source of truth), Microsoft 365 (account provisioning target), Entra ID (identity provider), and ServiceNow (incident management)
- **Scale** — must support 500–1,000 new hires per year across two regions (AU and UK)
- **Audit logging** — all provisioning actions must be logged for compliance; logs must be available for audit [NEEDS CLARIFICATION: What is the required audit log retention period?]

## Assumptions

- Workday is the authoritative source for new hire data and will trigger or supply the data that initiates the onboarding workflow (e.g., via API or event)
- "Standard roles" (eligible for same-day provisioning) represent the majority of new hires; non-standard roles may still require manual steps and are not held to the same-day target
- The existing Entra ID tenant is already federated or connected to Microsoft 365, so provisioning an identity in Entra ID grants access to M365 services
- Mandatory training modules are already defined and hosted somewhere; the portal needs to track completion status rather than host training content itself [NEEDS CLARIFICATION: Where are training modules hosted — an existing LMS, SharePoint, or a third-party platform?]
- The portal will authenticate users via Entra ID (SSO), consistent with existing identity infrastructure
- ServiceNow has an available API or integration pathway (e.g., REST API) for automated ticket creation
- "In-region" data residency applies to the onboarding portal's data storage and processing, not to Workday or M365 themselves (which have their own residency configurations)
- The two regions (AU and UK) cover all employees; there are no other office locations to support [NEEDS CLARIFICATION: Are there any employees outside AU and UK, or plans to expand to other regions?]
- There is no requirement for the portal to handle employee offboarding or role changes — only initial onboarding

## Out of scope

- Employee offboarding or mid-lifecycle changes (role transfers, departures)
- Replacement or migration of Workday, ServiceNow, or Microsoft 365
- Hosting or creation of training content; the portal tracks completion only
- Provisioning for non-Microsoft systems (e.g., Slack, Salesforce, or other SaaS tools) unless explicitly identified later [NEEDS CLARIFICATION: Are there other SaaS applications that need provisioning beyond M365?]
- Self-service password reset or broader identity management beyond initial account provisioning
- Mobile-native application development (assumed web portal is sufficient) [NEEDS CLARIFICATION: Is mobile access a requirement, or is a responsive web portal acceptable?]
- Payroll, benefits enrolment, or other HR processes outside the onboarding checklist and account provisioning workflow