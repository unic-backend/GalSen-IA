# Large-model deployment configurations

One file per model family that GalSen IA is prepared to serve on a rented GPU
server. These are **not** models the platform has run: nothing here has been
downloaded, loaded, or benchmarked. Each file says so in its own `state` field.

## Where the numbers come from

Every `serve_command` in this directory was **fetched from the official vLLM
recipes repository** (`vllm-project/recipes`, `main`, read 2026-08-24 via
`raw.githubusercontent.com`). They are copied, not reconstructed from memory —
a flag invented for a 400-billion-parameter deployment costs an hour of a rented
GPU to discover.

Facts carry their evidence level, and the levels are not decoration:

| Level | Meaning |
|---|---|
| `VERIFIED` | Read from the official source in this session. |
| `OBSERVED` | A search engine returned it; the source page was unreachable. |
| `NOT VERIFIED` | Stated by no source read here. Treat as a hypothesis. |

`huggingface.co`, `qwenlm.github.io` and `docs.vllm.ai` are refused by this
environment's egress proxy (measured). Model cards could not be read, which is
why VRAM figures are `OBSERVED` while serve commands are `VERIFIED`.

## How a file is used

```
python scripts/models/serve_large.py kimi-k2.5            # prints the command
python scripts/models/serve_large.py kimi-k2.5 --execute  # runs it (needs GPUs)
python scripts/models/connect.py --url http://SERVER:8000/v1
```

The last one is what joins the server to the platform: `OpenAICompatibleProvider`
already speaks the OpenAI HTTP contract that vLLM and SGLang serve, so a remote
model is a base URL and a model name — **no code change**, and no second model
architecture (ADR-017).

## Sovereignty still applies

ADR-014 governs *where* a model runs, not only which one. A rented GPU outside
the platform's control is a third-party runtime, and
`src/model_engine/providers/derogations.py` is the gate that decides whether it
is allowed. Preparing a deployment does not grant it.
