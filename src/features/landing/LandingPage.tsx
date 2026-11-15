import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  FileCode2,
  FolderTree,
  GitBranch,
  GitCompare,
  Layers,
  MessageSquareCode,
  Network,
  Share2,
  ShieldCheck,
  Sparkles,
  Upload,
} from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ConfidenceBadge } from '@/components/common/ConfidenceBadge';
import {
  PageFadeIn,
  StaggerGrid,
  StaggerItem,
} from '@/components/common/MotionPrimitives';
import { RepoMindLogo } from '@/components/common/RepoMindLogo';
import { ThemeToggle } from '@/components/common/ThemeToggle';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { APP_ROUTES, getRepositoryRoute } from '@/constants/routes';
import { cn } from '@/lib/utils';
import { repositoryService } from '@/services';
import { useAuthStore } from '@/stores/auth.store';
import { parseGitHubUrl } from '@/utils/formatters';

type PreviewTab = 'architecture' | 'trace' | 'explanation' | 'dependencies';

const PREVIEW_FILES = [
  {
    name: 'server.ts',
    path: 'src/server.ts',
    summary: 'Express bootstrap mounting /api proxy router and error middleware.',
  },
  {
    name: 'proxy.router.ts',
    path: 'src/routes/proxy.router.ts',
    summary: 'Dispatches /v1/:service/* through auth and tenant rate limits.',
  },
  {
    name: 'auth.middleware.ts',
    path: 'src/middleware/auth.middleware.ts',
    summary: 'Validates Bearer JWT claims and checks JTI revocation state.',
  },
  {
    name: 'session.service.ts',
    path: 'src/services/session.service.ts',
    summary: 'Maintains active revocation store for issued session tokens.',
  },
];

const FEATURE_CARDS = [
  {
    icon: FolderTree,
    title: 'Three-Panel Code Explorer',
    desc: 'Browse folder hierarchies, read syntax-highlighted files in Monaco Editor, jump directly to symbols, and view line-cited explanations side by side.',
  },
  {
    icon: Network,
    title: 'Interactive Architecture Graph',
    desc: 'Switch across 6 architectural views, filter 10 node categories, collapse logical groups, lock layouts, and open any defining source file.',
  },
  {
    icon: Activity,
    title: 'Execution Flow Tracing',
    desc: 'Trace API endpoints and functions step-by-step with expandable callers and callees marked Verified, Inferred, or Unresolved.',
  },
  {
    icon: Share2,
    title: 'Circular Dependency Detection',
    desc: 'Inspect module import graphs by language, isolate mutual dependency cycles in red, and review targeted refactoring recommendations.',
  },
  {
    icon: MessageSquareCode,
    title: 'Grounded AI Assistant',
    desc: 'Ask architectural questions with suggested prompts and inspect file-path + line-number citations alongside confidence indicators.',
  },
  {
    icon: BookOpen,
    title: 'Living Documentation Center',
    desc: 'Edit and preview Markdown + Mermaid documentation across Overview, API, Architecture, Modules, Dependencies, and Onboarding specs.',
  },
  {
    icon: GitCompare,
    title: 'Commit Diffs & Re-Indexing',
    desc: 'Review commit-level file changes, additions/deletions, and run incremental sample re-indexing when new commits arrive.',
  },
];

export function LandingPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const [githubUrl, setGithubUrl] = useState(
    'https://github.com/acme-platform/cloud-gateway'
  );
  const [urlError, setUrlError] = useState<string | null>(null);
  const [previewTab, setPreviewTab] = useState<PreviewTab>('architecture');
  const [selectedPreviewFile, setSelectedPreviewFile] = useState(
    PREVIEW_FILES[2].path
  );

  const connectMutation = useMutation({
    mutationFn: async (rawUrl: string) => {
      const parsed = parseGitHubUrl(rawUrl);
      if (!parsed) {
        throw new Error(
          'Enter a valid GitHub repository URL (e.g. https://github.com/owner/repository).'
        );
      }
      return repositoryService.addRepository({
        name: parsed.name,
        owner: parsed.owner,
        url: parsed.normalizedUrl,
        branch: 'main',
        isPrivate: false,
        sourceType: 'github',
      });
    },
    onSuccess: (repo) => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
      toast.success(`Sample repository "${repo.owner}/${repo.name}" connected.`);
      navigate(getRepositoryRoute(repo.id));
    },
    onError: (err) => {
      const message =
        err instanceof Error ? err.message : 'Unable to connect repository.';
      setUrlError(message);
    },
  });

  const handleConnectSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setUrlError(null);
    const parsed = parseGitHubUrl(githubUrl);
    if (!parsed) {
      setUrlError(
        'Enter a valid GitHub URL such as https://github.com/owner/repo.'
      );
      return;
    }
    connectMutation.mutate(githubUrl);
  };

  const activeFileMeta =
    PREVIEW_FILES.find((f) => f.path === selectedPreviewFile) ?? PREVIEW_FILES[0];

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* 3-Zone Top Bar */}
      <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-8 px-4 sm:px-6">
          <Link
            to={APP_ROUTES.LANDING}
            className="whitespace-nowrap shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md"
          >
            <RepoMindLogo />
          </Link>

          <nav
            aria-label="Primary"
            className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground"
          >
            <a
              href="#features"
              className="hover:text-foreground transition-colors whitespace-nowrap shrink-0"
            >
              Features
            </a>
            <a
              href="#workflow"
              className="hover:text-foreground transition-colors whitespace-nowrap shrink-0"
            >
              How it works
            </a>
            <a
              href="#architecture"
              className="hover:text-foreground transition-colors whitespace-nowrap shrink-0"
            >
              Grounding
            </a>
            <a
              href="#use-cases"
              className="hover:text-foreground transition-colors whitespace-nowrap shrink-0"
            >
              Use cases
            </a>
          </nav>

          <div className="flex items-center gap-2 shrink-0">
            <ThemeToggle />
            <Button asChild size="sm" className="whitespace-nowrap shrink-0">
              <Link
                to={isAuthenticated ? APP_ROUTES.DASHBOARD : APP_ROUTES.LOGIN}
              >
                {isAuthenticated ? 'Open Workspace' : 'Sign In'}
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero Section with Subtle Grid + Radial Glow */}
        <section className="relative overflow-hidden border-b border-border bg-hero-glow">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-grid-pattern opacity-60"
          />
          <PageFadeIn className="relative mx-auto grid max-w-7xl grid-cols-1 items-stretch gap-10 px-4 py-14 sm:px-6 lg:grid-cols-12 lg:py-20">
            <div className="flex flex-col justify-center space-y-6 lg:col-span-6">
              <p className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wide text-primary">
                <Sparkles className="size-3.5" />
                Repository Intelligence Platform · Phase 1 Interactive Preview
              </p>

              <h1
                className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl"
                style={{ textWrap: 'balance' }}
              >
                Understand any codebase. Trace every connection. Explain every flow.
              </h1>

              <p className="max-w-xl text-base leading-relaxed text-muted-foreground">
                RepoMind pairs deterministic structural indexing with grounded code
                explanations. Explore folder trees, inspect multi-view architecture
                graphs, isolate circular imports, and trace execution paths with
                Verified, Inferred, and Unknown evidence markers.
              </p>

              <form onSubmit={handleConnectSubmit} className="space-y-3 pt-1">
                <div className="flex flex-col gap-2.5 sm:flex-row">
                  <div className="flex-1">
                    <label htmlFor="landing-github-url" className="sr-only">
                      GitHub repository URL
                    </label>
                    <Input
                      id="landing-github-url"
                      type="url"
                      value={githubUrl}
                      onChange={(e) => {
                        setGithubUrl(e.target.value);
                        if (urlError) setUrlError(null);
                      }}
                      placeholder="https://github.com/owner/repository"
                      aria-invalid={Boolean(urlError)}
                      className="h-10 bg-background font-mono text-sm"
                    />
                  </div>
                  <Button
                    type="submit"
                    disabled={connectMutation.isPending}
                    className="h-10 px-5 whitespace-nowrap shrink-0"
                  >
                    {connectMutation.isPending
                      ? 'Connecting...'
                      : 'Connect Repository'}
                    <ArrowRight className="ml-1.5 size-4" />
                  </Button>
                </div>

                {urlError && (
                  <p role="alert" className="text-xs text-destructive">
                    {urlError}
                  </p>
                )}

                <div className="flex flex-wrap items-center gap-3 pt-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      navigate(`${APP_ROUTES.REPOSITORIES_ADD}?tab=zip`)
                    }
                    className="whitespace-nowrap shrink-0 bg-background/80"
                  >
                    <Upload className="mr-1.5 size-3.5" />
                    Upload ZIP Archive
                  </Button>
                  <Button
                    asChild
                    variant="ghost"
                    size="sm"
                    className="whitespace-nowrap shrink-0"
                  >
                    <Link to={getRepositoryRoute('repo-cloud-gateway')}>
                      Open Sample Repo
                    </Link>
                  </Button>
                </div>
              </form>
            </div>

            {/* Multi-Pane Interactive Product Preview */}
            <div className="surface-card flex flex-col justify-between rounded-xl border border-border bg-card/95 p-4 sm:p-5 backdrop-blur-xs lg:col-span-6">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground truncate">
                    acme-platform / cloud-gateway
                  </p>
                  <p className="text-xs font-mono text-muted-foreground">
                    branch: main · commit: 9a4f21c · sample workspace
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-1 rounded-lg bg-muted p-1">
                  {(
                    [
                      ['architecture', 'Architecture'],
                      ['trace', 'Trace'],
                      ['dependencies', 'Cycles'],
                      ['explanation', 'AI Cited'],
                    ] as const
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setPreviewTab(key)}
                      className={cn(
                        'rounded-md px-2.5 py-1 text-xs font-medium transition-colors whitespace-nowrap',
                        previewTab === key
                          ? 'bg-card text-foreground shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Split Multi-Pane Preview Body */}
              <div className="my-4 grid flex-1 grid-cols-1 gap-3 sm:grid-cols-12">
                {/* Left Explorer Mini-Pane */}
                <div className="rounded-lg border border-border bg-background/80 p-2.5 sm:col-span-5 flex flex-col justify-between">
                  <div>
                    <p className="px-1.5 pb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Explorer
                    </p>
                    <div className="space-y-1">
                      {PREVIEW_FILES.map((file) => {
                        const active = file.path === selectedPreviewFile;
                        return (
                          <button
                            key={file.path}
                            type="button"
                            onClick={() => setSelectedPreviewFile(file.path)}
                            className={cn(
                              'flex w-full items-center gap-1.5 rounded px-2 py-1.5 text-left font-mono text-[11px] transition-colors',
                              active
                                ? 'bg-accent text-accent-foreground font-medium'
                                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                            )}
                          >
                            <FileCode2 className="size-3.5 text-primary shrink-0" />
                            <span className="truncate">{file.name}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div className="mt-3 rounded border border-border bg-card p-2 text-[11px] text-muted-foreground">
                    <span className="font-mono text-foreground block truncate">
                      {activeFileMeta.path}
                    </span>
                    <span className="mt-0.5 block leading-snug">
                      {activeFileMeta.summary}
                    </span>
                  </div>
                </div>

                {/* Right Intelligence Mini-Pane */}
                <div className="rounded-lg border border-border bg-background/80 p-3.5 sm:col-span-7 flex flex-col justify-between">
                  {previewTab === 'architecture' && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-muted-foreground">
                          Architecture Boundaries
                        </span>
                        <ConfidenceBadge confidence="verified" />
                      </div>
                      <div className="space-y-2">
                        <div className="rounded-md border border-violet-500/40 bg-card p-2.5">
                          <p className="text-[10px] font-semibold uppercase text-violet-600 dark:text-violet-400">
                            API Router
                          </p>
                          <p className="font-mono text-xs font-semibold text-foreground">
                            proxy.router.ts → /v1/:service/*
                          </p>
                        </div>
                        <div className="rounded-md border border-emerald-500/40 bg-card p-2.5">
                          <p className="text-[10px] font-semibold uppercase text-emerald-600 dark:text-emerald-400">
                            Auth Middleware
                          </p>
                          <p className="font-mono text-xs font-semibold text-foreground">
                            auth.middleware.ts → requireAuth()
                          </p>
                        </div>
                        <div className="rounded-md border border-amber-500/40 bg-card p-2.5">
                          <p className="text-[10px] font-semibold uppercase text-amber-600 dark:text-amber-400">
                            Database / Session Store
                          </p>
                          <p className="font-mono text-xs font-semibold text-foreground">
                            session.service.ts → isTokenRevoked()
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {previewTab === 'trace' && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-muted-foreground">
                          POST /api/v1/auth/login
                        </span>
                        <span className="text-[11px] font-mono text-muted-foreground">
                          Sample Trace
                        </span>
                      </div>
                      {[
                        {
                          step: '01',
                          fn: 'Login API → Auth Controller',
                          status: 'verified' as const,
                        },
                        {
                          step: '02',
                          fn: 'Validate Credentials → User Service',
                          status: 'verified' as const,
                        },
                        {
                          step: '03',
                          fn: 'Database Query → Generate JWT',
                          status: 'verified' as const,
                        },
                        {
                          step: '04',
                          fn: 'upstreamHttpForward()',
                          status: 'unresolved' as const,
                        },
                      ].map((item) => (
                        <div
                          key={item.step}
                          className="flex items-center justify-between gap-2 rounded-md border border-border bg-card px-2.5 py-1.5"
                        >
                          <span className="font-mono text-[11px] font-medium text-foreground truncate">
                            {item.step}. {item.fn}
                          </span>
                          <ConfidenceBadge confidence={item.status} />
                        </div>
                      ))}
                    </div>
                  )}

                  {previewTab === 'dependencies' && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-destructive inline-flex items-center gap-1">
                          <AlertTriangle className="size-3.5" />
                          Sample Cycle Flagged
                        </span>
                        <ConfidenceBadge confidence="verified" />
                      </div>
                      <div className="rounded-md border border-red-500/40 bg-red-500/5 p-2.5 font-mono text-[11px] text-foreground">
                        auth.ts → userService.ts → permission.ts → auth.ts
                      </div>
                      <p className="text-xs leading-relaxed text-muted-foreground">
                        Extract <code className="font-mono text-foreground">AuthPolicyContext</code>{' '}
                        into a shared types module to break the circular import.
                      </p>
                    </div>
                  )}

                  {previewTab === 'explanation' && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-muted-foreground">
                          Grounded Citation
                        </span>
                        <ConfidenceBadge confidence="verified" />
                      </div>
                      <p className="text-xs leading-relaxed text-foreground">
                        Authentication executes inside{' '}
                        <code className="font-mono text-primary">requireAuth</code>{' '}
                        at lines 11–41. Revoked JTIs return HTTP 401 before reaching{' '}
                        <code className="font-mono text-primary">tenantRateLimit</code>.
                      </p>
                      <div className="rounded-md border border-border bg-card px-2.5 py-2 font-mono text-[11px] text-muted-foreground">
                        Citation: src/middleware/auth.middleware.ts · L11–L41
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between text-xs text-muted-foreground border-t border-border pt-3">
                <span>Evidence grading: Verified · Inferred · Unknown</span>
                <Link
                  to={getRepositoryRoute('repo-cloud-gateway', 'execution')}
                  className="font-medium text-primary hover:underline whitespace-nowrap"
                >
                  Launch Execution Tracer →
                </Link>
              </div>
            </div>
          </PageFadeIn>
        </section>

        {/* 7 Feature Cards Grid */}
        <section id="features" className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <div className="max-w-2xl space-y-2">
            <h2 className="font-heading text-2xl font-bold tracking-tight sm:text-3xl">
              Seven integrated workspaces for codebase intelligence
            </h2>
            <p className="text-sm text-muted-foreground sm:text-base">
              Every module separates deterministic static facts from AI-assisted
              summaries so engineers always know what is verified in source code.
            </p>
          </div>

          <StaggerGrid className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {FEATURE_CARDS.map((feature, idx) => {
              const Icon = feature.icon;
              return (
                <StaggerItem
                  key={feature.title}
                  className={cn(
                    'surface-card surface-card-interactive rounded-xl border border-border bg-card p-6 space-y-3',
                    idx === 0 && 'lg:col-span-2'
                  )}
                >
                  <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="size-4" />
                  </div>
                  <h3 className="text-base font-semibold text-foreground">
                    {feature.title}
                  </h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {feature.desc}
                  </p>
                </StaggerItem>
              );
            })}
          </StaggerGrid>
        </section>

        {/* Animated Workflow Steps */}
        <section
          id="workflow"
          className="border-y border-border bg-card/40 py-16"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6">
            <div className="max-w-2xl space-y-2">
              <h2 className="font-heading text-2xl font-bold tracking-tight sm:text-3xl">
                How RepoMind processes a repository
              </h2>
              <p className="text-sm text-muted-foreground sm:text-base">
                A deterministic pipeline indexes structure first, then pairs static
                relationships with contextual explanations.
              </p>
            </div>

            <StaggerGrid className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
              {[
                {
                  num: '01. Ingest Source',
                  title: 'Connect GitHub or upload ZIP',
                  body: 'Point to a public or authorized private repository URL, choose a branch, or upload a source archive directly.',
                  icon: GitBranch,
                },
                {
                  num: '02. Static Indexing',
                  title: 'Extract symbols & dependencies',
                  body: 'Map files, functions, classes, import edges, execution traces, and circular dependency cycles deterministically.',
                  icon: Layers,
                },
                {
                  num: '03. Grounded Intelligence',
                  title: 'Explore, trace & document',
                  body: 'Navigate multi-view architecture graphs, step through call sequences, review diffs, and query cited explanations.',
                  icon: MessageSquareCode,
                },
              ].map((step) => {
                const Icon = step.icon;
                return (
                  <StaggerItem
                    key={step.num}
                    className="surface-card surface-card-interactive rounded-xl border border-border bg-card p-6 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-semibold text-primary">
                        {step.num}
                      </span>
                      <Icon className="size-4 text-muted-foreground" />
                    </div>
                    <h3 className="text-base font-semibold text-foreground">
                      {step.title}
                    </h3>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {step.body}
                    </p>
                  </StaggerItem>
                );
              })}
            </StaggerGrid>
          </div>
        </section>

        {/* Grounding Matrix */}
        <section
          id="architecture"
          className="mx-auto max-w-7xl px-4 py-16 sm:px-6"
        >
          <div className="grid grid-cols-1 items-center gap-8 lg:grid-cols-12">
            <div className="space-y-4 lg:col-span-5">
              <h2 className="font-heading text-2xl font-bold tracking-tight sm:text-3xl">
                Designed around verification over guesswork
              </h2>
              <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
                Generic AI chat tools invent call paths when context is missing.
                RepoMind surfaces confidence levels on every edge, trace step, and
                assistant citation so engineers never confuse estimation with static
                proof.
              </p>
              <ul className="space-y-2.5 text-sm text-foreground">
                <li className="flex items-center gap-2.5">
                  <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
                  <span>Verified: directly backed by AST imports or definitions</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <ShieldCheck className="size-4 text-amber-500 shrink-0" />
                  <span>Inferred: estimated from naming, types, or routing patterns</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Network className="size-4 text-muted-foreground shrink-0" />
                  <span>Unknown / Unresolved: explicitly flagged external boundaries</span>
                </li>
              </ul>
              <div className="pt-2">
                <Button asChild variant="outline">
                  <Link to={getRepositoryRoute('repo-cloud-gateway', 'architecture')}>
                    Open Interactive Graph Demo
                  </Link>
                </Button>
              </div>
            </div>

            <div className="surface-card rounded-xl border border-border bg-card p-6 lg:col-span-7 space-y-4">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <span className="text-sm font-semibold">
                  Sample Dependency & Boundary Matrix
                </span>
                <span className="text-xs font-mono text-muted-foreground">
                  acme-platform/cloud-gateway
                </span>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-border bg-background p-3.5 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">
                      Ingress → Router
                    </span>
                    <ConfidenceBadge confidence="verified" />
                  </div>
                  <p className="font-mono text-xs text-foreground">
                    src/server.ts → src/routes/proxy.router.ts
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-background p-3.5 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">
                      Router → Middleware
                    </span>
                    <ConfidenceBadge confidence="verified" />
                  </div>
                  <p className="font-mono text-xs text-foreground">
                    proxy.router.ts → auth.middleware.ts
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-background p-3.5 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">
                      Cycle Flagged
                    </span>
                    <ConfidenceBadge confidence="verified" />
                  </div>
                  <p className="font-mono text-xs text-destructive">
                    auth.ts → userService.ts → permission.ts
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-background p-3.5 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">
                      Downstream Target
                    </span>
                    <ConfidenceBadge confidence="unresolved" />
                  </div>
                  <p className="font-mono text-xs text-foreground">
                    billing-service.internal:4100
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Use Cases + Final CTA */}
        <section
          id="use-cases"
          className="border-t border-border bg-card/40 py-16"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 space-y-14">
            <div>
              <div className="max-w-2xl space-y-2">
                <h2 className="font-heading text-2xl font-bold tracking-tight sm:text-3xl">
                  Practical developer use cases
                </h2>
                <p className="text-sm text-muted-foreground sm:text-base">
                  Built for individual engineers and platform teams working across
                  unfamiliar or fast-moving repositories.
                </p>
              </div>

              <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  {
                    title: 'Engineer Onboarding',
                    desc: 'Map entry points, data models, and core request flows without interrupting senior maintainers.',
                  },
                  {
                    title: 'Refactoring Safety',
                    desc: 'Spot circular imports and tightly coupled modules before extracting services or splitting packages.',
                  },
                  {
                    title: 'Change Impact Reviews',
                    desc: 'Track commit-by-commit file modifications and keep architectural specs synchronized with source.',
                  },
                  {
                    title: 'Technical Documentation',
                    desc: 'Maintain living README, API, module, and onboarding specs with Markdown and Mermaid diagrams.',
                  },
                ].map((item) => (
                  <div
                    key={item.title}
                    className="surface-card rounded-xl border border-border bg-card p-5 space-y-2"
                  >
                    <h3 className="text-sm font-semibold text-foreground">
                      {item.title}
                    </h3>
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      {item.desc}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Final CTA Banner */}
            <div className="surface-card rounded-2xl border border-border bg-card bg-hero-glow p-8 sm:p-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-2xl space-y-2">
                <h2 className="font-heading text-2xl font-bold tracking-tight text-foreground">
                  Explore the interactive workspace right now
                </h2>
                <p className="text-sm text-muted-foreground">
                  Inspect pre-indexed sample repositories across Code Explorer,
                  Architecture Graph, Execution Flow Tracing, and Dependency
                  Analysis.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3 shrink-0">
                <Button asChild size="lg">
                  <Link to={APP_ROUTES.DASHBOARD}>
                    Open Workspace Dashboard
                    <ArrowRight className="ml-1.5 size-4" />
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg">
                  <Link to={APP_ROUTES.REPOSITORIES_ADD}>
                    Connect Repository
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Clean Footer */}
      <footer className="border-t border-border bg-background">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-4 px-4 py-8 text-xs text-muted-foreground sm:flex-row sm:items-center sm:px-6">
          <div className="flex items-center gap-3">
            <RepoMindLogo />
            <span>·</span>
            <span>Understand any codebase. Trace every connection. Explain every flow.</span>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <Link to={APP_ROUTES.DASHBOARD} className="hover:text-foreground">
              Dashboard
            </Link>
            <Link to={APP_ROUTES.REPOSITORIES} className="hover:text-foreground">
              Repositories
            </Link>
            <Link to={APP_ROUTES.LOGIN} className="hover:text-foreground">
              Sign In
            </Link>
            <Link to={APP_ROUTES.REGISTER} className="hover:text-foreground">
              Sign Up
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
