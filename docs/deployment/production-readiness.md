# Production Readiness & Security Review — v0.1.0

Date: 2026-08-11. Scope: the four deployment problems of the 2026-08-11 audit
(`docs/deployment/audit-2026-08-11.md`), reviewed after the fixes.

Every line below says **how** it was checked. A row whose method is "not verified" is not
a warning about a hypothetical — it is a statement that nobody has run it, and it belongs
to the operator before the first real deployment.

## Security review

| Area | State | How it was checked |
|---|---|---|
| Authentication | API key in `X-API-Key`, compared with `hmac.compare_digest` against a SHA-256 digest; no key is ever logged or returned | `tests/test_api_auth.py`, `tests/test_api_key_rotation.py` |
| Authorization | Four roles (admin/operator/user/readonly) with per-permission checks; per-subject data isolation (ADR-010) | `tests/test_rbac.py`, `tests/test_search_subject_isolation.py` |
| Key revocation | Immediate on the running instance; a second instance can no longer exist (ADR-013) | `tests/test_instance_lock.py`, `tests/test_api_key_rotation.py` |
| **Revocation durability** | **Lost on restart** — accepted and surfaced: the endpoint answers `persistent: false` | `tests/test_instance_lock.py::test_la_revocation_ne_survit_pas_au_redemarrage` |
| Secrets in the repository | No `.env`, no `.sqlite`, no `.pem`, no `.key` tracked; no credential literal in the source | `scripts/release_check.py` (contrôle « Secrets »), plus a scan for assigned literals ≥ 16 chars — 0 hits |
| Secrets in logs | Values of variables whose name contains `KEY`, `TOKEN`, `PASSWORD`, `SECRET` are replaced by `***` before logging | `src/config/environment.py`, `tests/test_config_environment.py` |
| Environment configuration | Every variable read by the code is documented in `.env.example`, enforced by a test | `tests/test_config_environment.py::test_toute_variable_lue_par_le_code_est_documentee` |
| TLS | Terminated by Caddy; the application publishes no port; certificates persist in `caddy_data` (ADR-012) | Configuration reviewed; **end-to-end not verified — TEST 2** |
| HTTP headers | CSP `default-src 'none'`, `frame-ancestors 'none'`, `nosniff`, `DENY`, `no-referrer`, `no-store`; HSTS only behind a declared proxy | `tests/test_api_security_headers.py` |
| CORS | Empty by default: no origin is allowed, not even the caller's | `tests/test_api_security_headers.py::TestOriginesCroisees` |
| Client IP / forwarded headers | `X-Forwarded-*` believed only from a declared proxy; chain read right to left | `tests/test_trusted_proxies.py` |
| Rate limiting | On by default; token bucket per client under an `RLock`; 100 concurrent requests on a 40-token bucket yield 40 grants | `tests/test_instance_lock.py::TestQuotasSousConcurrence` |
| Quota bypass | Closed: forged addresses now hit `429` | `tests/test_trusted_proxies.py::test_un_en_tete_forge_ne_donne_plus_un_quota_illimite` |
| Threat detection bypass | Closed: an attacker rotating addresses is now counted as one source | `tests/test_trusted_proxies.py::test_un_attaquant_ne_se_disperse_plus_dans_le_detecteur` |
| Interactive docs | Closed automatically as soon as a key is configured | `tests/test_api_security_headers.py::TestDocumentationInteractive` |
| Error messages | A revoked key and an unknown key return the same 401 body; internal hosts removed from 500s (VOLET 12) | `tests/test_api_key_rotation.py::test_le_refus_ne_distingue_pas_revoquee_d_inconnue` |
| Database permissions | Database files are `0600`; encryption at rest available via `GALSEN_ENCRYPTION_KEY` | `tests/test_persistence_deployment.py` |
| Docker permissions | Runs as the non-root `galsen` user | `Dockerfile`, `tests/test_docker_image_contents.py` |
| Exposed ports | `api` publishes none; only Caddy binds 80/443 | `docker-compose.yml`; **not verified on a host** |
| Debug mode | No `debug=True` or `reload=True` in `src/`; the auto-reloading service is behind the `dev` profile | Repository scan — 0 hits |
| Backup security | Backups are `0600`, written by `VACUUM INTO`; restore refuses while an instance holds the lock | `tests/test_persistence_deployment.py` |
| Dependency risk | Versions pinned exactly; test tooling no longer ships in the production image; every third-party import is declared | `tests/test_requirements.py` |
| Redis | Not introduced; ADR-013 records the trigger that would reverse that | — |

## What this review changed

- `requirements.txt` was unpinned (`>=`). The same tag produced different images over
  time, which defeats the reproducible build this release is supposed to be.
  **Now pinned exactly**, to the versions the v0.1.0 suite ran against.
- The production image installed **pytest, its plugins and the test HTTP client**.
  Split into `requirements-dev.txt`; the image no longer carries them.
- `starlette` was imported directly by the code but never declared — the application
  relied on FastAPI happening to install it. Now declared.
- `tests/test_requirements.py` derives the expected runtime dependencies from the code's
  own imports, so the split cannot silently rot. Doing it by hand would break at the
  first added import, and the failure would appear only when starting the container.

## Deployment checklist

Before the first deployment, in this order:

- [ ] DNS: `GALSEN_DOMAIN` points at the host (A/AAAA record)
- [ ] Firewall: ports **80 and 443** open — 80 is not optional, ACME goes through it
- [ ] `.env` written from `.env.example`; `GALSEN_API_KEYS` set with real keys
- [ ] `GALSEN_STORAGE_BACKEND=sqlite` — otherwise nothing survives a restart
- [ ] `GALSEN_TRUSTED_PROXIES` matches the Docker network (`172.16.0.0/12` by default)
- [ ] `GALSEN_TLS_EMAIL` set, so certificate expiry warnings reach someone
- [ ] `docker compose up -d`, then **TEST 2**: `curl https://$GALSEN_DOMAIN/health`
- [ ] `curl -I http://$GALSEN_DOMAIN/health` returns 308
- [ ] A backup runs and lands: `docker compose exec api python scripts/backup.py sauvegarder`
- [ ] Backups leave the data volume — otherwise they die with it
- [ ] **TEST 6**: rehearse the rollback (`docs/deployment/rollback.md`) *before* needing it
- [ ] A model provider is configured, or accept that generation answers 503 (**C1**)

## Remaining risks, ranked

1. **The image has never been built or started.** No Docker on the machine that prepared
   this release. The `Release` workflow builds it and checks it answers on `/live`; until
   that run is green, "it deploys" is an expectation, not a fact.
2. **Generation is unproven end to end (C1).** The provider path is tested against a
   substituted transport; no real provider has answered.
3. **A revocation does not survive a restart.** With `restart: unless-stopped`, a crash
   restores a compromised key. Persisting the revocation list is the next step.
4. **Identities are asserted, not verified.** Whoever writes `GALSEN_API_KEYS` states who
   each key belongs to; nothing checks it (ADR-010).
5. **The knowledge base is empty.** Retrieval, ranking and governance all operate on 0
   items, and every report about it describes an empty base.
6. **`flock` and SQLite assume a local disk.** On a network mount neither guarantee holds.
