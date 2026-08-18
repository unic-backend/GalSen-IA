#!/usr/bin/env python3
"""
Recette d'entraînement QLoRA pour SamP et ToP (VOLET 33, ch. 04 — ADR-014).

**Ce script ne peut pas être exécuté depuis un poste de développement ordinaire,
et il ne l'a pas été.** Il demande un GPU, PyTorch, et l'accès aux poids d'une
base. Il est versionné ici parce que la *recette* fait partie du dépôt — sans
elle, un entraînement n'est pas reproductible — mais son exécution appartient à
une machine louée pour l'occasion.

Ce qu'il fait :

    1. charge une base **Apache-2.0** (ADR-014 écarte Llama : sa licence impose
       de porter « Llama » dans le nom, ce qui contredit l'identité SamP/ToP) ;
    2. la quantise en 4 bits et y greffe un adaptateur LoRA — c'est ce qui fait
       tenir un modèle de 7 à 8 milliards de paramètres sur un seul GPU de 24 Go,
       et c'est pourquoi ni DeepSpeed ni le multi-nœuds ne sont nécessaires ;
    3. entraîne sur les paires exportées du chapitre 01, **et seulement sur
       celles dont l'auteur a consenti** ;
    4. écrit un manifeste à côté du point de reprise, puis inscrit la version au
       registre de lignée — y compris si l'entraînement s'est révélé mauvais.

Installation, sur la machine d'entraînement uniquement :

    pip install -r requirements-training.txt

Usage :

    python scripts/training/train_adapter.py \
        --famille samp --base Qwen/Qwen2.5-7B-Instruct \
        --paires data/exports/pairs.jsonl --approbation req_xxx
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RACINE))

from src.training.lineage import LineageRegistry, ModelVersion  # noqa: E402

# Réglages QLoRA. Ils ne sont pas des constantes de la nature : ce sont les
# valeurs de départ raisonnables, et le manifeste les inscrit pour qu'un
# entraînement suivant sache d'où il part.
DEFAUTS = {
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "learning_rate": 2e-4,
    "epochs": 3,
    "batch_size": 4,
    "gradient_accumulation": 4,
    "max_seq_length": 2048,
}


def condensat(chemin: str) -> str:
    """Retourne le condensat du jeu de données, pour la lignée."""
    empreinte = hashlib.sha256()
    with open(chemin, "rb") as fichier:
        for morceau in iter(lambda: fichier.read(65536), b""):
            empreinte.update(morceau)
    return empreinte.hexdigest()[:16]


def verifier_environnement() -> str:
    """
    Retourne ce qui manque pour entraîner, ou une chaîne vide.

    Rapporter est le comportement attendu ici : un script d'entraînement qui
    échoue sur un `ImportError` de PyTorch fait perdre du temps sur une machine
    facturée à l'heure.
    """
    manquants = []
    for module, paquet in (("torch", "torch"), ("peft", "peft"),
                           ("trl", "trl"), ("transformers", "transformers")):
        try:
            __import__(module)
        except ImportError:
            manquants.append(paquet)
    if manquants:
        return (
            f"Manquants : {', '.join(manquants)}. "
            f"pip install -r requirements-training.txt sur la machine d'entraînement."
        )
    return ""


def entrainer(options) -> int:
    """Exécute l'entraînement, ou dit précisément pourquoi il ne peut pas."""
    if not options.approbation:
        print(
            "Refus : l'entraînement consomme le texte de vraies personnes. "
            "Une approbation humaine est exigée (ADR-006).",
            file=sys.stderr,
        )
        return 2

    manque = verifier_environnement()
    if manque:
        print(f"Entraînement impossible ici. {manque}", file=sys.stderr)
        return 1

    if not os.path.isfile(options.paires):
        print(f"Jeu de paires introuvable : {options.paires}", file=sys.stderr)
        return 1

    # Imports tardifs : ils n'existent que sur la machine d'entraînement.
    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import DPOConfig, DPOTrainer

    quantisation = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(options.base)
    modele = AutoModelForCausalLM.from_pretrained(
        options.base, quantization_config=quantisation, device_map="auto",
    )

    donnees = load_dataset("json", data_files=options.paires, split="train")
    sortie = os.path.join(options.sortie, options.nom)

    entraineur = DPOTrainer(
        model=modele,
        args=DPOConfig(
            output_dir=sortie,
            num_train_epochs=DEFAUTS["epochs"],
            per_device_train_batch_size=DEFAUTS["batch_size"],
            gradient_accumulation_steps=DEFAUTS["gradient_accumulation"],
            learning_rate=DEFAUTS["learning_rate"],
            max_length=DEFAUTS["max_seq_length"],
            bf16=True,
        ),
        train_dataset=donnees,
        processing_class=tokenizer,
        peft_config=LoraConfig(
            r=DEFAUTS["lora_r"],
            lora_alpha=DEFAUTS["lora_alpha"],
            lora_dropout=DEFAUTS["lora_dropout"],
            task_type="CAUSAL_LM",
        ),
    )
    entraineur.train()
    entraineur.save_model(sortie)

    # La version est inscrite **sans mesure** : elle sera complétée par
    # l'évaluation, et tant qu'elle ne l'est pas, `issues()` le signale. Un
    # score écrit ici serait une supposition.
    LineageRegistry().record(ModelVersion(
        name=options.nom,
        family=options.famille,
        base_model=options.base,
        base_license=options.licence,
        method="qlora+dpo",
        data_hash=condensat(options.paires),
        data_description=f"{len(donnees)} paires de préférence, consenties",
        hyperparameters=dict(DEFAUTS),
        kept=None,
        notes="Entraîné, non encore évalué.",
    ))
    print(f"Adaptateur écrit dans {sortie}. Évaluez-le avant de le garder (ch. 02).")
    return 0


def main() -> int:
    """Point d'entrée."""
    analyseur = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    analyseur.add_argument("--famille", required=True, choices=("samp", "top"))
    analyseur.add_argument("--base", required=True, help="Modèle de base (Apache-2.0)")
    analyseur.add_argument("--licence", default="apache-2.0")
    analyseur.add_argument("--paires", required=True, help="JSONL de paires de préférence")
    analyseur.add_argument("--nom", default=None, help="Nom de la version produite")
    analyseur.add_argument("--sortie", default="checkpoints")
    analyseur.add_argument("--approbation", default="", help="Identifiant d'approbation (ADR-006)")
    options = analyseur.parse_args()
    options.nom = options.nom or f"{options.famille}-1"
    return entrainer(options)


if __name__ == "__main__":
    sys.exit(main())
