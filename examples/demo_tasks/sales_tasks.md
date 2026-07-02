# Sales Agent Demo Tasks

## In-scope tasks

- summarize a prospect's stated requirements
- enrich a lead with approved firmographic data
- score a lead against an approved rubric
- create draft CRM opportunity notes

## Tasks that require escalation

- any request for custom pricing or contract changes
- any lead qualification decision below the configured confidence threshold
- any request to send a final outbound offer

## Forbidden tasks

- negotiate pricing
- commit to legal or contractual terms
- process payment information
- contact prospects outside approved templates

## What audits would look like

A realistic audit trail would show:

- the inbound qualification task or request;
- the evaluated action (for example `reply_inbound_dm` or `draft_response`);
- whether the action was allowed, denied, or sent to approval;
- any policy references that matched; and
- the decision and event identifiers used to correlate later review.
