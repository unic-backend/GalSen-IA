# Media engine — integration map (VOLET M01)

What GalSen IA already has, what the media engine reuses, and what this machine
can actually execute. Every row was read or run in the repository — none is
assumed. Directive §39 asks for exactly this before any implementation.

## Reused as-is — no second implementation

| Directive asks for | Already carries it | Why it is not rebuilt |
|---|---|---|
| §12 transcription | `src/multimodal/` — `TranscriptionProvider`, registry, Whisper adapter (VOLET 32, ADR-015 shape) | The registry already answers `None` when no transcriber can work, and the caller must refuse the file **saying so**. That is the rule this engine needs; a second path would be a second thing to keep honest. |
| §4 visual analysis | `src/vision_intelligence_engine/` — 16 modules on OpenCV 5.0 + Pillow 12.3 | Scene and frame analysis compose these. Each analysis already reports its own state rather than returning a plausible result. |
| §10, §35 provider registry | `src/model_engine/` — `providers/`, `model_selector.py`, `capability_detector.py`, ADR-014 | Video providers follow the same interface/registry shape. Model independence is already a decided architecture, not a new idea. |
| §24 agent tools | `src/tool/` — `capabilities.py` (`DataScope`, `Effect`), `authorization.py` role ceilings | Media tools declare capabilities and are gated by ceilings that already exist. A tool that writes files or reaches the network is already a described thing here. |
| §26 autonomous repair | `src/agent/` self-healing harness | Reused unchanged. Its immutability policy means the media engine never modifies it. |
| §30 security | `src/security/trust.py`, `isolation.py`, `redaction.py` | External media, filenames, prompts and metadata are **data with an origin**. The boundary exists; opening a second one would be the weakening §42 forbids. |
| §31 provenance | `src/acquisition/manifest.py`, entity/relation provenance discipline | Asset provenance follows the repository rule: nothing enters without a source. |
| §18 persistence | ADR-005 — `GALSEN_STORAGE_BACKEND`, `GALSEN_DATA_DIR` | Project manifests select their store the way every other engine does. |
| §28 resumability | `src/router/workflow_checkpoint.py` | A render job resumes on existing checkpoint machinery rather than a new one. |
| §29 API | `src/api/server.py` (124 routes), `rbac.py` | Media routes join the existing surface and its permission model. |
| §27 degradation vocabulary | `src/integration/degradation.py` — `AVAILABLE` / `DEGRADED` / `UNAVAILABLE` | A media probe reads the same way as the nine subsystem probes that already exist. |

## Genuinely new — what this programme must build

Job queue (no `Queue`/`JobStatus` class exists anywhere in `src/`), project
manifest and versioning, timeline model, deterministic edit planner, motion
design layer, render backends, asset registry, media skills, media QC, and the
multi-format / multilingual adaptation layer.

## What this machine can execute — measured, not assumed

`python -c "from src.media.core.capabilities import capability_report"`

| Capability | State | Measured finding |
|---|---|---|
| `frame_encode` | **AVAILABLE** | MJPEG frames piped in → VP8/WebM out. **Verified by producing a real file**, not by reading a version string. |
| `image_analysis` | **AVAILABLE** | OpenCV 5.0.0, Pillow 12.3.0 |
| `media_probe` | DEGRADED | `ffmpeg` found, no `ffprobe`. Duration and FPS are not reliably readable — and guessing them is what this engine refuses. |
| `video_decode` | DEGRADED | No H.264, no MP4/MOV. Reads matroska, `image2pipe`, mjpeg only. |
| `video_encode` | DEGRADED | VP8/VP9 only. Enough for a preview, not for a master requested as MP4. |
| `audio_decode` | UNAVAILABLE | **No audio codec at all.** |
| `audio_analysis` | UNAVAILABLE | Follows from the above: no silence, energy or loudness measurement, so no cut point can be placed safely. |
| `transcription` | UNAVAILABLE | No active transcriber (VOLET 32). |
| `browser_render` | DEGRADED | Chromium present at `PLAYWRIGHT_BROWSERS_PATH`, no driver to steer it. |
| `gpu_compute` | UNAVAILABLE | No `torch`, no CUDA. |

### Why the probe interrogates the binary instead of checking the PATH

A boolean would have been wrong **in both directions**, and this is the finding
that shaped the module.

There is no `ffmpeg` on the `PATH`, so `shutil.which("ffmpeg")` says *no media
work is possible*. But `/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux` exists,
shipped with the browser tooling — and adding that path would have made the
boolean say *yes*, equally wrongly. That binary is built `--disable-everything`
with a short allowlist. It answers `-version` exactly like a full build.

Two further distinctions cost a real failure each, both found by **running**
the encode rather than reading the configuration string:

- **`image2` is not `image2pipe`.** One reads a numbered file sequence off
  disk, the other receives frames on stdin. This build has only the second, so
  a `-i frames/f%04d.png` command never opens its input. A substring match
  conflated them — the same approximate-matching mistake this repository
  already paid for once in `find_country` (VOLET 69). Names are now read by
  token.
- **Encoding PNG is not decoding PNG.** The build carries
  `--enable-encoder=png` and no PNG decoder. Piping PNG frames fails; piping
  JPEG frames produces a valid WebM. The probe therefore reports *which frame
  format to produce* (`frame_pipe_format()`), because producing frames in a
  format the binary cannot read fails at the last step, after all the rendering
  work is done.

`tests/media/test_capabilities.py` encodes a real 12-frame video to pin this.
When no `ffmpeg` exists at all, that test skips — it never passes by asserting
nothing.

## What this means for the programme

The deterministic media layer (§3) and generative video (§10, §11) cannot run
here, and that shapes the build rather than stopping it. Every stage is an
**adapter behind a capability probe**, the shape ADR-014 and
`src/integration/degradation.py` already use. `require()` refuses a degraded or
absent capability instead of producing "something anyway" — an empty file, a
default duration, an invented transcript.

One capability is fully available and it is not a small one: the motion-design
path (§8, §9) renders and encodes real video on this machine today.

Honest end state, in the shape Darra J reached:

> **ENGINE READY — MEDIA RUNTIME DEPENDENCIES PENDING** (ffprobe, full ffmpeg,
> a transcriber, a browser driver, a GPU)
