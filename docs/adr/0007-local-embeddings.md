# 0007. Local embeddings with fastembed

Status: accepted, 2026-10-16

## Context
Similar-ticket search needs an embedding per ticket. Claude does not offer embeddings. Hosted options (e.g. Voyage AI) add an API key, a network dependency and a per-call cost.

## Decision
Run `BAAI/bge-small-en-v1.5` (384 dimensions, ONNX, quantized) on the CPU through fastembed. Store the vector and the model name on the ticket. Index with HNSW using cosine distance. The model is baked into the Docker image and loaded offline.

## Consequences
- $0 per call; 16 ms for four short texts; ~220 ms to load from disk.
- Image grows from ~394 MB to ~793 MB (ML libraries + 67 MB model).
- English only. A multilingual model has a different dimension: it needs a new column or a table rebuild and a re-embed of every ticket.
- Unrelated texts score ~0.5, so the default similarity cut-off is 0.65. Tune it with the eval set (Phase 5).
- Embedding runs inside the API request for now. Phase 4 moves it to the background worker.
