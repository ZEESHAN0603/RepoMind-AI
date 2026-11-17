import type { GroundingConfidence } from './repository';

export type DocSectionType =
  | 'readme'
  | 'architecture'
  | 'module'
  | 'api'
  | 'execution_flow'
  | 'dependencies'
  | 'update_changelog'
  | 'code_reference';

export interface DocumentVersionItem {
  id: string;
  documentId: string;
  repositoryId: string;
  versionNumber: number;
  content: string;
  changeSummary?: string | null;
  createdBy?: string | null;
  createdAt: string;
}

export interface DocumentationDocument {
  id: string;
  repositoryId: string;
  type: string;
  title: string;
  description: string;
  content: string;
  status: 'draft' | 'approved' | 'stale' | 'generating' | 'failed';
  confidence: GroundingConfidence;
  versionNumber: number;
  lastUpdated: string;
  approvedAt?: string | null;
  approvedBy?: string | null;
  sourceEvidence?: Record<string, any>;
  versions?: DocumentVersionItem[];
}

export interface DocumentDiffData {
  docType: string;
  baseVersion: number;
  targetVersion: number;
  diffPatch: string;
  baseContent: string;
  targetContent: string;
}
