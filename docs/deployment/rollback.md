# Rollback — GalSen IA

A rollback plan that has never been executed is a hope. This one names the exact
commands, says what each of them does **not** undo, and ends with the rehearsal that
proves the target exists.

## What a rollback is here

Going back to a released tag means three separate things, and confusing them is how a
rollback turns into an outage:

| Layer | Rolled back by | Not rolled back by it |
|---|---|---|
| Code | `git checkout <tag>` + rebuild | The data, the configuration |
| Configuration | Restoring the previous `.env` | Anything else |
| Data | `python scripts/backup.py restaurer <sauvegarde>` | The code |

**The code is reversible; the data is not, unless a backup was taken.** Take one before
every upgrade — that is the entire discipline.

## Before upgrading (this is the step people skip)

```bash
# 1. Note the version currently deployed
curl -s https://$GALSEN_DOMAIN/health | python -c "import json,sys; print(json.load(sys.stdin)['version'])"

# 2. Take a backup, and check it landed
docker compose exec api python scripts/backup.py sauvegarder
docker compose exec api python scripts/backup.py lister | head -3
```

Without step 1 you will not know what to roll back **to**. Without step 2 a rollback of
the code with an already-migrated database leaves you with neither version working.

## Rolling back

```bash
# 1. Take the code back to the released tag
git fetch --tags
git checkout v0.1.0

# 2. Rebuild and restart. The proxy keeps its certificates: caddy_data is a
#    named volume and is not touched by this.
docker compose build api
docker compose up -d api

# 3. Check what is actually running — not what you expect to be running
curl -s https://$GALSEN_DOMAIN/health | python -m json.tool | head -20
```

The version in the response must be the one you rolled back to. If it is not, the
container was not rebuilt: `docker compose up -d --force-recreate api`.

## If the data must go back too

Only when the newer version wrote something the older one cannot read. Restoring is
destructive — it replaces the live databases.

```bash
docker compose stop api                      # le verrou d'instance doit être relâché
docker compose run --rm api python scripts/backup.py lister
docker compose run --rm api python scripts/backup.py restaurer 2026-08-11T18-30-00
docker compose start api
```

`restaurer` refuses to run while an instance holds the data directory, and it asks the
lock rather than testing the file's presence — so a lock file left behind by a crash does
not block the manoeuvre the crash made necessary (ADR-013).

## Failure modes, and what each one means

| Symptom | Cause | Action |
|---|---|---|
| `/health` still reports the new version | The image was not rebuilt | `docker compose up -d --force-recreate api` |
| `InstanceAlreadyRunning` at startup | The old container is still up | `docker compose ps`, stop it before starting another |
| The API starts, the data is empty | `GALSEN_STORAGE_BACKEND` is not `sqlite`, or `GALSEN_DATA_DIR` moved | Check the environment before touching the data |
| Caddy asks for a new certificate | The `caddy_data` volume was removed | Let it reissue, and watch Let's Encrypt's rate limits (five failures per hour and per domain) |
| The database is corrupt after a `cp` | The copy was not `VACUUM INTO` | Restore a backup; never copy an open SQLite file |

## Rehearsal — done on 2026-08-11

The point of a rehearsal is that the target is proven to exist before it is needed.

```bash
git fetch --tags
git checkout v0.1.0
python -c "import sys; sys.path.insert(0,'.'); from src.version import __version__; print(__version__)"
# → 0.1.0
git checkout -            # back to the working branch
```

Verified: the tag resolves, the tree checks out clean, and the version it carries is the
one the tag names.

**The tag is annotated on `383fcf7` but not yet on the remote.** The environment that
prepared this release cannot push tag refs — the git proxy answers `403` — so
`git fetch --tags` finds nothing until someone runs, once, from a normal clone:

```bash
git push origin v0.1.0
```

That push is also what triggers `.github/workflows/release.yml`, which builds the image,
checks it answers on `/live`, and publishes the release notes. Until then the release is
prepared, not published.

**Not verified here, and it must be before the first real deployment**: the container
part of this procedure — rebuild, restart and answer over HTTPS (TEST 6). That needs a
Docker host; the machine that prepared this release had none, and a rehearsal that was
not run is not reported as one.
