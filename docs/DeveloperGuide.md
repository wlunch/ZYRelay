# Developer Guide

Use `make setup`, `make test`, `make lint`, `make format-check`, and
`make typecheck`. Add business policy as versioned YAML, not Python constants.
New resource plugins must be optional, declare a manifest, preserve block text
and offsets, emit model execution metadata, and provide a deterministic
fallback.

Do not add agent loops, vector stores, graph persistence, queues, or implicit
LLM reasoning to Relay. Any new semantic object must contain evidence and a
stable deterministic ID.
