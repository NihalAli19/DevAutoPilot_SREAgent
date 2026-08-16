"""Create (or update) the Azure AI Search index used by RAGService.

The IaC for the vector index — analogous to scripts/setup-branch-protection.sh for
branch protection. Safe to re-run (create_or_update). Requires AZURE_SEARCH_ENDPOINT
and AZURE_SEARCH_KEY to be set once the Azure AI Search resource exists.

Run from backend/:  python -m scripts.create_search_index
"""

from __future__ import annotations

from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from app.config import get_settings
from app.services.rag_service import EMBEDDING_FIELD, INDEX_NAME

VECTOR_DIMENSIONS = 768  # Gemini models/text-embedding-004
ALGORITHM_NAME = "hnsw-default"
PROFILE_NAME = "vector-profile"


def build_index(name: str = INDEX_NAME) -> SearchIndex:
    """Return the index definition: id/source/content fields + a vector field."""
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(
            name=EMBEDDING_FIELD,
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=VECTOR_DIMENSIONS,
            vector_search_profile_name=PROFILE_NAME,
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name=ALGORITHM_NAME)],
        profiles=[
            VectorSearchProfile(name=PROFILE_NAME, algorithm_configuration_name=ALGORITHM_NAME)
        ],
    )
    return SearchIndex(name=name, fields=fields, vector_search=vector_search)


def main() -> None:
    settings = get_settings()
    if not (settings.azure_search_endpoint and settings.azure_search_key):
        raise SystemExit("Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY in .env first")

    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient

    client = SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=AzureKeyCredential(settings.azure_search_key),
    )
    client.create_or_update_index(build_index())
    print(f"Index '{INDEX_NAME}' created/updated at {settings.azure_search_endpoint}")


if __name__ == "__main__":
    main()
