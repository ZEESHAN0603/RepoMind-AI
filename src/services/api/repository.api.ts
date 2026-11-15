import type {
  AddRepositoryInput,
  DashboardSummary,
  RepositoryOverviewDetails,
  RepositoryService,
} from './repository.service';
import type { Repository } from '@/types';
import { mockRepositoryService } from '@/services/mock/repository.mock';

const API_BASE = '/api/v1';

function getAuthHeader(): Record<string, string> {
  // If stored in localStorage or session
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('repomind_access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function mapBackendRepoToFrontend(raw: any, overview?: any): Repository {
  const languages: Record<string, number> = {};
  if (overview && overview.languages) {
    for (const l of overview.languages) {
      languages[l.language] = Math.round(l.percentage);
    }
  }

  const frameworks: string[] = [];
  if (overview && overview.manifests) {
    for (const m of overview.manifests) {
      if (Array.isArray(m.detected_frameworks)) {
        frameworks.push(...m.detected_frameworks);
      }
    }
  }

  const availableBranches: string[] = [];
  if (overview && overview.available_branches) {
    for (const b of overview.available_branches) {
      availableBranches.push(b.name);
    }
  }

  return {
    id: raw.id,
    name: raw.name,
    owner: raw.owner,
    url: raw.repository_url,
    branch: raw.default_branch || 'main',
    availableBranches: availableBranches.length > 0 ? availableBranches : [raw.default_branch || 'main'],
    commitSha: raw.current_commit_sha || 'latest',
    description: raw.description || '',
    language: Object.keys(languages)[0] || 'Python',
    languages: Object.keys(languages).length > 0 ? languages : { Python: 100 },
    frameworks: Array.from(new Set(frameworks)),
    status: (raw.status === 'completed' ? 'completed' : raw.status === 'failed' ? 'failed' : raw.status === 'ingesting' ? 'analyzing' : 'pending'),
    fileCount: raw.file_count || (overview?.file_count ?? 0),
    folderCount: raw.folder_count || (overview?.folder_count ?? 0),
    lastAnalyzed: raw.last_analyzed_at || raw.updated_at,
    isPrivate: raw.visibility === 'private',
    isArchived: raw.is_archived || false,
    sourceType: raw.source_type === 'zip_upload' ? 'zip' : 'github',
  };
}

export const apiRepositoryService: RepositoryService = {
  async getRepositories(): Promise<Repository[]> {
    try {
      const res = await fetch(`${API_BASE}/repositories`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });
      if (!res.ok) {
        return mockRepositoryService.getRepositories();
      }
      const data = await res.json();
      return data.map((r: any) => mapBackendRepoToFrontend(r));
    } catch {
      return mockRepositoryService.getRepositories();
    }
  },

  async getRepository(id: string): Promise<Repository> {
    try {
      const [repoRes, overviewRes] = await Promise.all([
        fetch(`${API_BASE}/repositories/${id}`, { headers: getAuthHeader() }),
        fetch(`${API_BASE}/repositories/${id}/overview`, { headers: getAuthHeader() }),
      ]);
      if (!repoRes.ok) {
        return mockRepositoryService.getRepository(id);
      }
      const raw = await repoRes.json();
      const overview = overviewRes.ok ? await overviewRes.json() : undefined;
      return mapBackendRepoToFrontend(raw, overview);
    } catch {
      return mockRepositoryService.getRepository(id);
    }
  },

  async getRepositoryOverview(id: string): Promise<RepositoryOverviewDetails> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${id}/overview`, { headers: getAuthHeader() });
      if (!res.ok) {
        return mockRepositoryService.getRepositoryOverview(id);
      }
      const data = await res.json();
      const repo = mapBackendRepoToFrontend(data.repository, data);
      return {
        repository: repo,
        recentCommits: [
          {
            sha: data.repository.current_commit_sha || 'main',
            message: 'Latest ingestion snapshot',
            author: data.repository.owner,
            date: data.repository.last_analyzed_at || new Date().toISOString(),
            filesChanged: data.file_count || 0,
          },
        ],
        importantModules: [],
        dependencyStats: {
          internalModules: data.folder_count || 0,
          externalPackages: data.manifests ? data.manifests.length : 0,
          circularCycles: 0,
        },
      };
    } catch {
      return mockRepositoryService.getRepositoryOverview(id);
    }
  },

  async getDashboardSummary(): Promise<DashboardSummary> {
    try {
      const repos = await this.getRepositories();
      if (!repos || repos.length === 0) {
        return mockRepositoryService.getDashboardSummary();
      }
      const totalRepositories = repos.length;
      const analyzedRepositories = repos.filter((r) => r.status === 'completed').length;
      const totalSourceFiles = repos.reduce((acc, r) => acc + r.fileCount, 0);

      const langCounts: Record<string, number> = {};
      repos.forEach((r) => {
        Object.keys(r.languages).forEach((l) => {
          langCounts[l] = (langCounts[l] || 0) + 1;
        });
      });

      return {
        totalRepositories,
        analyzedRepositories,
        totalSourceFiles,
        detectedLanguagesCount: Object.keys(langCounts).length,
        languageDistribution: Object.entries(langCounts).map(([lang, count]) => ({
          language: lang,
          fileCount: count,
          percentage: Math.round((count / Math.max(1, totalRepositories)) * 100),
          color: '#3178C6',
        })),
        recentActivities: repos.slice(0, 5).map((r) => ({
          id: `act-${r.id}`,
          repositoryId: r.id,
          repositoryName: r.name,
          action: `Repository ${r.status}`,
          timestamp: r.lastAnalyzed,
          status: r.status,
        })),
      };
    } catch {
      return mockRepositoryService.getDashboardSummary();
    }
  },

  async addRepository(input: AddRepositoryInput): Promise<Repository> {
    try {
      const payload = {
        repository_url: input.url,
        branch: input.branch,
        default_branch: input.branch,
        name: input.name,
        owner: input.owner,
        is_private: input.isPrivate,
        source_type: input.sourceType === 'zip' ? 'zip_upload' : (input.isPrivate ? 'github_private' : 'github_public'),
      };
      const res = await fetch(`${API_BASE}/repositories`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || `Failed to add repository: ${res.statusText}`);
      }
      const created = await res.json();
      return mapBackendRepoToFrontend(created);
    } catch (e) {
      if (e instanceof Error && e.message.includes('Failed to add')) {
        throw e;
      }
      return mockRepositoryService.addRepository(input);
    }
  },

  async toggleArchiveRepository(id: string): Promise<Repository> {
    try {
      const current = await this.getRepository(id);
      const res = await fetch(`${API_BASE}/repositories/${id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify({ is_archived: !current.isArchived }),
      });
      if (res.ok) {
        const updated = await res.json();
        return mapBackendRepoToFrontend(updated);
      }
    } catch {
      // fallback
    }
    return mockRepositoryService.toggleArchiveRepository(id);
  },

  async deleteRepository(id: string): Promise<void> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${id}`, {
        method: 'DELETE',
        headers: getAuthHeader(),
      });
      if (res.ok) return;
    } catch {
      // fallback
    }
    return mockRepositoryService.deleteRepository(id);
  },
};

