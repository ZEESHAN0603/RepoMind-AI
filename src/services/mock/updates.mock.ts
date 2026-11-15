import type { UpdatesService } from '@/services/api/intelligence.service';
import type { RepositoryUpdatesData } from '@/types';
import { simulateNetworkDelay } from './delay';

let updatesStore: Record<string, RepositoryUpdatesData> = {};

function buildInitialUpdates(repositoryId: string): RepositoryUpdatesData {
  return {
    repositoryId,
    currentAnalyzedSha: '71b08d2',
    latestRemoteSha: '9a4f21c',
    hasPendingUpdates: true,
    commits: [
      {
        sha: '9a4f21c8810a',
        shortSha: '9a4f21c',
        message: 'fix(auth): enforce strict token issuer validation in verifyJwtClaims',
        author: 'Priya Nair',
        timestamp: new Date(Date.now() - 1000 * 60 * 55).toISOString(),
        analysisStatus: 'pending',
        impactSummary:
          '3 files modified in authentication pipeline; incremental re-index recommended for AuthMiddleware and execution trace.',
        changedFiles: [
          {
            path: 'src/services/token-validator.service.ts',
            changeType: 'modified',
            additions: 18,
            deletions: 6,
            summary: 'Added issuer claim verification and strict length guard.',
          },
          {
            path: 'src/middleware/auth.middleware.ts',
            changeType: 'modified',
            additions: 7,
            deletions: 3,
            summary: 'Forwarded verification errors to centralized error middleware.',
          },
          {
            path: 'src/utils/token-id.ts',
            changeType: 'added',
            additions: 14,
            deletions: 0,
            summary: 'Introduced pure JTI normalization helper.',
          },
        ],
      },
      {
        sha: '71b08d2490ff',
        shortSha: '71b08d2',
        message: 'feat(ratelimit): add sliding window Redis bucket per tenant',
        author: 'Marcus Chen',
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 14).toISOString(),
        analysisStatus: 'completed',
        impactSummary:
          'Updated RateLimiter service and removed legacy fixed-window memory counter.',
        changedFiles: [
          {
            path: 'src/services/rate-limiter.service.ts',
            changeType: 'modified',
            additions: 34,
            deletions: 21,
            summary: 'Implemented tenant quota tracking with X-RateLimit-Remaining.',
          },
          {
            path: 'src/services/legacy-throttle.ts',
            changeType: 'deleted',
            additions: 0,
            deletions: 48,
            summary: 'Removed deprecated global rate limiter.',
          },
        ],
      },
    ],
  };
}

export const mockUpdatesService: UpdatesService = {
  async getRepositoryUpdates(repositoryId: string): Promise<RepositoryUpdatesData> {
    await simulateNetworkDelay(220);
    if (!updatesStore[repositoryId]) {
      updatesStore[repositoryId] = buildInitialUpdates(repositoryId);
    }
    return structuredClone(updatesStore[repositoryId]);
  },

  async triggerIncrementalReindex(repositoryId: string): Promise<RepositoryUpdatesData> {
    await simulateNetworkDelay(400);
    const current =
      updatesStore[repositoryId] ?? buildInitialUpdates(repositoryId);
    const updated: RepositoryUpdatesData = {
      ...current,
      currentAnalyzedSha: current.latestRemoteSha,
      hasPendingUpdates: false,
      commits: current.commits.map((c) => ({
        ...c,
        analysisStatus: 'completed',
      })),
    };
    updatesStore[repositoryId] = updated;
    return structuredClone(updated);
  },
};
