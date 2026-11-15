import type {
  AddRepositoryInput,
  DashboardSummary,
  RepositoryOverviewDetails,
  RepositoryService,
} from '@/services/api/repository.service';
import type {
  DashboardActivity,
  ImportantModule,
  LanguageDistributionItem,
  Repository,
  RepositoryCommit,
} from '@/types';
import { simulateNetworkDelay } from './delay';

const INITIAL_REPOSITORIES: Repository[] = [
  {
    id: 'repo-cloud-gateway',
    name: 'cloud-gateway',
    owner: 'acme-platform',
    url: 'https://github.com/acme-platform/cloud-gateway',
    branch: 'main',
    availableBranches: ['main', 'develop', 'release/v2.4'],
    commitSha: '9a4f21c',
    description:
      'Edge API gateway with JWT verification, rate-limiting middleware, and upstream service routing.',
    language: 'TypeScript',
    languages: {
      TypeScript: 68,
      SQL: 14,
      Shell: 10,
      Dockerfile: 8,
    },
    frameworks: ['Node.js', 'Express', 'PostgreSQL', 'Redis'],
    status: 'completed',
    fileCount: 142,
    folderCount: 24,
    lastAnalyzed: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
    isPrivate: false,
    isArchived: false,
    sourceType: 'github',
  },
  {
    id: 'repo-billing-ledger',
    name: 'billing-ledger',
    owner: 'acme-finance',
    url: 'https://github.com/acme-finance/billing-ledger',
    branch: 'main',
    availableBranches: ['main', 'staging'],
    commitSha: '4c81e0b',
    description:
      'Double-entry subscription ledger, invoice reconciliation worker, and webhook event processor.',
    language: 'Python',
    languages: {
      Python: 76,
      SQL: 16,
      YAML: 8,
    },
    frameworks: ['FastAPI', 'SQLAlchemy', 'Celery', 'PostgreSQL'],
    status: 'completed',
    fileCount: 98,
    folderCount: 17,
    lastAnalyzed: new Date(Date.now() - 1000 * 60 * 60 * 4).toISOString(),
    isPrivate: true,
    isArchived: false,
    sourceType: 'github',
  },
  {
    id: 'repo-analytics-web',
    name: 'analytics-web',
    owner: 'acme-platform',
    url: 'https://github.com/acme-platform/analytics-web',
    branch: 'develop',
    availableBranches: ['main', 'develop'],
    commitSha: '7d22a91',
    description:
      'Customer-facing product analytics workspace with query builder, funnel charts, and CSV exports.',
    language: 'TypeScript',
    languages: {
      TypeScript: 82,
      CSS: 12,
      HTML: 6,
    },
    frameworks: ['React', 'Vite', 'Tailwind CSS', 'TanStack Query'],
    status: 'analyzing',
    fileCount: 215,
    folderCount: 38,
    lastAnalyzed: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    isPrivate: false,
    isArchived: false,
    sourceType: 'github',
  },
  {
    id: 'repo-token-cli',
    name: 'design-tokens-cli',
    owner: 'acme-design',
    url: 'zip://design-tokens-cli.zip',
    branch: 'main',
    availableBranches: ['main'],
    commitSha: 'f103d4e',
    description:
      'CLI compiler converting W3C design token JSON into CSS custom properties and Tailwind presets.',
    language: 'Go',
    languages: {
      Go: 88,
      JSON: 12,
    },
    frameworks: ['Cobra CLI'],
    status: 'failed',
    fileCount: 44,
    folderCount: 9,
    lastAnalyzed: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString(),
    isPrivate: false,
    isArchived: false,
    sourceType: 'zip',
  },
];

let repositoriesStore: Repository[] = [...INITIAL_REPOSITORIES];

const MOCK_COMMITS_BY_REPO: Record<string, RepositoryCommit[]> = {
  'repo-cloud-gateway': [
    {
      sha: '9a4f21c',
      message: 'fix(auth): enforce strict token issuer validation in verifyJwt',
      author: 'Priya Nair',
      date: new Date(Date.now() - 1000 * 60 * 55).toISOString(),
      filesChanged: 3,
    },
    {
      sha: '71b08d2',
      message: 'feat(ratelimit): add sliding window Redis bucket per tenant',
      author: 'Marcus Chen',
      date: new Date(Date.now() - 1000 * 60 * 60 * 14).toISOString(),
      filesChanged: 5,
    },
    {
      sha: '3e904a1',
      message: 'refactor(proxy): extract upstream health probe into worker',
      author: 'Elena Rostova',
      date: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
      filesChanged: 4,
    },
  ],
  'repo-billing-ledger': [
    {
      sha: '4c81e0b',
      message: 'feat(reconcile): idempotent Stripe payout batch matcher',
      author: 'David Kim',
      date: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString(),
      filesChanged: 4,
    },
    {
      sha: '18f55aa',
      message: 'fix(ledger): prevent rounding drift on multi-currency credits',
      author: 'Sarah Jenkins',
      date: new Date(Date.now() - 1000 * 60 * 60 * 30).toISOString(),
      filesChanged: 2,
    },
  ],
};

const MOCK_MODULES_BY_REPO: Record<string, ImportantModule[]> = {
  'repo-cloud-gateway': [
    {
      name: 'AuthMiddleware',
      path: 'src/middleware/auth.middleware.ts',
      role: 'Verifies bearer JWTs, resolves tenant context, and rejects expired sessions.',
      symbolCount: 6,
      confidence: 'verified',
    },
    {
      name: 'RateLimiter',
      path: 'src/services/rate-limiter.service.ts',
      role: 'Enforces sliding-window request quotas backed by Redis Lua scripts.',
      symbolCount: 4,
      confidence: 'verified',
    },
    {
      name: 'UpstreamRouter',
      path: 'src/routes/proxy.router.ts',
      role: 'Matches incoming paths to upstream microservice clusters and injects trace headers.',
      symbolCount: 8,
      confidence: 'inferred',
    },
    {
      name: 'SessionStore',
      path: 'src/services/session.service.ts',
      role: 'Manages refresh token rotation and revocation checks.',
      symbolCount: 5,
      confidence: 'verified',
    },
  ],
  'repo-billing-ledger': [
    {
      name: 'LedgerEngine',
      path: 'app/domain/ledger_engine.py',
      role: 'Validates balanced debit/credit journal entries before persistence.',
      symbolCount: 9,
      confidence: 'verified',
    },
    {
      name: 'WebhookProcessor',
      path: 'app/api/webhooks.py',
      role: 'Verifies payment provider signatures and dispatches async tasks.',
      symbolCount: 5,
      confidence: 'verified',
    },
  ],
};

const LANGUAGE_COLORS: Record<string, string> = {
  TypeScript: '#4f46e5',
  Python: '#0284c7',
  Go: '#16a34a',
  SQL: '#d97706',
  CSS: '#7c3aed',
  Shell: '#64748b',
  Dockerfile: '#0ea5e9',
  JSON: '#94a3b8',
  YAML: '#eab308',
  HTML: '#f97316',
};

export const mockRepositoryService: RepositoryService = {
  async getRepositories() {
    await simulateNetworkDelay(220);
    return [...repositoriesStore];
  },

  async getRepository(id: string) {
    await simulateNetworkDelay(180);
    const repo = repositoriesStore.find((item) => item.id === id);
    if (!repo) {
      throw new Error(`Repository "${id}" was not found.`);
    }
    return { ...repo };
  },

  async getRepositoryOverview(id: string): Promise<RepositoryOverviewDetails> {
    await simulateNetworkDelay(240);
    const repo = repositoriesStore.find((item) => item.id === id);
    if (!repo) {
      throw new Error(`Repository "${id}" was not found.`);
    }
    return {
      repository: { ...repo },
      recentCommits: MOCK_COMMITS_BY_REPO[id] ?? [
        {
          sha: repo.commitSha,
          message: 'chore: initial sample repository snapshot indexed',
          author: 'Sample Maintainer',
          date: repo.lastAnalyzed,
          filesChanged: 12,
        },
      ],
      importantModules: MOCK_MODULES_BY_REPO[id] ?? [
        {
          name: 'CoreEntry',
          path: 'src/index.ts',
          role: 'Application entry point and module bootstrapper.',
          symbolCount: 4,
          confidence: 'inferred',
        },
      ],
      dependencyStats: {
        internalModules: Math.max(8, Math.round(repo.fileCount * 0.35)),
        externalPackages: Math.max(5, Math.round(repo.fileCount * 0.14)),
        circularCycles: id === 'repo-cloud-gateway' ? 2 : 1,
      },
    };
  },

  async getDashboardSummary(): Promise<DashboardSummary> {
    await simulateNetworkDelay(200);
    const activeRepos = repositoriesStore.filter((r) => !r.isArchived);
    const analyzed = activeRepos.filter((r) => r.status === 'completed');
    const totalFiles = activeRepos.reduce((acc, r) => acc + r.fileCount, 0);

    const langTotals: Record<string, number> = {};
    for (const repo of activeRepos) {
      for (const [lang, pct] of Object.entries(repo.languages)) {
        const estimatedFiles = Math.max(1, Math.round((pct / 100) * repo.fileCount));
        langTotals[lang] = (langTotals[lang] ?? 0) + estimatedFiles;
      }
    }

    const totalLangFiles = Object.values(langTotals).reduce((a, b) => a + b, 0) || 1;
    const languageDistribution: LanguageDistributionItem[] = Object.entries(langTotals)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([language, fileCount]) => ({
        language,
        fileCount,
        percentage: Math.round((fileCount / totalLangFiles) * 100),
        color: LANGUAGE_COLORS[language] ?? '#6366f1',
      }));

    const recentActivities: DashboardActivity[] = [
      {
        id: 'act-1',
        repositoryId: 'repo-cloud-gateway',
        repositoryName: 'acme-platform/cloud-gateway',
        action: 'Completed static analysis & dependency graph (142 files)',
        timestamp: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
        status: 'completed',
      },
      {
        id: 'act-2',
        repositoryId: 'repo-analytics-web',
        repositoryName: 'acme-platform/analytics-web',
        action: 'Indexing symbol references on branch develop',
        timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
        status: 'analyzing',
      },
      {
        id: 'act-3',
        repositoryId: 'repo-billing-ledger',
        repositoryName: 'acme-finance/billing-ledger',
        action: 'Detected 1 potential circular import cycle',
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 4).toISOString(),
        status: 'completed',
      },
      {
        id: 'act-4',
        repositoryId: 'repo-token-cli',
        repositoryName: 'acme-design/design-tokens-cli',
        action: 'ZIP parser encountered unsupported symlink entry (sample error)',
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString(),
        status: 'failed',
      },
    ];

    return {
      totalRepositories: activeRepos.length,
      analyzedRepositories: analyzed.length,
      totalSourceFiles: totalFiles,
      detectedLanguagesCount: Object.keys(langTotals).length,
      languageDistribution,
      recentActivities,
    };
  },

  async addRepository(input: AddRepositoryInput): Promise<Repository> {
    await simulateNetworkDelay(350);
    const cleanName =
      input.name ||
      input.url.split('/').pop()?.replace(/\.git$/, '') ||
      'sample-repository';
    const cleanOwner =
      input.owner || input.url.split('/').slice(-2, -1)[0] || 'workspace';
    const id = `repo-${cleanName.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${Date.now().toString().slice(-4)}`;

    const newRepo: Repository = {
      id,
      name: cleanName,
      owner: cleanOwner,
      url: input.url,
      branch: input.branch || 'main',
      availableBranches: [input.branch || 'main', 'develop'],
      commitSha: Math.random().toString(16).slice(2, 9),
      description:
        input.sourceType === 'zip'
          ? `Uploaded ZIP archive (${cleanName}) analyzed with sample Phase 1 static intelligence.`
          : `Connected GitHub repository (${cleanOwner}/${cleanName}) analyzed with sample Phase 1 intelligence.`,
      language: 'TypeScript',
      languages: {
        TypeScript: 72,
        JSON: 16,
        Markdown: 12,
      },
      frameworks: ['React', 'TypeScript', 'Node.js'],
      status: 'completed',
      fileCount: 64,
      folderCount: 12,
      lastAnalyzed: new Date().toISOString(),
      isPrivate: input.isPrivate,
      isArchived: false,
      sourceType: input.sourceType,
    };

    repositoriesStore = [newRepo, ...repositoriesStore];
    return { ...newRepo };
  },

  async toggleArchiveRepository(id: string): Promise<Repository> {
    await simulateNetworkDelay(180);
    let updated: Repository | undefined;
    repositoriesStore = repositoriesStore.map((repo) => {
      if (repo.id === id) {
        updated = { ...repo, isArchived: !repo.isArchived };
        return updated;
      }
      return repo;
    });
    if (!updated) {
      throw new Error(`Repository "${id}" was not found.`);
    }
    return { ...updated };
  },

  async deleteRepository(id: string): Promise<void> {
    await simulateNetworkDelay(200);
    repositoriesStore = repositoriesStore.filter((repo) => repo.id !== id);
  },
};
