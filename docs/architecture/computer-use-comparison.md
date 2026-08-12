# Computer Use, Desktop Automation and MCP

VOLET 34, phase 2.2. Researched on the web on 2026-08-12. This is the half where
GalSen IA is genuinely behind — phase 2.1 concluded the platform is not behind on
orchestration, memory, audit or approval; it is behind on **hands**.

**Source caution, stated up front.** Several of the most detailed pages on
computer use are vendor blogs selling an agent built on the approach they
recommend. Where a claim comes from an interested party it is marked. The OSWorld
figures come from leaderboards and the benchmark's own paper.

---

## 1. The axis that decides everything: pixels, accessibility tree, or both

Three architectures exist, and the choice is not a matter of taste:

| | Screenshot + vision model | Accessibility tree | Hybrid |
|---|---|---|---|
| What it reads | pixels | the structured element list the OS maintains for screen readers — role, label, bounds | both |
| Latency per step | **2–5 seconds** | **under 100 ms** | in between |
| What leaves the machine | **an image of your screen** | nothing | depends |
| Works on | anything drawn | applications that expose accessibility | anything, best-effort |

Most repositories that gained traction in early 2026 moved to the **hybrid**
approach. The latency and privacy figures above come from a vendor that sells an
accessibility-tree agent, so treat the exact numbers as directional — but the
*shape* of the trade-off is confirmed by independent sources: accessibility APIs
are described as a more robust mechanism than vision on screenshots, which are
"flaky, slow, and token heavy", and DOM-based targeting is inherently more
reliable than vision for anything in a browser.

### This decides chapter 05 for us, and ADR-014 is the reason

A screenshot agent **sends an image of the user's screen to a model**. On a
platform whose founding decision is that no third party sees the data
(ADR-014, sovereign mode on by default), a cloud vision call per step is not a
performance trade-off — **it is the thing the ADR exists to refuse**.

So chapter 05 is **accessibility-tree first**, with pixels as an explicit,
declared fallback for what the tree cannot describe. That ordering is not
caution; it is the only one consistent with a decision already taken. And it has
a pleasant side effect: the fallback is exactly where a local vision model earns
its place, which is a use for ToP that the sovereignty ADR already anticipated.

---

## 2. Where computer use actually stands: OSWorld

| When | Best reported |
|---|---|
| April 2024 | ~12 % |
| mid-2025 | mid-30s |
| December 2025 | **72.6 %** — Agent S3, first to cross the human baseline |
| June 2026 | **85.4 %** Claude Mythos Preview, 85.0 % Fable 5, 83.4 % Opus 4.8 |

The human baseline is **~72.36 %**, from the original paper.

**Two things this changes.**

1. **The capability is real.** Two years ago this would have been a research
   project; it is now above the human baseline on a benchmark of real
   applications on real operating systems.
2. **The top of that table is proprietary.** A sovereign platform running a local
   model will not score 85 %. Planning as if it would is the fabrication this
   repository keeps refusing. Chapter 05 must therefore be built so that the
   *ceiling is the model's*, and swapping in a better one later changes a
   configuration line, not the architecture — which is exactly what ADR-003
   already provides for text.

---

## 3. Desktop automation: what to build on

| Project | Approach | Note |
|---|---|---|
| **PyAutoGUI** | pixels only | "only sees pixels" — no element identity. The floor, not a foundation |
| **pywinauto** | Windows UI Automation | wraps UIA/UIA3 cleanly; reaches buttons, text boxes, menus inside almost any Windows program |
| **xa11y** | Playwright-style API over the accessibility tree, **Windows, macOS, Linux** | described as a solid foundation for building computer-use agents |
| **Terminator** | native Windows accessibility + Playwright-style SDK + **an MCP server** | the shape our chapter 09 should note |
| **Windows-Use** | semantic identifiers stable across screen configurations | claims 10× faster element detection than PyAutoGUI (vendor claim) |
| **Playwright** | browser DOM | the answer to our browser gap (§4) |

**Recommendation for chapter 06**: a single `GUITool` interface with one
accessibility-backed implementation per platform, and a pixel fallback declared
as such. Not PyAutoGUI as the base — an agent that clicks coordinates cannot
report *what* it clicked, and an approval gate that cannot name the target is a
dialog box asking the user to approve a mystery.

That last sentence is the real requirement, and it comes from our own
architecture rather than from any of these projects: **the approval gate needs
element identity.** Pixels cannot provide it. That is an argument for the
accessibility tree that no benchmark makes.

---

## 4. The browser gap has an obvious answer

`BrowserTool` is `urllib` plus regular expressions (phase 1.1). DOM targeting is
more reliable than vision for browser work, so chapter 06 should carry a real
browser tool built on Playwright, gated like every other write.

Measured rather than assumed: the Playwright **Python package is not installed**
here (`ModuleNotFoundError`), though Chromium binaries are present in this
development container. Neither is in the production image. So this is a declared
dependency to add with its weight stated — the pattern `requirements-embeddings.txt`
and `requirements-audio.txt` already follow — not something to switch on.

---

## 5. MCP: adopt it in the reverse of the usual order

**Adoption.** More than **18 000 servers** listed on the MCP Market within a
year, with OpenAI, Google, Meta and Microsoft participating. It is the de facto
way tools reach models.

**The threat, and it is not generic.** *Tool poisoning* — malicious instructions
embedded in tool **metadata** (descriptions, parameters, prompts) rather than in
user input — is documented as **the most prevalent and impactful client-side
vulnerability** of MCP. There is a threat model in a peer-reviewed journal, an
arXiv threat analysis, a Cloud Security Alliance best-practice guide, and a
proposed cascaded defence architecture. This is a well-studied hole, not a
rumour.

**What that means here, concretely.** GalSen IA's tool catalogue is local,
declared in `tools.yaml`, and reviewed. Becoming an **MCP client** means loading
*someone else's tool descriptions into our own prompt* — importing the exact
attack surface above, on a platform that gates writes precisely so that a
manipulated instruction cannot become an action.

So the order is reversed from the obvious one:

1. **MCP server first.** Expose GalSen IA's own tools — file service, memory,
   knowledge, audit — over MCP. Claude, Cursor and VS Code can then drive the
   platform. **The risk is ours to control** (we authenticate, we authorise, we
   audit), and the strategic gain is real: a Senegalese platform that other
   people's agents call is in a different position from one that calls theirs.
2. **MCP client second, and narrow.** Pinned servers, reviewed tool descriptions,
   no dynamic discovery, tool metadata treated as untrusted input — which is what
   `.claude/rules/security.md` already says about every external input.

---

## 6. What this changes in the plan

Nothing in the chapter list moves; three decisions inside it are now made:

- **Ch. 05 — sight**: accessibility tree first, pixels as declared fallback.
  Driven by ADR-014, not by performance.
- **Ch. 06 — GUI**: accessibility-backed element identity is a **requirement**,
  because the approval gate must be able to name what will be clicked. Playwright
  for the browser.
- **Ch. 09 — MCP**: server before client, and the client is pinned and narrow.

And one thing to carry into chapter 13: OSWorld's ceiling is the model's. Every
capability in this VOLET should degrade to a stated refusal when the model is
absent — which is what the platform already does everywhere else, and what makes
C1 the dependency it is.

---

## Sources

- Screen understanding approaches and the latency/privacy trade-off (vendor,
  sells an accessibility-tree agent):
  [architectures compared](https://fazm.ai/blog/best-open-source-computer-use-agents-2026-local-desktop-control) ·
  [the axis roundups skip](https://fazm.ai/t/best-ai-computer-use-agent-control-desktop-2026) ·
  [Windows agents](https://fazm.ai/blog/best-open-source-computer-use-agent-windows-2026)
- Independent view of accessibility APIs vs vision:
  [cross-platform desktop automation through accessibility APIs](https://crowecawcaw.github.io/general/2026/05/30/accessibility-for-computer-use.html)
- OSWorld: [leaderboard](https://leaderboard.steel.dev/leaderboards/osworld/) ·
  [benchmark description and human baseline](https://benchmarkingagents.com/osworld/) ·
  [85 % milestone and the progression from 12 %](https://cryptobriefing.com/computer-use-agents-85-percent-osworld-benchmark/) ·
  [state of computer-use agents](https://medium.com/@adnanmasood/the-hardest-easy-problem-in-ai-the-state-of-computer-use-agents-a7e3aea7fa3a)
- Desktop frameworks: [xa11y](https://xa11y.dev/) ·
  [Terminator](https://t8r.tech/) ·
  [AutoGUI](https://github.com/BillJr99/AutoGUI) ·
  [PyAutoGUI alternatives, incl. pywinauto](https://anthon.b-cdn.net/post/9-alternatives-for-pyautogui.html)
- MCP: [adoption and risks](https://checkmarx.com/learn/mcp-security-risks-real-world-incidents-and-security-controls/) ·
  [tool poisoning threat model (MDPI)](https://www.mdpi.com/2624-800X/6/3/84) ·
  [threat modeling (arXiv)](https://arxiv.org/abs/2603.22489) ·
  [Cloud Security Alliance best practices](https://labs.cloudsecurityalliance.org/agentic/agentic-mcp-security-best-practices-v1/) ·
  [prevention guide](https://www.practical-devsecops.com/mcp-security-vulnerabilities/)
