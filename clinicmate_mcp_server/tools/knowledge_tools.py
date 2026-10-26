# knowledge_tools.py
# RAG tools: search ClinicMate policies and general health guides, with sources and a distance filter.

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from repositories import knowledge_repository
from services.embedding_service import embed_query, to_vector_text

# Chunks farther than this are not about the question (Task 2: distance filter). Tune with real questions.
MAX_DISTANCE = 0.40

HEALTH_DISCLAIMER = "General information only, not a diagnosis. Do not suggest medicines. Advise seeing a doctor."


def search_knowledge(question: str, category: str, topic: str | None, limit: int) -> dict:
    """Shared search: embed the question, find close chunks, drop far ones, build sources."""
    chunks = knowledge_repository.search_chunks(
        to_vector_text(embed_query(question)), category=category, topic=topic, limit=limit
    )
    relevant = [chunk for chunk in chunks if chunk["distance"] <= MAX_DISTANCE]

    if not relevant:
        return {
            "found": False,
            "hint": "Nothing in the ClinicMate knowledge base matches. Say you don't have this information; do not guess.",
        }

    sources = []
    for chunk in relevant:
        source = {"title": chunk["title"], "section": chunk["heading"], "url": chunk["source_url"]}
        if source not in sources:
            sources.append(source)

    return {
        "found": True,
        "results": [
            {"section": chunk["heading"], "content": chunk["content"], "distance": chunk["distance"]}
            for chunk in relevant
        ],
        "related_specialties": sorted({chunk["related_specialty"] for chunk in relevant if chunk["related_specialty"]}),
        "sources": sources,
    }


def register_knowledge_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def search_policies(
        question: Annotated[str, Field(description="The user's question in their own words", min_length=3, max_length=500)],
    ) -> dict:
        """Search ClinicMate's own policies: booking rules, cancellation, payment, refunds, privacy, cities.
        Answer ONLY from the returned results and mention the policy name."""
        return search_knowledge(question, category="policy", topic=None, limit=4)

    @mcp.tool()
    def search_health_guides(
        question: Annotated[str, Field(description="The user's health question in their own words", min_length=3, max_length=500)],
        topic: Annotated[
            Literal["infections", "chronic", "heart", "cancer", "ent", "allergy"] | None,
            Field(description="Optional group to search in"),
        ] = None,
    ) -> dict:
        """Search general health guides (symptoms, causes, prevention, when to see a doctor) for common diseases in Pakistan.
        Answer ONLY from the returned results, never diagnose and never suggest medicines.
        Use related_specialties to offer search_doctors."""
        result = search_knowledge(question, category="health_guide", topic=topic, limit=5)
        result["disclaimer"] = HEALTH_DISCLAIMER
        return result