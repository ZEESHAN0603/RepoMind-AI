from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

DependencyCategory = Literal["internal", "external", "circular", "unresolved"]
DependencyNodeType = Literal["module", "file", "package", "service"]
CycleSeverity = Literal["high", "medium", "low"]


class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class DependencyModuleNode(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    label: str
    file_path: str
    node_type: DependencyNodeType = "file"
    category: Literal["internal", "external"] = "internal"
    language: str = "Unknown"
    exports_count: int = 0
    position: Position = Field(default_factory=Position)


class DependencyRelationship(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    source_module: str
    source_path: str
    target_module: str
    target_path: str
    category: DependencyCategory = "internal"
    language: str = "Unknown"
    import_specifiers: List[str] = Field(default_factory=list)
    confidence: str = "verified"
    line_number: Optional[int] = None


class CircularDependencyCycle(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    severity: CycleSeverity = "medium"
    cycle_path: List[str] = Field(default_factory=list)
    file_paths: List[str] = Field(default_factory=list)
    affected_count: int = 0
    description: str = ""
    impact: str = ""
    recommendation: str = ""
    confidence: str = "verified"


class DependencyAnalysisData(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    repository_id: str
    last_analyzed: str
    total_modules: int = 0
    total_imports: int = 0
    internal_count: int = 0
    external_count: int = 0
    circular_count: int = 0
    unresolved_count: int = 0
    nodes: List[DependencyModuleNode] = Field(default_factory=list)
    relationships: List[DependencyRelationship] = Field(default_factory=list)
    cycles: List[CircularDependencyCycle] = Field(default_factory=list)


class DirectDependenciesResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    file_path: str
    direction: Literal["upstream", "downstream", "both"]
    dependencies: List[DependencyRelationship] = Field(default_factory=list)
    count: int = 0


class TransitiveDependenciesResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    file_path: str
    max_depth: int
    chains: List[List[str]] = Field(default_factory=list)
    reachable_nodes: List[str] = Field(default_factory=list)
    total_reachable: int = 0


class UnresolvedDependenciesResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    repository_id: str
    unresolved_count: int = 0
    unresolved_imports: List[DependencyRelationship] = Field(default_factory=list)


class ExternalPackagesResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    repository_id: str
    package_count: int = 0
    packages: List[Dict[str, Any]] = Field(default_factory=list)
