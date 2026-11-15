import type { GroundingConfidence } from './repository';

export type ArchNodeCategory =
  | 'frontend'
  | 'backend'
  | 'api'
  | 'database'
  | 'authentication'
  | 'external'
  | 'internal'
  | 'utility'
  | 'ai'
  | 'worker';

export type ArchitectureViewMode =
  | 'system'
  | 'frontend'
  | 'backend'
  | 'api'
  | 'database'
  | 'modules';

export interface ArchitectureNodeData {
  id: string;
  label: string;
  category: ArchNodeCategory;
  group: string;
  filePath: string;
  description: string;
  exports: string[];
  confidence: GroundingConfidence;
  position: { x: number; y: number };
}

export interface ArchitectureEdgeData {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence: GroundingConfidence;
}

export interface ArchitectureViewPayload {
  viewMode: ArchitectureViewMode;
  title: string;
  subtitle: string;
  nodes: ArchitectureNodeData[];
  edges: ArchitectureEdgeData[];
}

export interface ArchitectureGraphData {
  repositoryId: string;
  nodes: ArchitectureNodeData[];
  edges: ArchitectureEdgeData[];
  views: Record<ArchitectureViewMode, ArchitectureViewPayload>;
}

export type ExecutionStatus = 'verified' | 'inferred' | 'unresolved';

export type ExecutionNodeType =
  | 'function'
  | 'api'
  | 'method'
  | 'database'
  | 'external';

export interface ExecutionStep {
  stepOrder: number;
  nodeId: string;
  functionName: string;
  moduleName: string;
  nodeType: ExecutionNodeType;
  filePath: string;
  lineNumber: number;
  caller: string;
  callee: string;
  dataPassed: string;
  description: string;
  status: ExecutionStatus;
}

export interface ExecutionFlow {
  id: string;
  title: string;
  triggerType: 'api-endpoint' | 'function' | 'event';
  entryPoint: string;
  summary: string;
  rootNodeId: string;
  steps: ExecutionStep[];
}

export interface ExecutionFunctionSymbol {
  id: string;
  name: string;
  filePath: string;
  lineNumber: number;
  nodeType: ExecutionNodeType;
  parameters: string;
  returnType: string;
  description: string;
  status: ExecutionStatus;
  callers: string[];
  callees: string[];
  relatedFunctions: string[];
  codeSnippet: string;
}

export interface ExecutionGraphNode {
  id: string;
  label: string;
  nodeType: ExecutionNodeType;
  filePath: string;
  lineNumber: number;
  parameters: string;
  returnType: string;
  description: string;
  status: ExecutionStatus;
  callers: string[];
  callees: string[];
  relatedFunctions: string[];
  codeSnippet: string;
  position: { x: number; y: number };
  depth: number;
}

export interface ExecutionGraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  status: ExecutionStatus;
  dataPassed?: string;
}

export interface ExecutionEntryGraph {
  flow: ExecutionFlow;
  nodes: ExecutionGraphNode[];
  edges: ExecutionGraphEdge[];
}

export interface ExecutionTraceWorkspace {
  repositoryId: string;
  repositoryName: string;
  functions: ExecutionFunctionSymbol[];
  traces: ExecutionEntryGraph[];
}
