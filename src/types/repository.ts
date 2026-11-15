export type AnalysisStatus = 'pending' | 'analyzing' | 'completed' | 'failed';

export type GroundingConfidence = 'verified' | 'inferred' | 'unknown';

export interface Repository {
  id: string;
  name: string;
  owner: string;
  url: string;
  branch: string;
  availableBranches: string[];
  commitSha: string;
  description: string;
  language: string;
  languages: Record<string, number>;
  frameworks: string[];
  status: AnalysisStatus;
  fileCount: number;
  folderCount: number;
  lastAnalyzed: string;
  isPrivate: boolean;
  isArchived?: boolean;
  sourceType: 'github' | 'zip';
}

export interface RepositoryCommit {
  sha: string;
  message: string;
  author: string;
  date: string;
  filesChanged: number;
}

export interface ImportantModule {
  name: string;
  path: string;
  role: string;
  symbolCount: number;
  confidence: GroundingConfidence;
}

export interface RepositoryFileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'folder';
  language?: string;
  sizeBytes?: number;
  children?: RepositoryFileNode[];
}

export interface CodeSymbol {
  id: string;
  name: string;
  kind: 'function' | 'class' | 'interface' | 'endpoint' | 'hook';
  startLine: number;
  endLine: number;
  signature: string;
  summary: string;
  confidence: GroundingConfidence;
}

export interface FileIntelligence {
  path: string;
  language: string;
  content: string;
  explanation: string;
  confidence: GroundingConfidence;
  symbols: CodeSymbol[];
  relatedFiles: string[];
  dependencies: string[];
  sourceReferences: { label: string; line: number }[];
}

export interface DashboardActivity {
  id: string;
  repositoryId: string;
  repositoryName: string;
  action: string;
  timestamp: string;
  status: AnalysisStatus;
}

export interface LanguageDistributionItem {
  language: string;
  fileCount: number;
  percentage: number;
  color: string;
}
