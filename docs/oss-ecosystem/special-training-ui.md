# E04.4 — §4G where Unsloth belongs, §4H does Open WebUI fill a real gap

**Written**: 2026-08-20. E03.4 filled the twenty fields. This phase answers the
two questions §4 asks, and both are decided by something already in the
repository rather than by a comparison of features.

---

## §4G — Runtime, training pipeline, research pipeline, or a future phase?

### **A future phase — and the pipeline it would join already exists and already refuses to run unsupervised.**

`scripts/training/train_adapter.py` is not a placeholder. It:

- takes `--famille samp --base … --paires … --approbation req_xxx`
- **refuses to start without an approval identifier**: line 94, *"Une
  approbation humaine est exigée (ADR-006)"*
- hashes the dataset for lineage (`condensat`)
- writes a manifest beside the checkpoint and registers the version in
  `src/training/lineage.py` — **including when the training turned out badly**
- carries QLoRA defaults written down as *starting values, not constants of
  nature*, recorded in the manifest so the next run knows where it began

So the question *"does training infrastructure belong here"* was decided before
this audit: it belongs in `scripts/training/`, gated by ADR-006, with lineage.

### What §4G actually warns about, measured against that

> *"NEVER train on private user data without explicit authorization and proper
> controls."*

The input is `--paires data/exports/pairs.jsonl` — **a file path chosen by
whoever runs the script on a training host**. The approval gate proves *someone
approved a run*; it does not prove *what was in the file*. The dataset hash
gives lineage after the fact, which is how you find out later, not how you
prevent.

**That is a real gap and it is not Unsloth's.** It is the same shape as the
finding in E04.3: a control that exists, one step short of where it needs to
bite. Recorded for Ch. 07, unchanged here — §12 forbids implementation, and
this programme was not asked to design a dataset-provenance gate.

### Why not the other three options

- **Not runtime.** Unsloth is a training library. Putting it in the serving path
  would mean shipping a fine-tuning stack to answer a prompt.
- **Not the training pipeline, yet.** The pipeline exists and uses
  `transformers` + `BitsAndBytesConfig` — the quantized shape Unsloth
  accelerates. Swapping it in is a **one-file change on a GPU host**, and there
  is no GPU host, no authorised dataset, and **no family to train**: ADR-014
  names SamP and ToP as families that *do not exist yet*.
- **Not a research pipeline.** There is no research pipeline. Inventing one to
  house a library would be building the cage the directive's final rule warns
  about.

### Recommendation

**`DEFER`**, unchanged, with the trigger named: **a GPU host, an authorised
dataset with recorded provenance, and a family worth training.** All three, not
any one. Until then the row is infrastructure for work nobody has scheduled.

**And the honest note**: when that day comes, `scripts/training/train_adapter.py`
is where Unsloth goes, it replaces two imports, and the approval gate and the
lineage registry keep working unchanged. The cost of deferring is therefore
close to zero — which is exactly why deferring is right rather than merely
cautious.

---

## §4H — Does Open WebUI provide functionality GalSen IA actually lacks?

### Yes. And it cannot be used anyway.

**Both halves of that sentence matter**, and collapsing them into *"we already
have a UI"* would be dishonest.

**What it genuinely offers that this platform lacks**: a mature, polished chat
interface with conversation management, model switching, and years of usability
work. The platform serves its own UI — including `/ui/studio.html` — and nobody
should pretend it competes on polish. §4H says *"Do not replace the existing
GALSEN-IA UI simply because Open WebUI is popular."* The honest reading is that
popularity is not the reason it would be attractive; **quality is**.

### What decides it is the licence, and it was read in full

The file is titled *"Open WebUI License"*, opens **"All rights reserved"**, and
is BSD-3-Clause **plus a clause 4** forbidding removal or replacement of Open
WebUI branding — with three exceptions: **fewer than 50 end users in any rolling
30 days**, prior written permission, or an enterprise licence. PyPI classifies
the package **`Other/Proprietary License`**, agreeing with the file.

GalSen IA is meant to be deployed by ministries, universities and NGOs **under
its own name**. The three ways to comply are: ship Open WebUI branding, stay
under 50 users, or buy a licence. The first two contradict the vision directly.

### And a second reason that stands on its own

It is **an application, not a component**: its own database outside
`GALSEN_DATA_DIR` and outside `scripts/backup.py`, its own users beside the RBAC
table ADR-029 decided, its own authentication beside the platform's API keys.
Two authorities over one deployment is the shape ADR-034 already named as the
one to avoid — there, for a different project.

**Even under a permissive licence this would be `REJECT`.** The licence makes it
decisive; the architecture makes it correct.

### Recommendation

**`REJECT`**, unchanged.

**What is worth taking, and it costs nothing**: the observation that this
platform's UI is the weakest thing an outside user would meet first. That is a
product finding, not an integration one, and it belongs in the backlog rather
than in an integration plan.

---

## The §8 lesson these two rows carry

Of twelve candidates, **two published something other than a clean permissive
grant**, and both were found only by reading the file:

| Project | PyPI says | The `LICENSE` file says |
|---|---|---|
| **Open WebUI** | `Other/Proprietary License` | BSD-3-Clause **+ clause 4**, "All rights reserved", 50-user threshold |
| **LiteLLM** | `MIT` | MIT **except `enterprise/`**, whose licence file returns **404** |

**PyPI agreed with the file for Open WebUI and disagreed for LiteLLM.** A
manifest is a declaration; a file is a grant — and for one of these two, the
declaration was the more permissive of the two readings.

---

## What E04.4 refuses to conclude

- **That Unsloth would not help.** On a GPU host with an authorised dataset it
  probably would. Nothing here measured it, and no VRAM figure is invented.
- **That the existing UI is good.** It was not evaluated, and Open WebUI's
  advantage on polish is stated rather than argued away.
- **That the dataset-provenance gap is this programme's to close.** It is named,
  it is real, and it belongs to whoever is asked to fix it.
