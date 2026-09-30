import math
import pytest

from app.services.ai.embedding import (
    DeterministicFallbackEmbeddingModel,
    EmbeddingService,
    cosine_similarity,
)


def test_cosine_similarity_edge_cases():
    # 1. Identical vectors
    vec_a = [1.0, 0.0, 0.0]
    assert cosine_similarity(vec_a, vec_a) == 1.0

    # 2. Orthogonal vectors
    vec_b = [0.0, 1.0, 0.0]
    assert cosine_similarity(vec_a, vec_b) == 0.0

    # 3. Opposite vectors
    vec_c = [-1.0, 0.0, 0.0]
    assert cosine_similarity(vec_a, vec_c) == -1.0

    # 4. Zero vector handling (safe, no zero division)
    zero_vec = [0.0, 0.0, 0.0]
    assert cosine_similarity(vec_a, zero_vec) == 0.0

    # 5. Unequal lengths
    short_vec = [1.0, 0.0]
    assert cosine_similarity(vec_a, short_vec) == 0.0


def test_deterministic_fallback_embedding_model():
    model = DeterministicFallbackEmbeddingModel(dimension=384)
    assert model.dimension == 384
    assert model.model_name == "deterministic-fallback-v1"

    texts = [
        "BALL VALVE DN50 CS CLASS150 RF SS304",
        "VALVE BALL DN50 CS 150# RF 304SS",
        "CENTRIFUGAL PUMP 50M3/HR CS",
        "",
    ]
    vectors = model.encode(texts)
    assert len(vectors) == 4

    for vec in vectors:
        assert len(vec) == 384
        # Assert unit length (||v|| = 1.0)
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-4

    # Deterministic repeatability: same input produces exact same vector
    vec_repeat = model.encode(["BALL VALVE DN50 CS CLASS150 RF SS304"])[0]
    assert vectors[0] == vec_repeat

    # Semantic similarity: similar texts score higher than completely different equipment
    sim_similar = cosine_similarity(vectors[0], vectors[1])
    sim_different = cosine_similarity(vectors[0], vectors[2])
    assert sim_similar > sim_different


def test_embedding_service_singleton():
    EmbeddingService.reset_instance()
    service1 = EmbeddingService.get_instance()
    service2 = EmbeddingService.get_instance()
    assert service1 is service2
    assert service1.dimension == 384

    res = service1.encode_one("GATE VALVE DN100 CS CLASS300 RF SS316")
    assert len(res) == 384
    norm = math.sqrt(sum(x * x for x in res))
    assert abs(norm - 1.0) < 1e-4

