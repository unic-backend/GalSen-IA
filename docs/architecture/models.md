# Model providers

The path exit criterion **C1** depends on, measured on 2026-08-11.

---

## Four providers behind one contract

ADR-003 puts every provider behind `ModelProvider`. Five implementations exist: three
hosted (OpenAI, Anthropic, Google), one local (Ollama), and one for any
OpenAI-compatible server (vLLM, LM Studio, llama.cpp, OpenRouter…). None is configured, so
generation answers 503 and C1 is open — that part is an operator's move, not a build.

What was a build problem: **the hosted path had never been exercised.** Only the
no-credentials branch was tested, which is the branch that never touches the API. Two
defects were hiding behind that.

## Every failure except 401 and 429 raised

The three hosted providers wrote:

```python
reason = UnavailabilityReason.UNAVAILABLE
```

**That member does not exist.** The enum holds `NO_CREDENTIALS`, `MISSING_DEPENDENCY`,
`UNREACHABLE`, `QUOTA_EXCEEDED`, `UNAUTHORIZED`, `DISABLED`. So the generic HTTP branch —
400, 403, 404, 500, 503 — and the catch-all for network errors, timeouts and malformed
JSON both raised `AttributeError` **out of** `_call_api`, instead of returning an
unavailable response. Measured before the fix:

```
LEVE : AttributeError UNAVAILABLE
```

The first real API call that was neither a refused key nor an exceeded quota would have
crashed the caller. It is now `UNREACHABLE`, and a 500 returns a response.

## The error body was read twice, so it was always empty

```python
error_body = e.read().decode('utf-8') if e.read() else str(e)
```

`e.read()` runs in the condition, consuming the stream; the second call returns nothing.
`error_body` was therefore **empty whenever a body existed** — precisely when it matters.

For OpenAI and Anthropic the variable was then unused, so a 400 reported
`"Erreur API OpenAI: 400"` and the body explaining it — unknown model, refused parameter —
was read and thrown away. For **Google it was used**:

```python
if e.code == 400 and "API_KEY_INVALID" in error_body:
```

That detection could never fire. An invalid Google key was reported as a generic 400
instead of an authentication failure, sending the operator looking in the wrong place.

`read_error_body()` reads once and truncates to 500 characters — this text ends up in an
error message, and API bodies run to kilobytes. `detail_avec_corps()` appends it, so the
operator now sees what the API actually said.

## What the tests cover, and why they mock

`tests/test_hosted_providers_api.py` replaces `urlopen`. That is not mocking the thing
under test: what is under test is request construction, response parsing and error
translation, and those are exactly what remains real. Covered for all three providers: a
successful generation, the key and model reaching the request, 429 as a quota rather than a
failure, a network error returning instead of raising, 401 for the two that use it, Google's
400-with-`API_KEY_INVALID`, and the API's own message reaching the operator.

What is still **not** proven: that a real vendor accepts these payloads.
`tests/test_generation_end_to_end.py` skips while no provider answers and runs the moment
one does — that remains the only proof that counts, and it is C1.
