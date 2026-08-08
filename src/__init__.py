# Ce fichier fait de `src/` un paquet Python.
#
# Il ne doit rien faire d'autre. Une version précédente ajoutait `src/` à
# `sys.path` pour que des imports « nus » (`from storage...`) résolvent. Cela
# marche, et c'est précisément le problème : le même fichier devient alors
# importable sous deux noms (`storage.x` et `src.storage.x`), Python en fait
# deux modules distincts, et les classes qu'ils définissent cessent d'être
# égales — `isinstance` échoue, deux membres d'énumération de même nom ne sont
# plus le même objet. Le défaut est silencieux et se manifeste très loin de sa
# cause.
#
# La convention est donc unique et sans exception : à l'intérieur de `src/`,
# tout import interne s'écrit `from src.<module> import ...`, et c'est la racine
# du dépôt qui doit être importable.
