# E02.1 — Existing architecture: inference, providers, routing, voice (§2)

**Measured**: 2026-08-20, `Linux 6.18.5-fc-v20`, Python 3.11.15, 4 CPUs, no GPU.
Every number below comes from running the code in this repository, not from
reading its documentation.

Phase 2's rule, quoted: *"Do not replace existing components simply because a
popular open-source project exists."* This phase establishes what would be
replaced.

---

## 1. The model engine, sized

| Layer | Modules | Lines |
|---|---:|---:|
| `src/model_engine/` | **33** | **7 155** |
| of which `providers/` | 9 | — |
| `src/router/` (orchestration) | 16 | 3 017 |
| `src/multimodal/` (voice) | 4 | — |

**33 modules is not a wrapper.** It carries `model_router`, `routing_policy`,
`provider_selector`, `capability_detector`, `capability_discoverer`,
`cost_tracker`, `health_monitor`, `rate_limiter`, `response_ranker`,
`response_validator`, `retry_manager`, `token_tracker`, `parallel_executor`,
`prompt_optimizer` and `stream_handler`. Several candidates in this audit
propose to supply **one** of those.

## 2. What the provider registry actually answers

```python
ProviderRegistry().provider_ids()
→ ['local', 'openai_compatible']

.sovereignty_report()
→ {'sovereign_mode': True, 'third_party_providers': [], 'reference': 'ADR-014',
   'derogations': {'count': 0,
                   'unconditional_refusals': ['screen_capture',
                                              'training_export', 'user_content'],
                   'caller_can_request': False, 'reference': 'ADR-018'}}
```

**Two providers, and hosted ones are not registered at all** — not disabled, not
key-less: absent. That is ADR-014, and `tests/test_sovereignty_subordinate_runtimes.py`
now covers the subordinate-runtime path as well.

## 3. The finding of this phase

`ProviderRegistry().unavailability_summary()` returns, **verbatim**:

> API compatible OpenAI: Aucune URL déclarée. Renseignez
> `GALSEN_OPENAI_COMPATIBLE_URL`, par exemple **`http://localhost:8000/v1` pour
> un serveur vLLM local**.

**The repository's own error message names vLLM, port and path.** This
independently confirms what E01 found by reading `openai_compatible_provider.py`:
**vLLM and SGLang are already reachable today**, through a provider that exists,
by setting one environment variable. Nothing needs to be integrated for that to
be true, and `INTEGRATE` would therefore be the wrong verdict for a capability
that is already present.

`local` names the other half: *"Aucun serveur Ollama sur `http://localhost:11434`.
Démarrez-le avec `ollama serve`"* — the C1 exit criterion, unchanged.

## 4. Routing, measured rather than described

`config/model_routing.yaml` is read at runtime — the policy is **configuration,
not code**, and its own header says why: *"c'est une décision d'exploitation qui
dépend des modèles réellement installés sur la machine"*.

```python
shared_policy().task_types()
→ ['analysis', 'code_generation', 'code_review', 'conversation',
   'document_analysis', 'planning', 'reasoning', 'summarization',
   'translation', 'vision']          # ten

shared_policy().families()
→ {'samp': …, 'top': …}              # two, ADR-014
```

A real decision, run just now:

```python
decide({"task_type": "code_generation", "complexity": "high"}, [])
→ RouteDecision(family='top', requirements={'min_context_window': 32000, …},
                family_available=False,
                reason="Aucun modèle de la famille « top » n'est servi
                        (VOLET 33) : repli sur le meilleur modèle disponible.")
```

**`family_available=False` travels with the decision.** The router does not
pretend a generic model is `top`; it routes anyway and says what it could not
honour. That is the behaviour LiteLLM would have to match, not merely replicate.

**Failover exists and is parameterised**: `FailoverModelRouter`, threshold **3**
consecutive failures, reset after **300 s**, counted per model id.

## 5. Voice, and why whisper.cpp is a narrower question than it looks

```python
transcription_status()
→ {'provider_id': 'whisper_local', 'model_name': 'small', 'available': False,
   'reason': 'missing_dependency',
   'detail': "Aucune implémentation de Whisper n'est installée.
              pip install -r requirements-audio.txt …
              Sans elle, un fichier audio est refusé à l'ingestion plutôt que
              transcrit à vide.",
   'reference': 'VOLET 32'}

active_transcriber() → None
```

Three things follow, and they matter for §4E:

1. **A `TranscriptionProvider` interface already exists**, with a registry
   (`set_transcriber`, `reset_transcriber`, `active_transcriber`). whisper.cpp
   would be **an implementation of an existing seam**, never a new subsystem.
2. **The absence is reported, not worked around** — an audio file is *refused*
   rather than transcribed empty. Whatever fills the seam inherits that rule.
3. `whisper_provider.py`'s own docstring records why `faster-whisper` was chosen
   over `openai-whisper`: *"le même modèle sur CTranslate2, environ quatre fois
   plus vite sur CPU"*. **A CPU-speed argument was already made and decided
   here** — which is exactly whisper.cpp's pitch. §4E is therefore not *"do we
   want fast CPU transcription"* but *"is whisper.cpp faster than
   `faster-whisper` on this class of machine"*, and **that comparison has not
   been run** (`UNKNOWN`, Ch. 08).

The same docstring records the environmental blocker, measured earlier and still
true: *"Les poids se téléchargent depuis Hugging Face, qui répond 403 à travers
le mandataire de cet environnement."*

## 6. What E02.1 refuses to conclude

- **That the existing engine is better.** Nothing has been compared yet. It is
  *large, configured, and reports its own gaps* — three properties a replacement
  must preserve, not three arguments that it should not be replaced.
- **That vLLM is therefore useless.** Being reachable as a wire format says
  nothing about throughput or batching. Ch. 03 and Ch. 08.
- **That `local` + `openai_compatible` are enough.** Both are unavailable on
  this host right now. An architecture that routes correctly to nothing is still
  an architecture that routes to nothing.
