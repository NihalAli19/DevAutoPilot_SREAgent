"""Tests for the Azure AI Search index definition (no live Azure call)."""

from app.services.rag_service import EMBEDDING_FIELD, INDEX_NAME
from scripts.create_search_index import VECTOR_DIMENSIONS, build_index


def test_build_index_has_expected_fields():
    index = build_index()

    assert index.name == INDEX_NAME
    field_names = {f.name for f in index.fields}
    assert field_names == {"id", "source", "content", EMBEDDING_FIELD}


def test_build_index_vector_field_matches_embedding_dimensions():
    index = build_index()

    vector_field = next(f for f in index.fields if f.name == EMBEDDING_FIELD)
    assert vector_field.vector_search_dimensions == VECTOR_DIMENSIONS
