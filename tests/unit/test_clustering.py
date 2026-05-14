"""Tests clustering géographique (sklearn requis — pas de réseau)."""
import pytest

from app.ai.clustering import cluster_clients, HAS_SKLEARN


@pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn requis")
def test_cluster_clients_groups(clients_10):
    # Arrange
    n = 3
    # Act
    clusters = cluster_clients(clients_10, n_clusters=n)
    # Assert
    assert isinstance(clusters, dict)
    assert len(clusters) >= 1
    total = sum(len(v["clients"]) for v in clusters.values())
    assert total == len(clients_10)


def test_cluster_clients_empty():
    assert cluster_clients([], n_clusters=3) == {}
