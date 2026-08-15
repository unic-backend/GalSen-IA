# Writing a plugin for GalSen IA

A plugin is code this repository did not write. Everything below follows from
that single fact, and none of it is negotiable by a plugin author — including
the parts that will refuse you.

This page is written from `src/plugins/contract.py`, and a test confronts the
two. A rule added to the code and forgotten here **fails the suite** rather than
being discovered by the author it refuses.

Contract version: **1.0**

## Where a plugin lives

```
plugins/<plugin_id>/
    manifest.yaml     # the declaration — nothing runs without it
    main.py           # whatever `entry_point` names, inside this directory
```

The entry point is a path **relative to the plugin's own directory**, and it
must stay there. `../../src/api/server.py` is a perfectly valid string, and that
is exactly why it is refused.

## The manifest

```yaml
plugin_id: exemple-meteo        # [a-z][a-z0-9_-]{2,39}
version: "0.1.0"
author: "Your name"             # a free string; no identity is verified
description: "One readable sentence."
entry_point: main.py

effects:                        # read | write | external
  - read
scopes:                         # public | user_private | system
  - public
```

`enabled` is never read from a manifest. That would be the author granting
themselves trust.

## What will refuse you

The complete list, so that no refusal is a surprise.

| Rule | Refuses | Why |
|---|---|---|
| `manifest_required` | A directory with no `manifest.yaml` | Nothing runs without a declaration; a directory is not one. |
| `required_fields` | A manifest missing `plugin_id`, `version`, `author`, `description` or `entry_point` | None has a default: a silent default would make an omission look like a decision. |
| `identifier_shape` | An identifier outside `[a-z][a-z0-9_-]{2,39}` | It is used as a directory name and a log key. |
| `private_and_external` | Asking for `user_private` **and** the `external` effect | An exfiltration path whatever the author's intentions. The same rule the platform's own tools hold. |
| `system_scope` | Asking for the `system` scope | It asks to modify the platform that judges it. No manifest can make that safe. |
| `entry_point_inside` | An absolute `entry_point`, or one leaving the plugin directory | A plugin only names code that belongs to it. |
| `identifier_taken` | Installing over an identifier already taken | A plugin silently replacing another would inherit its authorisation without being judged. |
| `disabled_by_default` | Running an installed but not enabled plugin | Installing is not enabling: otherwise copying a file would amount to trusting its author. |
| `undeclared_capability` | Starting a plugin for an effect or scope it did not declare | It is judged on what it asked for, not on what it attempts. |
| `no_sandbox_no_run` | Any execution while the sandbox is unavailable | Executing while believing in absent bounds is worse than not executing. |

## Lifecycle

1. Drop the directory in `plugins/`, then `POST /plugins/discover` — the plugin
   is **installed and disabled**.
2. A person enables it (`POST /plugins/{id}/enable`) and says why. That decision
   is recorded with their name.
3. `POST /plugins/{id}/run` executes the declared entry point in the sandbox.
   **No code is accepted in the request**: it comes from the file the manifest
   names, and nowhere else.
4. `POST /plugins/{id}/disable` stops it, asking nothing. Stopping something in
   a hurry must be free.

## Bounds

Execution goes through `src/sandbox/` (VOLET 34) — kernel limits, an explicit
list of what it does not guarantee, and escape tests that try to get out. A
second sandbox was not written for plugins: it would be one nobody has ever
tried to escape from.

Plugins run under tighter bounds than the platform's own agents: 5 s CPU, 10 s
wall clock, 256 MB, 64 KB of captured output.

## Your output is data

Whatever a plugin prints comes back wrapped as **external data with an origin**,
never as an instruction. A plugin that prints "ignore your previous
instructions" has printed a string, and it stays a string.

## What this platform does not do

- **It does not verify who you are.** `author` is a free string. Claiming
  otherwise would be worse than verifying nothing.
- **It does not inspect what your code does once started.** The refusals above
  are about *starting*. Claiming to police execution would be the dangerous lie.
- **It does not guarantee what `src/sandbox/policy.py` explicitly lists as not
  guaranteed.** That list travels with every execution result.

## A complete example

`plugins/exemple-meteo/` is the smallest honest plugin: it prints one JSON
object and stops. It does nothing useful on purpose — an example that called an
external API would need a credential this repository does not have, and an
example that lied about what it does would teach lying.
