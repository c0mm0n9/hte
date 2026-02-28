from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class InfoGraphRequest(BaseModel):
    website_text: str
    website_url: str


class GraphSource(BaseModel):
    url: str
    title: str


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    description: str
    source_url: Optional[str] = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    weight: Optional[float] = None


class RelatedArticle(BaseModel):
    url: str
    title: str
    snippet: str


class InfoGraphResponse(BaseModel):
    source: GraphSource
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    related_articles: List[RelatedArticle]
