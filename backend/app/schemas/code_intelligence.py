import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CodeSymbolResponse(BaseModel):
    id: str
    repository_id: str
    file_id: str
    name: str
    symbol_type: str
    scope: Optional[str] = None
    signature: str
    docstring: Optional[str] = None
    start_line: int
    end_line: int
    start_column: Optional[int] = None
    end_column: Optional[int] = None
    is_async: bool
    is_exported: bool
    visibility: str
    parameters: List[Dict[str, Any]] = []
    return_type: Optional[str] = None
    decorators: List[str] = []
    bases_or_interfaces: List[str] = []
    confidence: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("parameters", mode="before")
    @classmethod
    def parse_parameters(cls, v: Any) -> List[Dict[str, Any]]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v or []

    @field_validator("decorators", mode="before")
    @classmethod
    def parse_decorators(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v or []

    @field_validator("bases_or_interfaces", mode="before")
    @classmethod
    def parse_bases(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v or []


class CodeImportExportResponse(BaseModel):
    id: str
    repository_id: str
    file_id: str
    statement_type: str
    source_module: str
    symbol_name: Optional[str] = None
    alias: Optional[str] = None
    is_relative: bool
    is_default: bool
    line_number: int

    model_config = ConfigDict(from_attributes=True)


class ApiRouteEndpointResponse(BaseModel):
    id: str
    repository_id: str
    file_id: str
    http_method: str
    path: str
    handler_name: str
    framework: str
    start_line: int
    end_line: int
    confidence: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("metadata_json", mode="before")
    @classmethod
    def parse_metadata(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        if isinstance(v, dict):
            return v
        return {}


class SymbolsListResponse(BaseModel):
    items: List[CodeSymbolResponse]
    total: int
    offset: int
    limit: int


class AnalysisSummaryResponse(BaseModel):
    repository_id: str
    files_analyzed: int
    files_parsed: int
    files_partial: int
    files_failed: int
    files_skipped: int
    symbols_extracted: int
    endpoints_extracted: int
    imports_exports_extracted: int
    stats: Dict[str, Any]
    errors: List[Dict[str, Any]] = []


class RepositoryAnalysisOverviewResponse(BaseModel):
    repository_id: str
    total_symbols: int
    symbols_by_type: Dict[str, int]
    total_endpoints: int
    endpoints_by_framework: Dict[str, int]
    total_imports_exports: int
    last_analyzed_at: Optional[datetime] = None
