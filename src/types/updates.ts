import type { AnalysisStatus } from './repository';

export type FileChangeType = 'added' | 'modified' | 'deleted';

export interface CommitDiffFile {
  path: string;
  changeType: FileChangeType;
  additions: number;
  deletions: number;
  summary: string;
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
  commits: CommitUpdateRecord[];
}
