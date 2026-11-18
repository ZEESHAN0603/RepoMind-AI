import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  ArrowRight,
  Cpu,
  FileCode2,
  FolderGit2,
  FolderTree,
  Languages,
  Network,
  Plus,
  Share2,
  Sparkles,
} from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ErrorState } from '@/components/common/ErrorState';
import {
  AnimatedCounter,
  PageFadeIn,
} from '@/components/common/MotionPrimitives';
import { SampleDataBanner } from '@/components/common/SampleDataBanner';
import { StatusText } from '@/components/common/StatusText';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { APP_ROUTES, getRepositoryRoute } from '@/constants/routes';
import { cn } from '@/lib/utils';
import { repositoryService } from '@/services';
import { useSettingsStore } from '@/stores/settings.store';
import { formatRelativeTime, parseGitHubUrl } from '@/utils/formatters';

export function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const settings = useSettingsStore((state) => state.settings);

  const [quickUrl, setQuickUrl] = useState('');
  const [quickError, setQuickError] = useState<string | null>(null);
  const [hoveredLang, setHoveredLang] = useState<{
    language: string;
    fileCount: number;
    percentage: number;
    color: string;
  } | null>(null);

  const summaryQuery = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: () => repositoryService.getDashboardSummary(),
  });

  const reposQuery = useQuery({
    queryKey: ['repositories'],
    queryFn: () => repositoryService.getRepositories(),
  });

  const quickConnectMutation = useMutation({
    mutationFn: async (url: string) => {
      const parsed = parseGitHubUrl(url);
      if (!parsed) {
        throw new Error('Enter a valid GitHub URL (https://github.com/owner/repo).');
      }
      return repositoryService.addRepository({
        name: parsed.name,
        owner: parsed.owner,
        url: parsed.normalizedUrl,
        branch: settings.preferences.defaultBranch,
        isPrivate: false,
        sourceType: 'github',
      });
    },
    onSuccess: (repo) => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      setQuickUrl('');
      toast.success(`Added sample repository "${repo.owner}/${repo.name}".`);
      navigate(getRepositoryRoute(repo.id));
    },
    onError: (err) => {
      setQuickError(err instanceof Error ? err.message : 'Unable to connect.');
    },
  });

  const handleQuickConnect = (e: React.FormEvent) => {
    e.preventDefault();
    setQuickError(null);
    if (!parseGitHubUrl(quickUrl)) {
      setQuickError('Enter a valid GitHub URL such as https://github.com/vercel/next.js');
      return;
    }
    quickConnectMutation.mutate(quickUrl);
  };

  if (summaryQuery.isError || reposQuery.isError) {
    return (
      <ErrorState
        message="Could not load workspace dashboard summary."
        onRetry={() => {
          summaryQuery.refetch();
          reposQuery.refetch();
        }}
      />
    );
  }

  const isLoading = summaryQuery.isLoading || reposQuery.isLoading;
  const summary = summaryQuery.data;
  const repositories = (reposQuery.data ?? []).filter((r) => !r.isArchived);
  const featuredRepoId = repositories[0]?.id ?? 'repo-cloud-gateway';

  return (
    <PageFadeIn className="space-y-6">
      {/* Header + Quick Actions */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">
            Workspace Dashboard
          </h1>
          <p className="text-sm text-muted-foreground">
            Overview of indexed repositories, language distribution, and provider status.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild variant="outline" size="sm" className="whitespace-nowrap">
            <Link to={getRepositoryRoute(featuredRepoId, 'execution')}>
              <Activity className="mr-1.5 size-3.5 text-primary" />
              Execution Tracer
            </Link>
          </Button>
          <Button asChild variant="outline" size="sm" className="whitespace-nowrap">
            <Link to={getRepositoryRoute(featuredRepoId, 'dependencies')}>
              <Share2 className="mr-1.5 size-3.5 text-primary" />
              Dependencies
            </Link>
          </Button>
          <Button asChild size="sm" className="w-fit whitespace-nowrap shrink-0">
            <Link to={APP_ROUTES.REPOSITORIES_ADD}>
              <Plus className="mr-1.5 size-4" />
              Add Repository
            </Link>
          </Button>
        </div>
      </div>

      <SampleDataBanner />

      {/* Animated KPI Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, idx) => (
            <Card key={idx}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-28" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))
        ) : (
          <>
            <Card className="surface-card-interactive">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-medium text-muted-foreground">
                  Total Repositories
                </CardTitle>
                <FolderGit2 className="size-4 text-primary" />
              </CardHeader>
              <CardContent>
                <div className="font-mono text-2xl font-bold tabular-nums">
                  <AnimatedCounter value={summary?.totalRepositories ?? 0} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Active in sample workspace
                </p>
              </CardContent>
            </Card>

            <Card className="surface-card-interactive">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-medium text-muted-foreground">
                  Successfully Analyzed
                </CardTitle>
                <Sparkles className="size-4 text-emerald-500" />
              </CardHeader>
              <CardContent>
                <div className="font-mono text-2xl font-bold tabular-nums">
                  <AnimatedCounter value={summary?.analyzedRepositories ?? 0} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Ready for exploration & tracing
                </p>
              </CardContent>
            </Card>

            <Card className="surface-card-interactive">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-medium text-muted-foreground">
                  Total Source Files
                </CardTitle>
                <FileCode2 className="size-4 text-sky-500" />
              </CardHeader>
              <CardContent>
                <div className="font-mono text-2xl font-bold tabular-nums">
                  <AnimatedCounter value={summary?.totalSourceFiles ?? 0} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Across all active repositories
                </p>
              </CardContent>
            </Card>

            <Card className="surface-card-interactive">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-medium text-muted-foreground">
                  Detected Languages
                </CardTitle>
                <Languages className="size-4 text-amber-500" />
              </CardHeader>
              <CardContent>
                <div className="font-mono text-2xl font-bold tabular-nums">
                  <AnimatedCounter value={summary?.detectedLanguagesCount ?? 0} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Primary & secondary dialects
                </p>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Interactive Language Chart & Recent Repos */}
        <div className="space-y-6 lg:col-span-8">
          <Card>
            <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle className="text-base">Language Distribution</CardTitle>
                <CardDescription>
                  Hover or select any segment to inspect indexed file counts
                </CardDescription>
              </div>
              {hoveredLang && (
                <div className="inline-flex items-center gap-2 rounded-md border border-border bg-muted/50 px-2.5 py-1 text-xs">
                  <span
                    className="size-2.5 rounded-xs shrink-0"
                    style={{ backgroundColor: hoveredLang.color }}
                  />
                  <span className="font-semibold text-foreground">
                    {hoveredLang.language}
                  </span>
                  <span className="font-mono text-muted-foreground tabular-nums">
                    {hoveredLang.fileCount} files ({hoveredLang.percentage}%)
                  </span>
                </div>
              )}
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
              ) : (
                <div className="space-y-4">
                  <div
                    className="flex h-3.5 w-full overflow-hidden rounded-full bg-muted"
                    onMouseLeave={() => setHoveredLang(null)}
                  >
                    {summary?.languageDistribution.map((item) => {
                      const isActive = hoveredLang?.language === item.language;
                      return (
                        <button
                          key={item.language}
                          type="button"
                          onMouseEnter={() => setHoveredLang(item)}
                          onFocus={() => setHoveredLang(item)}
                          aria-label={`${item.language}: ${item.fileCount} files (${item.percentage}%)`}
                          style={{
                            width: `${item.percentage}%`,
                            backgroundColor: item.color,
                          }}
                          className={cn(
                            'h-full transition-opacity focus:outline-none',
                            hoveredLang && !isActive ? 'opacity-45' : 'opacity-100'
                          )}
                        />
                      );
                    })}
                  </div>

                  <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                    {summary?.languageDistribution.map((item) => {
                      const isActive = hoveredLang?.language === item.language;
                      return (
                        <button
                          key={item.language}
                          type="button"
                          onMouseEnter={() => setHoveredLang(item)}
                          onMouseLeave={() => setHoveredLang(null)}
                          onFocus={() => setHoveredLang(item)}
                          className={cn(
                            'flex items-center justify-between rounded-md border px-3 py-2 text-xs text-left transition-colors',
                            isActive
                              ? 'border-primary/50 bg-accent/40'
                              : 'border-border hover:bg-muted/40'
                          )}
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className="size-2.5 rounded-xs shrink-0"
                              style={{ backgroundColor: item.color }}
                            />
                            <span className="font-medium text-foreground">
                              {item.language}
                            </span>
                          </div>
                          <span className="font-mono text-muted-foreground tabular-nums">
                            {item.fileCount} files · {item.percentage}%
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <div>
                <CardTitle className="text-base">Recent Repositories</CardTitle>
                <CardDescription>
                  Jump straight into any repository overview, explorer, or graph
                </CardDescription>
              </div>
              <Button asChild variant="ghost" size="sm">
                <Link to={APP_ROUTES.REPOSITORIES}>
                  View all
                  <ArrowRight className="ml-1 size-3.5" />
                </Link>
              </Button>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-border">
                {isLoading ? (
                  <div className="p-6 space-y-3">
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                  </div>
                ) : (
                  repositories.slice(0, 4).map((repo) => (
                    <div
                      key={repo.id}
                      className="flex flex-col gap-3 px-6 py-3.5 sm:flex-row sm:items-center sm:justify-between hover:bg-muted/40 transition-colors"
                    >
                      <div className="min-w-0 space-y-0.5">
                        <Link
                          to={getRepositoryRoute(repo.id)}
                          className="font-medium text-sm text-foreground hover:text-primary transition-colors truncate block"
                        >
                          {repo.owner}/{repo.name}
                        </Link>
                        <p className="text-xs text-muted-foreground">
                          {repo.language} · {repo.fileCount} files · Branch{' '}
                          <span className="font-mono">{repo.branch}</span> ·{' '}
                          <span className="font-mono">{repo.commitSha}</span>
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                        <StatusText status={repo.status} />
                        <Button asChild variant="ghost" size="xs" title="Code Explorer">
                          <Link to={getRepositoryRoute(repo.id, 'explorer')}>
                            <FolderTree className="size-3.5" />
                          </Link>
                        </Button>
                        <Button asChild variant="ghost" size="xs" title="Architecture Graph">
                          <Link to={getRepositoryRoute(repo.id, 'architecture')}>
                            <Network className="size-3.5" />
                          </Link>
                        </Button>
                        <Button asChild variant="outline" size="xs">
                          <Link to={getRepositoryRoute(repo.id)}>Open</Link>
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Quick Connect, AI Provider Status, Activity Timeline */}
        <div className="space-y-6 lg:col-span-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Quick Connect Repository</CardTitle>
              <CardDescription>
                Simulate connecting a public GitHub URL
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleQuickConnect} className="space-y-3">
                <Input
                  type="url"
                  value={quickUrl}
                  onChange={(e) => {
                    setQuickUrl(e.target.value);
                    if (quickError) setQuickError(null);
                  }}
                  placeholder="https://github.com/owner/repo"
                  className="font-mono text-xs"
                />
                {quickError && (
                  <p role="alert" className="text-xs text-destructive">
                    {quickError}
                  </p>
                )}
                <Button
                  type="submit"
                  size="sm"
                  className="w-full"
                  disabled={quickConnectMutation.isPending}
                >
                  {quickConnectMutation.isPending
                    ? 'Connecting...'
                    : 'Connect & Analyze'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-base">AI Provider Status</CardTitle>
                <CardDescription>Configured inference architecture</CardDescription>
              </div>
              <Cpu className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                <div>
                  <p className="font-medium text-foreground">
                    Primary: {settings.providers.primaryProvider.toUpperCase()}
                  </p>
                  <p className="font-mono text-muted-foreground">
                    {settings.models.generationModel}
                  </p>
                </div>
                <span className={`font-medium ${settings.providers.ollamaStatus === 'connected' ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
                  {settings.providers.ollamaStatus === 'connected' ? 'Ready' : 'Offline'}
                </span>
              </div>

              <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                <div>
                  <p className="font-medium text-foreground">
                    Fallback:{' '}
                    {settings.providers.fallbackProvider === 'none'
                      ? 'Disabled'
                      : settings.providers.fallbackProvider.toUpperCase()}
                  </p>
                  <p className="font-mono text-muted-foreground">
                    {settings.models.embeddingModel}
                  </p>
                </div>
                <span className="text-muted-foreground">Standby</span>
              </div>

              <Button asChild variant="outline" size="sm" className="w-full">
                <Link to={APP_ROUTES.SETTINGS}>Configure Providers</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Activity Timeline</CardTitle>
              <CardDescription>Recent workspace indexing events</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : (
                <div className="relative space-y-4 pl-4 before:absolute before:left-[5px] before:top-1.5 before:bottom-1.5 before:w-px before:bg-border">
                  {summary?.recentActivities.map((act) => (
                    <div key={act.id} className="relative space-y-1">
                      <span
                        className={cn(
                          'absolute -left-4 top-1.5 size-2.5 rounded-full border-2 border-card',
                          act.status === 'completed'
                            ? 'bg-emerald-500'
                            : act.status === 'failed'
                              ? 'bg-destructive'
                              : 'bg-primary'
                        )}
                      />
                      <div className="flex items-center justify-between gap-2">
                        <Link
                          to={getRepositoryRoute(act.repositoryId)}
                          className="text-xs font-medium text-foreground hover:text-primary truncate"
                        >
                          {act.repositoryName}
                        </Link>
                        <span className="text-[11px] text-muted-foreground tabular-nums shrink-0">
                          {formatRelativeTime(act.timestamp)}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">{act.action}</p>
                      <StatusText status={act.status} />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </PageFadeIn>
  );
}
