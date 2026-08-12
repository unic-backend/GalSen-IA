# Training Infrastructure — Design & Evaluation

Companion to `docs/architecture/assessment-2026-08-11.md`, written before any code.
Scope: the capability to fine-tune specialised models for African languages and GalSen IA
use cases — **not** to train a large model.

## What exists today, measured

`grep` over `src/`, `agents/` and `tools/` for `torch`, `train(`, `dataset`, `LoRA`,
`checkpoint`, `fine-tun`: **zero hits**. For `feedback`, `preference`, `rating`: two
hits, neither related (memory summarisation, knowledge quality). There is no training
code, no dataset, no evaluation set and no feedback capture.

One thing *does* exist, and it is the piece that matters most:
`src/model_engine/providers/openai_compatible_provider.py` and `local_provider.py`.
**A fine-tuned model re-enters the platform through an interface that is already built
and already tested** (ADR-003). Nothing about serving a trained model needs inventing.

---

## The uncomfortable finding, stated first

The brief lists distributed training, DeepSpeed and GPU optimisation. Those solve
**"the model does not fit on my GPUs"**. That is not this project's problem and will not
be for a long time.

The real blockers for a Wolof-capable specialised model, in order:

1. **There is no data.** No parallel corpus, no instruction set, no preference pairs. A
   LoRA run needs a few thousand good examples; the repository has zero.
2. **There is no way to tell whether a fine-tune helped.** With no evaluation set, a
   trained model is a feeling. This is the exact failure mode `.claude/rules/verification.md`
   names — a plausible answer where a status was owed.
3. **The feedback signal is not being captured.** The platform will run, users will
   correct it, and every one of those corrections is preference data that **is lost
   forever if nobody writes it down today**. This is the only item on the list that gets
   more expensive the longer it waits.
4. Only then: compute.

A single rented A100 or a 24 GB consumer GPU fine-tunes a 7–8B model with QLoRA. That
regime needs **no distributed training at all**. Building multi-node infrastructure before
having 5 000 training examples would be the most speculative work in this repository.

So the design below is deliberately inverted relative to the brief: **capture, evaluate,
adapt — then scale the compute if the data ever justifies it.**

---

## Evaluation of the named ecosystems

| Candidate | Verdict | Reasoning |
|---|---|---|
| **PyTorch Distributed** | **Substrate, not a choice** | It ships with PyTorch and everything else sits on it. `DistributedDataParallel` is the right tool at 2–8 GPUs. Using its APIs directly means writing launch, sharding and checkpoint code by hand — work Accelerate already does. Present by dependency, not adopted as an interface. |
| **Hugging Face Accelerate** | **Yes — the default** | The thinnest correct abstraction: the same training script runs on CPU, on one GPU, on several, or on multiple nodes, with the device placement removed from the code. It is a *library*, not a framework — it does not own the training loop, so it can be dropped later without a rewrite. It also fronts DeepSpeed and FSDP by configuration, which makes the next question cheap to answer instead of urgent. |
| **DeepSpeed** | **Not now; reachable through Accelerate when needed** | ZeRO-2/3 exists to train models that do not fit in memory. With QLoRA on a 7–8B model, they fit. Adopting DeepSpeed today buys nothing and costs a heavy dependency, NCCL tuning and a second launch path. **Trigger to adopt: a full fine-tune (not LoRA) of a model above ~13B, or a run that does not fit at batch size 1.** When that day comes, Accelerate turns it on with a config file. |
| **PEFT (LoRA / QLoRA)** | **Yes — this is the actual lever** | Trains 0.1–2 % of the parameters. A 7B adaptation on one 24 GB GPU, in hours, for a few euros. Adapters are ~50–200 MB, so **several domain adapters can be kept and swapped** — agriculture, health, education — which fits this platform's structure far better than one monolithic fine-tune. |
| **TRL — DPO, not PPO/RLHF** | **Yes, and this is a correction to the brief** | Classic RLHF needs a reward model plus PPO: three models in memory, unstable, expensive to tune. **DPO trains directly on preference pairs**, needs no reward model, and reaches comparable quality for this class of work. The brief's "reinforcement learning from feedback" is best served by DPO — the requirement is the *feedback loop*, and DPO is the cheapest honest way to close it. |
| **bitsandbytes** | **Yes** | 4-bit quantised base weights are what makes QLoRA fit. It is a dependency of the QLoRA path, not a separate decision. |
| **Unsloth** | **Evaluate at the first real run** | 2× faster, less memory, same LoRA output. Attractive, narrower hardware support. Decide with a measurement, not in advance. |
| **Axolotl** | **No** | A YAML wrapper over the same libraries. This repository already has a configuration culture of its own; adding a second one hides what is actually running. |
| **llama.cpp / GGUF conversion** | **Yes — the last mile** | An adapter nobody can serve is a research artefact. Merging the adapter and converting to GGUF puts the model behind Ollama, which the platform already speaks (`local_provider.py`). **This is the step that closes the loop, and it is the one most projects skip.** |
| **vLLM** | **Later** | Serving, not training. It matters when concurrency does; ADR-013 says one instance. |
| **Weights & Biases** | **No** | A hosted service for runs measured in dozens. A run manifest written next to the checkpoint answers the same question with no account and no data leaving the machine. |

**Rejected in one sentence:** everything whose purpose is scale (DeepSpeed, multi-node,
vLLM, hosted tracking) is deferred behind a written trigger; everything whose purpose is
*efficiency at small scale* (PEFT, bitsandbytes, DPO, GGUF) is adopted.

---

## The proposed architecture

Four components, each usable alone, each verifiable without a GPU except the trainer.

### 1. Signal capture — `src/training/feedback/`

Records what the platform got right and wrong, as it happens: the prompt, the model that
answered, the answer, the correction or the rating, the subject (ADR-010) and the domain.

Design constraints, all inherited from decisions already taken:

- Stored through `src/storage/` like everything else — no new persistence layer (ADR-005).
- **Consent and ownership are not optional.** A correction belongs to the person who wrote
  it; export for training passes through the approval gate (ADR-006) and honours ADR-010.
- Personal data is excluded at capture time, not at export time. Filtering later means
  it was written to disk in the first place.

This component is the reason to start early: it is the only one whose cost grows every day
it is postponed.

### 2. Evaluation — `src/training/evaluation/`

A held-out set and a scorer, **built before the first training run**. Without it there is
no way to state that a fine-tune helped, and the project's rules forbid claiming it did.

Contents: French and Wolof prompts drawn from real use, the domains the platform targets
(agriculture, health, education, business), and the failure cases already known. Scored on
exact-match where applicable, retrieval hit-rate for RAG answers, and a small human-rated
subset — reported separately, never averaged into one number that hides which half moved.

### 3. Adaptation — `scripts/training/`

A training script, not a framework: `accelerate` + `peft` + `trl`, driven by a config
file, producing a run manifest (base model, data hash, hyper-parameters, seed, metrics)
next to every checkpoint. Runs on a rented GPU; the repository holds the recipe, never
the weights.

**Two adapters, in this order — and the first one is the recommendation that departs most
from the brief:**

1. **A fine-tuned embedding model** (VOLET 27's `sentence-transformers` base, adapted on
   French/Wolof pairs). It is small, trains on CPU or a modest GPU, its effect is
   **measurable without any human judgement** — retrieval hit-rate goes up or it does not
   — and it improves search, memory and RAG at once. It proves the whole pipeline end to
   end at a fraction of the cost of an LLM run.
2. **A domain LLM adapter** (QLoRA on a 7–8B open model), once capture and evaluation have
   produced enough material to justify it.

### 4. Return to service — the loop closes

Merge, quantise to GGUF, serve through Ollama, and the model appears in the registry like
any other (ADR-003). Evaluated on the same set as its base. **Kept only if it wins**, and
the losing run is recorded too — a training log that only contains successes is not a log.

---

## What this deliberately does not build

- No cluster, no scheduler, no multi-node anything.
- No reward model, no PPO.
- No pretraining from scratch. Adapting a good open model to Wolof is a hard, useful,
  achievable problem; pretraining is neither achievable nor necessary here.
- No GPU dependency in the API image. Training lives in `scripts/training/` with its own
  requirements file; the production image stays as light as the release made it.

---

## What was built (2026-08-12), and what could not be

VOLET 33 delivered the three components that do not need a GPU, and wrote the one
that does without pretending to have run it.

| Component | State |
|---|---|
| `src/training/feedback.py` | **Built and verified.** Corrections, preferences and reports, with consent, per-subject ownership (ADR-010), personal data scrubbed **at write time**, and export gated by ADR-006 |
| `src/training/evaluation.py` + `docs/evaluation/retrieval.jsonl` | **Built and verified**, with a real baseline measured — see below |
| `src/training/lineage.py` + `docs/training/lineage.jsonl` | **Built and verified.** Base, licence, data hash, metrics, kept-or-not |
| `scripts/training/train_adapter.py` | **Written, never executed.** It needs a GPU, PyTorch and access to base weights. It refuses to start without an approval id, and reports precisely what is missing rather than dying on an ImportError halfway through a rented hour |

### The baseline, measured rather than assumed

Against the 250 passages of the project's own documentation, on ten questions
whose answer is verifiable line by line:

```
méthode : lexical    cas : 10    hits : 4    hit_rate : 0.4
```

**That 0.4 is the number to beat.** It is what the semantic path of VOLET 27 must
improve, and then what the fine-tuned embedding model — the first training run
planned — must improve again. It needs no human judgement and no generation
model, which is why it can be measured today while exit criterion C1 is still open.

### What is deliberately still missing

- **A Wolof evaluation set.** Writing questions *and their answers* here would
  fabricate the truth the model is measured against: it would learn to satisfy an
  invention. The set grows from real usage — the questions asked, the corrections
  received — one line per case in `docs/evaluation/retrieval.jsonl`.
- **Any training run.** No GPU here, and `huggingface.co` answers 403 through this
  environment's proxy, so no base weights can be fetched. The recipe is versioned;
  running it belongs to a machine rented for the occasion.
