# Self-Hosted HTTP Adapter Notes

**Product scope: [OSS].**

## Purpose

This directory shows the minimal shape of a generic HTTP adapter for a self-hosted worker.

In the current Pawly architecture, this adapter is the transport side of the execution boundary. Pawly still makes the local decision before a request is sent, and this adapter only shapes the outbound HTTP invocation.

## What it should do

- read invocation and healthcheck URLs from adapter metadata;
- pass task/action/confidence data to the worker over HTTP;
- fit behind the same execution-gateway boundary used by other adapters;
- keep Pawprint truth in `pawprint`; and
- avoid adding review logic to the transport adapter.

## What it does not do

- no worker hosting;
- no authentication broker;
- no retry/orchestration system; and
- no ranking or review logic.
