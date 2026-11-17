import type { AnalysisStatus } from './repository';

export type FileChangeType = 'added' | 'modified' | 'deleted' | 'renamed';
export type FileCategoryType = 'source' | 'config' | 'manifest' | 'documentation' | 'other';
export type ImpactLevelType =
  | 'directly_changed'
  | 'directly_affected'
  | 'indirectly_affected'
  | 'potentially_affected'
  | 'unknown';

export interface CommitDiffFile {
  path: string;
  oldPath?: string | null;
  changeType: FileChangeType;
  fileCategory?: FileCategoryType;
  additions: number;
  deletions: number;
  oldSizeBytes?: number;
  newSizeBytes?: number;
  diffPatch?: string | null;
  summary: string;
}

export interface ChangedSymbolItem {
  id: string;
  symbolName: string;
  symbolType: string;
  scope?: string | null;
  changeType: FileChangeType;
  oldSignature?: string | null;
  newSignature?: string | null;
  evidence?: Record<string, any>;
}

export interface ImpactRecordItem {
  id: string;
  affectedType: string;
  affectedIdentifier: string;
  affectedPath: string;
  impactLevel: ImpactLevelType;
  evidenceReason: string;
  depth: number;
}

export interface UpdateRunStats {
  filesChanged: number;
  additions: number;
  deletions: number;
  symbolsChanged: number;
  endpointsAffected: number;
}

export interface ImpactMetrics {
  directlyChanged: number;
  directlyAffected: number;
  indirectlyAffected: number;
  potentiallyAffected: number;
  unknown: number;
}

export interface UpdateRunDetail {
  id: string;
  repositoryId: string;
  baseVersionId?: string | null;
  targetVersionId: string;
  baseCommitSha?: string | null;
  targetCommitSha?: string | null;
  status: string;
  stats: UpdateRunStats;
  impactMetrics: ImpactMetrics;
  impactSummary: Record<string, any>;
  aiSummaryMarkdown?: string | null;
  aiSummaryStatus: string;
  analyzedAt?: string | null;
  createdAt: string;
  fileChanges: CommitDiffFile[];
  symbolChanges: ChangedSymbolItem[];
  impactRecords: ImpactRecordItem[];
}

export interface CommitUpdateRecord {
  sha: string;
  shortSha: string;
  message: string;
  author: string;
  timestamp: string;
  analysisStatus: AnalysisStatus;
  impactSummary: string;
  changedFiles: CommitDiffFile[];
}

export interface RepositoryUpdatesData {
  repositoryId: string;
  currentAnalyzedSha: string;
  latestRemoteSha: string;
  hasPendingUpdates: boolean;
  totalRuns?: number;
  commits: CommitUpdateRecord[];
  activeRunDetail?: UpdateRunDetail | null;
}
