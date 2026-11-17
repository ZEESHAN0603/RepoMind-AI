from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PositionSchema(BaseModel):
    x: float
    y: float


class ArchitectureNodeSchema(BaseModel):
    id: str
    label: str
    category: str
    group: str
    filePath: str
    description: str
    exports: List[str] = Field(default_factory=list)
    confidence: str
    position: PositionSchema


class ArchitectureEdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    label: str
    confidence: str


class ArchitectureViewPayloadSchema(BaseModel):
    viewMode: str
    title: str
    subtitle: str
    nodes: List[ArchitectureNodeSchema] = Field(default_factory=list)
    edges: List[ArchitectureEdgeSchema] = Field(default_factory=list)


class ArchitectureGraphResponse(BaseModel):
    repositoryId: str
    nodes: List[ArchitectureNodeSchema] = Field(default_factory=list)
    edges: List[ArchitectureEdgeSchema] = Field(default_factory=list)
    views: Dict[str, ArchitectureViewPayloadSchema] = Field(default_factory=dict)


class ArchitectureNodeDetailResponse(BaseModel):
    node: ArchitectureNodeSchema
    incomingRelationships: List[ArchitectureEdgeSchema] = Field(default_factory=list)
    outgoingRelationships: List[ArchitectureEdgeSchema] = Field(default_factory=list)
    totalConnections: int = 0
