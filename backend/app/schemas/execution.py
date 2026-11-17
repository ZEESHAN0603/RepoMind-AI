from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionFlowStepSchema(BaseModel):
    stepOrder: int
    caller: str
    callee: str
    dataPassed: str = ""
    description: str = ""
    status: str = "verified"


class ExecutionFlowSchema(BaseModel):
    id: str
    title: str
    triggerType: str = "api-endpoint"  # api-endpoint, function, event
    entryPoint: str
    summary: str
    rootNodeId: str
    steps: List[ExecutionFlowStepSchema] = Field(default_factory=list)


class ExecutionFunctionSymbolSchema(BaseModel):
    id: str
    name: str
    filePath: str
    lineNumber: int
    nodeType: str = "function"  # function, method, api, database, external
    parameters: str = "()"
    returnType: str = "void"
    description: str = ""
    status: str = "verified"  # verified, inferred, unresolved
    callers: List[str] = Field(default_factory=list)
    callees: List[str] = Field(default_factory=list)
    relatedFunctions: List[str] = Field(default_factory=list)
    codeSnippet: str = ""


class ExecutionGraphNodePosition(BaseModel):
    x: float
    y: float


class ExecutionGraphNodeSchema(BaseModel):
    id: str
    label: str
    nodeType: str = "function"
    filePath: str
    lineNumber: int
    parameters: str = "()"
    returnType: str = "void"
    description: str = ""
    status: str = "verified"
    callers: List[str] = Field(default_factory=list)
    callees: List[str] = Field(default_factory=list)
    relatedFunctions: List[str] = Field(default_factory=list)
    codeSnippet: str = ""
    position: ExecutionGraphNodePosition
    depth: int = 0


class ExecutionGraphEdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    label: str = "calls"
    status: str = "verified"
    dataPassed: Optional[str] = None


class ExecutionEntryGraphSchema(BaseModel):
    flow: ExecutionFlowSchema
    nodes: List[ExecutionGraphNodeSchema] = Field(default_factory=list)
    edges: List[ExecutionGraphEdgeSchema] = Field(default_factory=list)


class ExecutionWorkspaceResponse(BaseModel):
    repositoryId: str
    repositoryName: str
    functions: List[ExecutionFunctionSymbolSchema] = Field(default_factory=list)
    traces: List[ExecutionEntryGraphSchema] = Field(default_factory=list)


class ExecutionAnalysisSummaryResponse(BaseModel):
    repository_id: str
    calls_extracted: int
    entry_points_detected: int
    traces_generated: int
    analyzed_at: str


class ExecutionEntryPointItemSchema(BaseModel):
    id: str
    entry_type: str
    display_name: str
    file_path: str
    symbol_name: Optional[str] = None
    route_path: Optional[str] = None
    http_method: Optional[str] = None
    line_number: int
    confidence: str
    description: str


class ExecutionEntryPointsListResponse(BaseModel):
    repository_id: str
    total_count: int
    entry_points: List[ExecutionEntryPointItemSchema] = Field(default_factory=list)


class ExecutionCallDetailItem(BaseModel):
    id: str
    caller_name: Optional[str]
    callee_name: str
    caller_file_path: str
    callee_file_path: Optional[str]
    line_number: int
    call_type: str
    resolution_status: str
    confidence: str
    arguments: List[str] = Field(default_factory=list)
    evidence: str = ""


class ExecutionNodeCallsResponse(BaseModel):
    symbol_id: str
    incoming: List[ExecutionCallDetailItem] = Field(default_factory=list)
    outgoing: List[ExecutionCallDetailItem] = Field(default_factory=list)


class ExecutionTracePathStepItem(BaseModel):
    step: int
    from_symbol: str
    to_symbol: str
    call_type: str
    line_number: int
    evidence: str


class ExecutionTracePathResponse(BaseModel):
    source_symbol_id: str
    target_symbol_id: str
    path_found: bool
    path_length: int
    steps: List[ExecutionTracePathStepItem] = Field(default_factory=list)


class ExecutionExplainRequest(BaseModel):
    flowId: Optional[str] = None
    selectedSymbolId: Optional[str] = None
    depth: int = 3
    focusQuestion: Optional[str] = None


class ExecutionCitationItem(BaseModel):
    filePath: str
    startLine: int
    endLine: int


class ExecutionExplainResponse(BaseModel):
    flowId: Optional[str]
    summary: str
    verifiedSteps: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    citations: List[ExecutionCitationItem] = Field(default_factory=list)
    providerUsed: str
