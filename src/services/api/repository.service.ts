import type {
  DashboardActivity,
  ImportantModule,
  LanguageDistributionItem,
  Repository,
  RepositoryCommit,
} from '@/types';

export interface DashboardSummary {
  totalRepositories: number;
  analyzedRepositories: number;
  totalSourceFiles: number;
  detectedLanguagesCount: number;
  languageDistribution: LanguageDistributionItem[];
  recentActivities: DashboardActivity[];
}

export interface RepositoryOverviewDetails {
  repository: Repository;
  recentCommits: RepositoryCommit[];
  importantModules: ImportantModule[];
  dependencyStats: {
    internalModules: number;
    externalPackages: number;
    circularCycles: number;
  };
}

export interface AddRepositoryInput {
  name?: string;
  owner?: string;
  url: string;
  branch: string;
  isPrivate: boolean;
  sourceType: 'github' | 'zip';
}

export interface RepositoryService {
  getRepositories(): Promise<Repository[]>;
  getRepository(id: string): Promise<Repository>;
  getRepositoryOverview(id: string): Promise<RepositoryOverviewDetails>;
  getDashboardSummary(): Promise<DashboardSummary>;
  addRepository(input: AddRepositoryInput): Promise<Repository>;
  uploadRepositoryZip?(file: File, name?: string): Promise<Repository>;
  toggleArchiveRepository(id: string): Promise<Repository>;
  deleteRepository(id: string): Promise<void>;
}
