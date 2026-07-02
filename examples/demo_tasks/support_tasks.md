# Support Agent Demo Tasks

## In-scope tasks

- summarize ticket text
- classify support category and severity
- suggest approved troubleshooting steps
- assign the correct support queue

## Tasks that require escalation

- legal threats, fraud reports, or security compromise indicators
- requests for refunds or financial adjustments
- low-confidence classification outcomes

## Forbidden tasks

- approve refunds autonomously
- close security incidents autonomously
- alter subscription terms
- access data outside ticket context

## What audits would look like

A realistic audit trail would record:

- the ticket intake request;
- the proposed routing or draft-response action;
- the escalation target when trust-and-safety or billing review is needed;
- any denied or approval-gated outcome; and
- the policy references attached to the decision.
