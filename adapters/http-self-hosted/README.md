# Self-Hosted HTTP Adapter Notes

## Purpose

This directory shows the minimal shape of a generic HTTP adapter for a self-hosted worker.

In the current Pawly architecture, this adapter is the transport side of the execution boundary. Pawly still makes the local decision before a request is sent, and this adapter only shapes the outbound HTTP invocation.

## What it should do

- read invocation and healthcheck URLs from `metadata.platform_hints`;
- pass task/action/confidence data to the worker over HTTP;
- fit behind the same execution-gateway boundary used by other adapters;
- keep Pawprint truth in `pawprint`; and
- avoid introducing a hosted runtime abstraction or platform review logic.

## What it does not do

- no worker hosting;
- no authentication broker;
- no retry/orchestration system; and
- no platform ranking or review logic.
