"""
Test du moteur de connaissances GalSen IA.
"""

import asyncio
import tempfile
import os
import json
from src.knowledge_engine import (
    KnowledgeManagerImpl,
    KnowledgeItem,
    KnowledgeSource,
    KnowledgeType,
    ContentType,
    Language,
    SourceCategory,
    KnowledgePriority
)


def test_knowledge_basic():
    """Test de base du gestionnaire de connaissances."""
    print("Testing Knowledge Manager...")

    # Créer le gestionnaire
    km = KnowledgeManagerImpl()

    # Créer une connaissance de test
    source = KnowledgeSource(
        id="test-src-001",
        type="file",
        location="/tmp/test.txt"
    )

    k1 = KnowledgeItem(
        content="Le Sénégal est un pays d'Afrique de l'Ouest. Sa capitale est Dakar.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source,
        confidence=0.9
    )

    # Ajouter la connaissance
    kid1 = km.add_knowledge(k1)
    print(f"Added knowledge with ID: {kid1}")
    assert kid1 == k1.id

    # R�cup�rer la connaissance
    retrieved = km.get_knowledge(kid1)
    assert retrieved is not None
    assert retrieved.content == k1.content
    assert retrieved.confidence == k1.confidence
    print("OK Knowledge retrieval works")

    # Mettre � jour la connaissance
    k1_updated = k1.update_content(
        "Le Sénégal est un pays d'Afrique de l'Ouest. Sa capitale est Dakar. Il a obtenu son indépendance en 1960.",
        source
    )
    success = km.update_knowledge(k1_updated)
    assert success, "Update should succeed"

    # V�rifier la mise � jour
    retrieved_updated = km.get_knowledge(kid1)
    assert "1960" in retrieved_updated.content
    assert retrieved_updated.version == 2
    print("OK Knowledge update works")

    # Recherche par texte
    results = km.search_knowledge("capitale Dakar", limit=5)
    assert len(results) > 0
    assert any("Dakar" in r.content for r in results)
    print("OK Text search works")

    # Recherche par diff�rents termes
    results2 = km.search_knowledge("indépendance 1960", limit=5)
    assert len(results2) > 0
    print("OK Search for updated content works")

    # Test de validation
    # Knowledge invalide (contenu vide)
    try:
        bad_k = KnowledgeItem(
            content="",
            knowledge_type=KnowledgeType.FACT,
            content_type=ContentType.TEXT,
            language=Language.FR,
            source=source
        )
        km.add_knowledge(bad_k)
        assert False, "Should have rejected empty content"
    except ValueError as e:
        print(f"OK Validation correctly rejected empty content: {e}")

    # Test de r�cup�ration pour RAG (simul�)
    related = km.retrieve_for_prompt("Quelle est la capitale du Sénégal?", max_items=3)
    assert len(related) > 0
    assert any("Dakar" in r.content for r in related)
    print("OK RAG retrieval works")

    # Test des statistiques
    stats = km.get_stats()
    assert "store" in stats
    assert "indexer" in stats
    assert "cache" in stats
    print(f"OK Stats: {stats}")

    # Test de suppression
    deleted = km.delete_knowledge(kid1)
    assert deleted, "Deletion should succeed"
    assert km.get_knowledge(kid1) is None
    print("OK Knowledge deletion works")

    print("All knowledge manager tests passed!")


def test_knowledge_loading():
    """Test du chargement depuis des sources."""
    print("\nTesting Knowledge Loading...")

    km = KnowledgeManagerImpl()

    # Cr�er un fichier temporaire
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("L'intelligence artificielle transforme de nombreux secteurs.\n")
        f.write("Elle permet d'automatiser des tâches complexes.\n")
        temp_file = f.name

    try:
        # Cr�er une source
        source = KnowledgeSource(
            id="test-txt-001",
            type="file",
            location=temp_file
        )

        # Charger depuis la source
        ids = km.load_from_source(source)
        print(f"Loaded {len(ids)} knowledge items from file")
        assert len(ids) > 0

        # V�rifier qu'on peut les récupérer
        for kid in ids:
            item = km.get_knowledge(kid)
            assert item is not None
            assert "intelligence artificielle" in item.content.lower()

        print("OK File loading works")

        # Test avec un fichier JSON
        json_data = {
            "title": "Test AI",
            "facts": [
                {"fact": "L'IA nécessite des données de qualité"},
                {"fact": "L'apprentissage automatique est une sous-domaine de l'IA"}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
            json_file = f.name

        try:
            json_source = KnowledgeSource(
                id="test-json-001",
                type="file",
                location=json_file
            )

            json_ids = km.load_from_source(json_source)
            print(f"Loaded {len(json_ids)} knowledge items from JSON")
            assert len(json_ids) > 0

            for jid in json_ids:
                item = km.get_knowledge(jid)
                assert item is not None
                # Le contenu devrait être le JSON format�
                assert '"title": "Test AI"' in item.content
            print("OK JSON loading works")
        finally:
            os.unlink(json_file)

    finally:
        os.unlink(temp_file)

    print("All loading tests passed!")


def test_knowledge_relationships():
    """Test des relations entre connaissances (graphe)."""
    print("\nTesting Knowledge Relationships...")

    km = KnowledgeManagerImpl()

    source = KnowledgeSource(
        id="test-src-rel",
        type="file",
        location="/tmp/rel.txt"
    )

    # Cr�er deux connaissances li�es
    k1 = KnowledgeItem(
        content="Le machine learning est une branche de l'intelligence artificielle.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source,
        confidence=0.95
    )

    k2 = KnowledgeItem(
        content="Le deep learning utilise des r�seaux de neurones profonds.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source,
        confidence=0.9
    )

    id1 = km.add_knowledge(k1)
    id2 = km.add_knowledge(k2)

    # Ajouter une relation via le graphe (acc�s direct au graphe pour ce test)
    # En pratique, cela pourrait être fait via une m�thode sp�cialis�e
    km._graph.add_edge(id1, id2, "related_to")
    km._graph.add_edge(id2, id1, "related_to")

    # V�rifier les voisins
    neighbors = km.get_related(id1)
    assert len(neighbors) == 1
    assert neighbors[0].id == id2
    print("OK Graph relationships work")

    # Trouver le plus court chemin
    path = km._graph.shortest_path(id1, id2)
    assert len(path) == 2
    assert path[0] == id1 and path[1] == id2
    print("OK Graph path finding works")

    print("All relationship tests passed!")


def test_knowledge_ranking():
    """Test du classement des connaissances."""
    print("\nTesting Knowledge Ranking...")

    km = KnowledgeManagerImpl()

    source = KnowledgeSource(
        id="test-src-rank",
        type="file",
        location="/tmp/rank.txt"
    )

    # Cr�er des connaissances avec diff�rents niveaux de confiance et de fra�cheur
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    k1 = KnowledgeItem(
        content="Fait ancien mais très fiable.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source,
        confidence=0.95
    )
    # Simuler une anciennet�
    past_time = now - timedelta(days=30)
    k1.created_at = past_time
    k1.updated_at = past_time

    k2 = KnowledgeItem(
        content="Fait récent mais moins fiable.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source,
        confidence=0.6
    )
    # Simuler une anciennet�
    recent_time = now - timedelta(hours=1)
    k2.created_at = recent_time
    k2.updated_at = recent_time

    k3 = KnowledgeItem(
        content="Fait moyen.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source,
        confidence=0.75
    )
    # Simuler une anciennet�
    medium_time = now - timedelta(days=5)
    k3.created_at = medium_time
    k3.updated_at = medium_time

    # Ajouter les connaissances (cela mettra � jour les dates internes)
    # Pour simplifier, on utilise les objets tels quels après ajout
    id1 = km.add_knowledge(k1)
    id2 = km.add_knowledge(k2)
    id3 = km.add_knowledge(k3)

    # R�cup�rer les objets stock�s (avec les bonnes dates)
    stored_k1 = km.get_knowledge(id1)
    stored_k2 = km.get_knowledge(id2)
    stored_k3 = km.get_knowledge(id3)

    # Tester le classement par confiance
    ranked_conf = km.rank_by_confidence([stored_k1, stored_k2, stored_k3])
    assert ranked_conf[0][0].id == id1  # plus haute confiance
    assert ranked_conf[-1][0].id == id2  # plus basse confiance
    print("OK Ranking by confidence works")

    # Tester le classement par r�cence
    ranked_rec = km.rank_by_recency([stored_k1, stored_k2, stored_k3])
    assert ranked_rec[0][0].id == id2  # le plus récent
    assert ranked_rec[-1][0].id == id1  # le plus ancien
    print("OK Ranking by recency works")

    # Tester le classement personnalis�
    ranked_custom = km.rank([stored_k1, stored_k2, stored_k3], {
        "confidence": 0.7,
        "recency": 0.3
    })
    # Avec ces poids, le k2 (récent mais moins confiant) devrait peut-�tre gagner
    # mais on v�rifie juste que cela fonctionne
    assert len(ranked_custom) == 3
    print("OK Custom weighted ranking works")

    print("All ranking tests passed!")


def test_knowledge_priority_hierarchy():
    """Test de la hiérarchie de fiabilité P1–P4."""
    print("\nTesting Knowledge Priority Hierarchy...")

    # Valeurs : plus petit = plus fiable
    assert KnowledgePriority.P1.value < KnowledgePriority.P2.value
    assert KnowledgePriority.P2.value < KnowledgePriority.P3.value
    assert KnowledgePriority.P3.value < KnowledgePriority.P4.value
    print("OK Priority ordering is correct (P1 > P2 > P3 > P4 in reliability)")

    # Mapping depuis la catégorie de source
    assert KnowledgePriority.from_source_category(SourceCategory.OFFICIAL) == KnowledgePriority.P1
    assert KnowledgePriority.from_source_category(SourceCategory.GOVERNMENT) == KnowledgePriority.P1
    assert KnowledgePriority.from_source_category(SourceCategory.STANDARD) == KnowledgePriority.P1
    assert KnowledgePriority.from_source_category(SourceCategory.OFFICIAL_DOCUMENTATION) == KnowledgePriority.P1
    assert KnowledgePriority.from_source_category(SourceCategory.PEER_REVIEWED) == KnowledgePriority.P2
    assert KnowledgePriority.from_source_category(SourceCategory.TRUSTED_DOCUMENTATION) == KnowledgePriority.P2
    assert KnowledgePriority.from_source_category(SourceCategory.INSTITUTIONAL) == KnowledgePriority.P2
    assert KnowledgePriority.from_source_category(SourceCategory.INDUSTRY) == KnowledgePriority.P3
    assert KnowledgePriority.from_source_category(SourceCategory.EXPERT_CONSENSUS) == KnowledgePriority.P3
    assert KnowledgePriority.from_source_category(SourceCategory.ESTIMATE) == KnowledgePriority.P4
    assert KnowledgePriority.from_source_category(SourceCategory.OPINION) == KnowledgePriority.P4
    assert KnowledgePriority.from_source_category(None) == KnowledgePriority.P3
    print("OK Source category to priority mapping is correct")

    km = KnowledgeManagerImpl()

    # Priorité par défaut = P3 (valeur prudente par défaut)
    source = KnowledgeSource(
        id="test-src-prio",
        type="file",
        location="/tmp/prio.txt"
    )
    default_item = KnowledgeItem(
        content="Le revenu minimum au Sénégal est un sujet complexe.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source
    )
    assert default_item.priority == KnowledgePriority.P3
    kid_default = km.add_knowledge(default_item)
    stored_default = km.get_knowledge(kid_default)
    assert stored_default.priority == KnowledgePriority.P3
    print("OK Default priority is P3")

    # Classement par priorité (P1 en premier)
    ranked_priorities = [
        (KnowledgePriority.P1, "La Constitution sénégalaise garantit des droits fondamentaux."),
        (KnowledgePriority.P2, "Une recherche évaluée par des pairs étudie l'économie de Dakar."),
        (KnowledgePriority.P3, "Les rapports industriels décrivent les pratiques du marché."),
        (KnowledgePriority.P4, "Une opinion personnelle sur l'avenir du transport."),
    ]
    items = []
    for prio, content in ranked_priorities:
        items.append(KnowledgeItem(
            content=content,
            knowledge_type=KnowledgeType.FACT,
            content_type=ContentType.TEXT,
            language=Language.FR,
            source=source,
            priority=prio
        ))
    ranked = km.rank_by_priority(items)
    assert ranked[0][0].priority == KnowledgePriority.P1
    assert ranked[-1][0].priority == KnowledgePriority.P4
    print("OK rank_by_priority orders P1 first, P4 last")

    # Classement pondéré par priorité uniquement
    weighted = km.rank(items, {"priority": 1.0})
    assert weighted[0][0].priority == KnowledgePriority.P1
    assert weighted[-1][0].priority == KnowledgePriority.P4
    print("OK Weighted ranking by priority works")

    km.delete_knowledge(kid_default)
    print("All priority hierarchy tests passed!")


def test_knowledge_source_provenance():
    """Test du suivi de provenance et de citation."""
    print("\nTesting Knowledge Source Provenance...")

    km = KnowledgeManagerImpl()

    # Source avec provenance complète (texte de la Constitution : priorité P1)
    from datetime import datetime, timezone
    retrieved = datetime.now(timezone.utc)
    source = KnowledgeSource(
        id="loi-2024-01",
        type="url",
        location="https://www.jo.gouv.sn/loi-2024-01",
        source_category=SourceCategory.OFFICIAL,
        title="Loi n° 2024-01 sur la protection des données",
        author="République du Sénégal",
        url="https://www.jo.gouv.sn/loi-2024-01",
        citation="Loi n° 2024-01, Journal Officiel du Sénégal, 2024",
        retrieved_at=retrieved
    )

    k = KnowledgeItem(
        content="La loi sénégalaise impose la déclaration des données personnelles.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source,
        priority=KnowledgePriority.from_source_category(source.source_category)
    )
    assert k.priority == KnowledgePriority.P1

    kid = km.add_knowledge(k)
    stored = km.get_knowledge(kid)
    assert stored is not None

    # La provenance est conservée intégralement
    assert stored.source.source_category == SourceCategory.OFFICIAL
    assert stored.source.title == "Loi n° 2024-01 sur la protection des données"
    assert stored.source.author == "République du Sénégal"
    assert stored.source.citation == "Loi n° 2024-01, Journal Officiel du Sénégal, 2024"
    assert stored.source.retrieved_at is not None
    assert stored.priority == KnowledgePriority.P1
    print("OK Provenance fields are preserved")

    # Filtrage du stockage par catégorie de source
    official_items = km.get_store().list_items(source_category=SourceCategory.OFFICIAL)
    assert any(item.id == kid for item in official_items)
    peer_reviewed_items = km.get_store().list_items(source_category=SourceCategory.PEER_REVIEWED)
    assert all(item.id != kid for item in peer_reviewed_items)
    print("OK Store filtering by source_category works")

    # La mise à jour conserve la priorité et la citation
    updated = stored.update_content(
        "La loi sénégalaise impose la déclaration des données personnelles. Elle est entrée en vigueur en 2025.",
        source
    )
    assert km.update_knowledge(updated)
    after_update = km.get_knowledge(kid)
    assert after_update.priority == KnowledgePriority.P1
    assert after_update.source.citation == "Loi n° 2024-01, Journal Officiel du Sénégal, 2024"
    assert "2025" in after_update.content
    assert after_update.version == 2
    print("OK update_content preserves priority and citation")

    km.delete_knowledge(kid)
    print("All provenance tests passed!")


def test_knowledge_reliability_filtering():
    """Test du renforcement du comportement « Je ne sais pas »."""
    print("\nTesting Knowledge Reliability Filtering...")

    km = KnowledgeManagerImpl()

    source_official = KnowledgeSource(
        id="src-official",
        type="url",
        location="https://www.gouv.sn/prix-riz",
        source_category=SourceCategory.OFFICIAL,
        citation="Communiqué officiel du gouvernement sénégalais"
    )
    source_industry = KnowledgeSource(
        id="src-industry",
        type="file",
        location="/tmp/marche.txt",
        source_category=SourceCategory.INDUSTRY,
        citation="Rapport de l'Association des commerçants de Dakar"
    )
    source_opinion = KnowledgeSource(
        id="src-opinion",
        type="file",
        location="/tmp/blogueur.txt",
        source_category=SourceCategory.OPINION,
        citation="Article d'opinion d'un blogueur local"
    )

    k1 = KnowledgeItem(
        content="Le prix officiel du riz au Sénégal est fixé par l'État.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source_official,
        confidence=0.95,
        priority=KnowledgePriority.from_source_category(source_official.source_category)
    )
    k2 = KnowledgeItem(
        content="Le prix du riz dans les marchés de Dakar varie selon la saison.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source_industry,
        confidence=0.8,
        priority=KnowledgePriority.from_source_category(source_industry.source_category)
    )
    k3 = KnowledgeItem(
        content="Le prix du riz va probablement augmenter l'année prochaine.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=source_opinion,
        confidence=0.6,
        priority=KnowledgePriority.from_source_category(source_opinion.source_category)
    )

    assert k1.priority == KnowledgePriority.P1
    assert k2.priority == KnowledgePriority.P3
    assert k3.priority == KnowledgePriority.P4

    id1 = km.add_knowledge(k1)
    id2 = km.add_knowledge(k2)
    id3 = km.add_knowledge(k3)

    # Récupération fiable par défaut : toutes les priorités jusqu'à P4 autorisées
    result = km.retrieve_reliable("prix riz", max_items=5)
    assert result["reliable"] is True
    assert len(result["items"]) == 3
    assert result["best_priority"] == "P1"
    assert any(item.id == id1 for item in result["items"])
    assert any(item.id == id3 for item in result["items"])
    print("OK Default retrieve_reliable keeps all priorities up to P4")

    # Seuil de priorité : P3 exclut l'opinion (P4)
    filtered = km.retrieve_reliable("prix riz", max_items=5, min_priority=KnowledgePriority.P3)
    assert filtered["reliable"] is True
    assert all(item.id != id3 for item in filtered["items"])
    assert any(item.id == id1 for item in filtered["items"])
    print("OK min_priority=P3 excludes P4 items")

    # Combinaison seuil de priorité + seuil de confiance
    strict = km.retrieve_reliable("prix riz", max_items=5,
                                   min_priority=KnowledgePriority.P3, min_confidence=0.9)
    assert strict["reliable"] is True
    assert any(item.id == id1 for item in strict["items"])  # confiance 0.95
    assert all(item.id != id2 for item in strict["items"])  # confiance 0.8
    print("OK min_confidence filters low-confidence items")

    # Aucune connaissance fiable : GalSen IA doit dire « Je ne sais pas »
    uncertain = km.retrieve_reliable("augmenter prochaine", max_items=5,
                                      min_priority=KnowledgePriority.P3)
    assert uncertain["reliable"] is False
    assert uncertain["items"] == []
    assert uncertain["best_priority"] is None
    assert "Je ne sais pas" in uncertain["reason"]
    print("OK 'I don't know' behavior when no reliable knowledge exists")

    km.delete_knowledge(id1)
    km.delete_knowledge(id2)
    km.delete_knowledge(id3)
    print("All reliability filtering tests passed!")


def test_knowledge_priority_validation():
    """Test de la validation renforcée liée à la priorité."""
    print("\nTesting Knowledge Priority Validation...")

    km = KnowledgeManagerImpl()

    # P1 exige une source traçable (id et location définis)
    untraceable = KnowledgeItem(
        content="Un fait de niveau P1 sans source traçable.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=KnowledgeSource(id="unknown", type="file", location="unknown"),
        priority=KnowledgePriority.P1
    )
    try:
        km.add_knowledge(untraceable)
        assert False, "P1 with untraceable source should be rejected"
    except ValueError as e:
        assert "traceable" in str(e)
        print(f"OK P1 untraceable source rejected: {e}")

    # P1 avec source traçable : accepté
    traceable_p1 = KnowledgeItem(
        content="La loi sénégalaise fixe le salaire minimum interprofessionnel garanti.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=KnowledgeSource(
            id="jo-gouv-001",
            type="url",
            location="https://www.jo.gouv.sn/smig-2024",
            source_category=SourceCategory.OFFICIAL
        ),
        priority=KnowledgePriority.P1
    )
    id_p1 = km.add_knowledge(traceable_p1)
    assert km.get_knowledge(id_p1) is not None
    print("OK P1 with traceable source accepted")

    # P2 avec source traçable : accepté
    traceable_p2 = KnowledgeItem(
        content="Une étude évaluée par des pairs confirme l'efficacité du traitement.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=KnowledgeSource(
            id="article-2023",
            type="file",
            location="/tmp/article-2023.pdf",
            source_category=SourceCategory.PEER_REVIEWED
        ),
        priority=KnowledgePriority.P2
    )
    id_p2 = km.add_knowledge(traceable_p2)
    assert km.get_knowledge(id_p2) is not None
    print("OK P2 with traceable source accepted")

    # Priorité invalide : rejetée
    invalid_priority = KnowledgeItem(
        content="Une connaissance avec une priorité invalide.",
        knowledge_type=KnowledgeType.FACT,
        content_type=ContentType.TEXT,
        language=Language.FR,
        source=KnowledgeSource(id="src-invalid", type="file", location="/tmp/inv.txt")
    )
    invalid_priority.priority = "P5"
    try:
        km.add_knowledge(invalid_priority)
        assert False, "Invalid priority should be rejected"
    except ValueError as e:
        assert "Invalid priority" in str(e)
        print(f"OK Invalid priority rejected: {e}")

    # Filtres du stockage par priorité
    p1_items = km.get_store().list_items(priority=KnowledgePriority.P1)
    assert all(item.priority == KnowledgePriority.P1 for item in p1_items)
    assert any(item.id == id_p1 for item in p1_items)
    print("OK Store exact priority filter works")

    min_priority_items = km.get_store().list_items(min_priority=KnowledgePriority.P2)
    ids_min = [item.id for item in min_priority_items]
    assert id_p1 in ids_min  # P1 <= P2 : gardé
    assert id_p2 in ids_min  # P2 <= P2 : gardé
    print("OK Store min_priority filter keeps P1 and P2")

    km.delete_knowledge(id_p1)
    km.delete_knowledge(id_p2)
    print("All priority validation tests passed!")


if __name__ == "__main__":
    test_knowledge_basic()
    test_knowledge_loading()
    test_knowledge_relationships()
    test_knowledge_ranking()
    test_knowledge_priority_hierarchy()
    test_knowledge_source_provenance()
    test_knowledge_reliability_filtering()
    test_knowledge_priority_validation()
    print("\nOK All knowledge engine tests passed!")