"""
Le contexte live : ce qui est observé, et à quel point on en est sûr (ADR-033).

Quatre modules, et c'est tout ce que les audits ont laissé à construire :

| Module | Ce qu'il porte |
|---|---|
| `state.py` | `Observation` et `LiveContextState` — ce qui est su, et comment |
| `capture.py` | la surface d'entrée, et le rapport honnête de son absence |
| `fusion.py` | combiner sans conclure |
| `readiness.py` | l'état de chaque étape, calculé, jamais écrit |

Tout le reste est un appel vers ce qui existe : la transcription
(`multimodal/`), l'alternance de langues (`creative/language/switching.py`),
l'audio d'origine (`creative/voice/scene.py`), la frontière de confiance
(`security/trust.py`), la mémoire, les résumés, la boucle d'agent, MCP et les
suggestions proactives (`src/proactive/`).
"""
