import type {
  AddRepositoryInput,
  DashboardSummary,
  RepositoryOverviewDetails,
  RepositoryService,
} from './repository.service';
import type { Repository } from '@/types';
import { API_BASE, apiFetch, getAuthHeader } from './client';

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
    const res = await apiFetch('/repositories', {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!res.ok) {
      if (res.status === 401) {
        throw new Error('Authentication required to view repositories.');
      }
      throw new Error(`Failed to fetch repositories: ${res.statusText}`);
    }

    const data = await res.json();
    if (!Array.isArray(data)) return [];
    return data.map((r: any) => mapBackendRepoToFrontend(r));
  },

  async getRepository(id: string): Promise<Repository> {
    const [repoRes, overviewRes] = await Promise.all([
      apiFetch(`/repositories/${id}`),
      apiFetch(`/repositories/${id}/overview`),
    ]);

    if (!repoRes.ok) {
      throw new Error(`Repository not found (${repoRes.statusText})`);
    }

    const raw = await repoRes.json();
    const overview = overviewRes.ok ? await overviewRes.json() : undefined;
    return mapBackendRepoToFrontend(raw, overview);
  },

  async getRepositoryOverview(id: string): Promise<RepositoryOverviewDetails> {
    const res = await apiFetch(`/repositories/${id}/overview`);
    if (!res.ok) {
      throw new Error(`Failed to load repository overview: ${res.statusText}`);
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
  },

  async getDashboardSummary(): Promise<DashboardSummary> {
    const repos = await this.getRepositories();
    if (!repos || repos.length === 0) {
      return {
        totalRepositories: 0,
        analyzedRepositories: 0,
        totalSourceFiles: 0,
        detectedLanguagesCount: 0,
        languageDistribution: [],
        recentActivities: [],
      };
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
  },

  async addRepository(input: AddRepositoryInput): Promise<Repository> {
    const payload = {
      repository_url: input.url,
      branch: input.branch,
      default_branch: input.branch,
      name: input.name,
      owner: input.owner,
      is_private: input.isPrivate,
      source_type: input.isPrivate ? 'github_private' : 'github_public',
    };

    const res = await apiFetch('/repositories', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.error?.message || err?.detail || `Failed to add repository: ${res.statusText}`);
    }

    const created = await res.json();
    return mapBackendRepoToFrontend(created);
  },

  async uploadRepositoryZip(file: File, name?: string): Promise<Repository> {
    const formData = new FormData();
    formData.append('file', file);
    if (name) {
      formData.append('name', name);
    }

    const token = typeof window !== 'undefined' ? window.localStorage.getItem('repomind_access_token') : null;
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}/repositories/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.error?.message || err?.detail || `Failed to upload ZIP archive: ${res.statusText}`);
    }

    const created = await res.json();
    return mapBackendRepoToFrontend(created);
  },

  async toggleArchiveRepository(id: string): Promise<Repository> {
    const current = await this.getRepository(id);
    const res = await apiFetch(`/repositories/${id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ is_archived: !current.isArchived }),
    });

    if (!res.ok) {
      throw new Error(`Failed to toggle archive status: ${res.statusText}`);
    }

    const updated = await res.json();
    return mapBackendRepoToFrontend(updated);
  },

  async deleteRepository(id: string): Promise<void> {
    const res = await apiFetch(`/repositories/${id}`, {
      method: 'DELETE',
    });

    if (!res.ok) {
      throw new Error(`Failed to delete repository: ${res.statusText}`);
    }
  },
};
