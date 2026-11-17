import type { UpdatesService } from './intelligence.service';
import type {
  CommitDiffFile,
  CommitUpdateRecord,
  RepositoryUpdatesData,
  UpdateRunDetail,
} from '@/types';
import { mockUpdatesService } from '@/services/mock/updates.mock';

const API_BASE = '/api/v1';

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('repomind_access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiUpdatesService implements UpdatesService {
  async getRepositoryUpdates(repositoryId: string): Promise<RepositoryUpdatesData> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/updates/history`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });

      if (!res.ok) {
        return mockUpdatesService.getRepositoryUpdates(repositoryId);
      }

      const raw = await res.json();
      const commits: CommitUpdateRecord[] = [];

      for (const run of raw.update_runs || []) {
        const target = run.target_version;
        commits.push({
          sha: run.target_commit_sha || target?.commit_sha || run.id,
          shortSha: (run.target_commit_sha || target?.commit_sha || run.id).slice(0, 7),
          message: target?.commit_message || `Update analysis run ${run.id.slice(0, 8)}`,
          author: target?.author_name || 'Author',
          timestamp: target?.commit_timestamp || run.analyzed_at || run.created_at,
          analysisStatus: run.status === 'completed' ? 'completed' : run.status === 'failed' ? 'failed' : 'pending',
          impactSummary: `${run.total_files_changed} files changed, ${run.total_symbols_changed} symbols analyzed (+${run.total_additions}/-${run.total_deletions})`,
          changedFiles: [],
        });
      }

      // If no runs yet, check if there are versions or fall back
      if (commits.length === 0 && (!raw.versions || raw.versions.length === 0)) {
        return mockUpdatesService.getRepositoryUpdates(repositoryId);
      }

      // Fetch the latest run detail if available
      let activeRunDetail: UpdateRunDetail | null = null;
      if (raw.update_runs && raw.update_runs.length > 0) {
        try {
          activeRunDetail = await this.getUpdateRunDetail(repositoryId, raw.update_runs[0].id);
          if (activeRunDetail && commits.length > 0) {
            commits[0].changedFiles = activeRunDetail.fileChanges;
          }
        } catch {
          // ignore
        }
      }

      return {
        repositoryId,
        currentAnalyzedSha: raw.current_commit_sha || (commits[0]?.shortSha ?? 'main'),
        latestRemoteSha: raw.latest_remote_sha || (commits[0]?.shortSha ?? 'main'),
        hasPendingUpdates: raw.has_pending_updates ?? false,
        totalRuns: raw.total_runs ?? commits.length,
        commits,
        activeRunDetail,
      };
    } catch {
      return mockUpdatesService.getRepositoryUpdates(repositoryId);
    }
  }

  async triggerIncrementalReindex(repositoryId: string): Promise<RepositoryUpdatesData> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/updates/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify({ include_ai_summary: true }),
      });

      if (!res.ok) {
        return mockUpdatesService.triggerIncrementalReindex(repositoryId);
      }

      return this.getRepositoryUpdates(repositoryId);
    } catch {
      return mockUpdatesService.triggerIncrementalReindex(repositoryId);
    }
  }

  async getUpdateRunDetail(repositoryId: string, runId: string): Promise<UpdateRunDetail> {
    const res = await fetch(`${API_BASE}/repositories/${repositoryId}/updates/${runId}`, {
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
    });

    if (!res.ok) {
      throw new Error(`Failed to load update run ${runId}`);
    }

    const data = await res.json();
    return {
      id: data.id,
      repositoryId: data.repository_id,
      baseVersionId: data.base_version_id,
      targetVersionId: data.target_version_id,
      baseCommitSha: data.base_commit_sha,
      targetCommitSha: data.target_commit_sha,
      status: data.status,
      stats: {
        filesChanged: data.stats?.files_changed ?? data.total_files_changed ?? 0,
        additions: data.stats?.additions ?? data.total_additions ?? 0,
        deletions: data.stats?.deletions ?? data.total_deletions ?? 0,
        symbolsChanged: data.stats?.symbols_changed ?? data.total_symbols_changed ?? 0,
        endpointsAffected: data.stats?.endpoints_affected ?? 0,
      },
      impactMetrics: {
        directlyChanged: data.impact_metrics?.directly_changed ?? 0,
        directlyAffected: data.impact_metrics?.directly_affected ?? 0,
        indirectlyAffected: data.impact_metrics?.indirectly_affected ?? 0,
        potentiallyAffected: data.impact_metrics?.potentially_affected ?? 0,
        unknown: data.impact_metrics?.unknown ?? 0,
      },
      impactSummary: data.impact_summary || {},
      aiSummaryMarkdown: data.ai_summary_markdown,
      aiSummaryStatus: data.ai_summary_status,
      analyzedAt: data.analyzed_at,
      createdAt: data.created_at,
      fileChanges: (data.file_changes || []).map((f: any) => ({
        path: f.path,
        oldPath: f.old_path,
        changeType: f.change_type,
        fileCategory: f.file_category,
        additions: f.additions,
        deletions: f.deletions,
        diffPatch: f.diff_patch,
        summary: f.summary || `${f.change_type} ${f.path}`,
      })),
      symbolChanges: (data.symbol_changes || []).map((s: any) => ({
        id: s.id,
        symbolName: s.symbol_name,
        symbolType: s.symbol_type,
        scope: s.scope,
        changeType: s.change_type,
        oldSignature: s.old_signature,
        newSignature: s.new_signature,
        evidence: s.evidence || {},
      })),
      impactRecords: (data.impact_records || []).map((r: any) => ({
        id: r.id,
        affectedType: r.affected_type,
        affectedIdentifier: r.affected_identifier,
        affectedPath: r.affected_path,
        impactLevel: r.impact_level,
        evidenceReason: r.evidence_reason,
        depth: r.depth,
      })),
    };
  }

  async generateExplanation(repositoryId: string, runId: string, focus?: string): Promise<string> {
    const res = await fetch(`${API_BASE}/repositories/${repositoryId}/updates/${runId}/explain`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify({ focus }),
    });

    if (!res.ok) {
      throw new Error('Failed to generate AI change explanation');
    }

    const data = await res.json();
    return data.ai_summary_markdown;
  }
}

export const apiUpdatesService = new ApiUpdatesService();
