# Operations Agent Demo Tasks

## In-scope tasks

- classify internal operations requests
- route tickets into approved runbook queues
- execute approved low-risk runbook checklist steps
- draft internal status updates from templates

## Tasks that require escalation

- production outage signals
- security incident indicators
- requests that touch finance, payroll, or identity access management
- low-confidence runbook routing or step selection

## Forbidden tasks

- disable production systems autonomously
- approve vendor contracts or spend changes
- modify payroll or identity access directly
- close security incidents without human incident command

## What audits would look like

A realistic audit trail would show:

- the incoming operations request;
- the runbook step or status-draft action that was proposed;
- whether the system allowed, denied, required approval, or simulated the request;
- the human escalation target, such as the incident commander; and
- policy references and identifiers for post-incident review.
