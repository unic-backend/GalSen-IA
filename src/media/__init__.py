"""
GalSen IA — Universal Media Intelligence Engine.

An AI-directed multimedia production system, not a video generator. The engine
reasons about a production before executing it, and the reasoning is separated
from the execution on purpose (directive §1): the model decides *what* a
production should contain, deterministic tools decide *where* a cut can safely
land, what a file's duration is, and whether a render actually succeeded.

Nothing here fabricates a capability. A media operation that cannot run in the
current environment reports its state and refuses; it never returns a plausible
result. That rule is not caution — a fabricated timestamp cuts a real sentence
in half, and a fabricated transcript puts words in someone's mouth.
"""
