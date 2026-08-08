# This file makes the src directory a Python package.
#
# Les modules internes de src/ utilisent des imports « nus » (from storage...,
# from services..., from memory_engine...) plutôt que le préfixe src. Ces imports
# ne résolvent que si src/ est dans sys.path. On l'ajoute ici une fois pour
# toutes, au lieu de le répéter dans chaque fichier ou test.

import os
import sys

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)