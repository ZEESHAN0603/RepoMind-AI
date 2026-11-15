import type { GroundingConfidence } from './repository';

export type DependencyCategory = 'internal' | 'external' | 'circular';
export type DependencyNodeType = 'module' | 'file' | 'package' | 'service';
export type CycleSeverity = 'high' | 'medium' | 'low';

export interface DependencyModuleNode {
  id: string;
  label: string;
  filePath: string;
  nodeType: DependencyNodeType;
  category: 'internal' | 'external';
  language: string;
  exportsCount: number;
  position: { x: number; y: number };
}

export interface DependencyRelationship {
  id: string;
  sourceModule: string;
  sourcePath: string;
  targetModule: string;
  targetPath: string;
  category: DependencyCategory;
  language: string;
  importSpecifiers: string[];
  confidence: GroundingConfidence;
}

export interface CircularDependencyCycle {
  id: string;
  severity: CycleSeverity;
  cyclePath: string[];
  filePaths: string[];
  affectedCount: number;
  description: string;
  impact: string;
  recommendation: string;
  confidence: GroundingConfidence;
}

export interface DependencyAnalysisData {
  repositoryId: string;
  lastAnalyzed: string;
  totalModules: number;
  totalImports: number;
  internalCount: number;
  externalCount: number;
  circularCount: number;
  nodes: DependencyModuleNode[];
  relationships: DependencyRelationship[];
  cycles: CircularDependencyCycle[];
}
