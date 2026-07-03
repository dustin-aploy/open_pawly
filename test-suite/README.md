# Pawly Test Suite

`pawly-test-suite` is the minimal validation layer for Pawprint-based workers.

It depends on:

- [`pawprint`](https://github.com/dustin-aploy/pawprint) for the worker identity and behavior boundary specification
- [`pawly`](https://github.com/dustin-aploy/open_pawly) for the local execution-boundary path

It checks a small set of things:

- the Pawprint worker card validates
- key Pawprint fields are present
- optional `smart` boundaries remain schema-valid when present
- safe requests complete
- `ask_first` requests require approval
- `never` requests deny
- audit output contains the expected fields
- Pawly reports contain the expected fields

## Install locally

From a checkout of [open_pawly](https://github.com/dustin-aploy/open_pawly):

```bash
pip install -e ../pawprint   # sibling checkout, or: pip install pawly-pawprint
pip install -e .
pip install -e ./test-suite
```

## Run tests

```bash
pytest test-suite/tests
```
