import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronRight,
  Code2,
  Cpu,
  FileCode2,
  FileDiff,
  FileMinus,
  FilePlus,
  GitCommit,
  Layers,
  Loader2,
  Network,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useParams } from 'react-router-dom';
import remarkGfm from 'remark-gfm';
import { toast } from 'sonner';
import { ErrorState } from '@/components/common/ErrorState';
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
import { cn } from '@/lib/utils';
import { updatesService } from '@/services';
import type { FileCategoryType, FileChangeType, ImpactLevelType } from '@/types';
import { formatRelativeTime } from '@/utils/formatters';

const CHANGE_BADGE: Record<
  FileChangeType,
  { label: string; classes: string; icon: typeof FilePlus }
> = {
  added: {
    label: 'Added',
    classes: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/25',
    icon: FilePlus,
  },
  modified: {
    label: 'Modified',
    classes: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/25',
    icon: FileDiff,
  },
  deleted: {
    label: 'Deleted',
    classes: 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/25',
    icon: FileMinus,
  },
  renamed: {
    label: 'Renamed',
    classes: 'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/25',
    icon: FileCode2,
  },
};

const IMPACT_LEVEL_BADGE: Record<
  ImpactLevelType,
  { label: string; classes: string }
> = {
  directly_changed: {
    label: 'Directly Changed',
    classes: 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/25',
  },
  directly_affected: {
    label: 'Directly Affected',
    classes: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/25',
  },
  indirectly_affected: {
    label: 'Transitive Dependent',
    classes: 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/25',
  },
  potentially_affected: {
    label: 'Potentially Affected',
    classes: 'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/25',
  },
  unknown: {
    label: 'Unknown Impact',
    classes: 'bg-muted text-muted-foreground border-border',
  },
};

type ActiveTab = 'files' | 'symbols' | 'impact' | 'ai_summary';

export function UpdatesPage() {
  const { id = 'repo-cloud-gateway' } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [selectedCommitSha, setSelectedCommitSha] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('files');
  const [fileSearch, setFileSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [expandedDiffs, setExpandedDiffs] = useState<Record<string, boolean>>({});

  const updatesQuery = useQuery({
    queryKey: ['repository-updates', id],
    queryFn: () => updatesService.getRepositoryUpdates(id),
  });

  const analyzeMutation = useMutation({
    mutationFn: () => updatesService.triggerIncrementalReindex(id),
    onSuccess: (updated) => {
      queryClient.setQueryData(['repository-updates', id], updated);
      toast.success('Repository update analysis completed successfully.');
    },
    onError: () => {
      toast.error('Repository update analysis failed.');
    },
  });

  const data = updatesQuery.data;
  const activeCommit = useMemo(() => {
    if (!data?.commits.length) return null;
    return data.commits.find((c) => c.sha === selectedCommitSha) ?? data.commits[0];
  }, [data, selectedCommitSha]);

  const activeRunDetail = data?.activeRunDetail;

  // Filtered files
  const filteredFiles = useMemo(() => {
    const files = activeRunDetail?.fileChanges ?? activeCommit?.changedFiles ?? [];
    return files.filter((f) => {
      const matchesSearch = f.path.toLowerCase().includes(fileSearch.toLowerCase());
      const matchesCategory =
        categoryFilter === 'all' || (f.fileCategory && f.fileCategory === categoryFilter);
      return matchesSearch && matchesCategory;
    });
  }, [activeRunDetail, activeCommit, fileSearch, categoryFilter]);

  const toggleDiff = (path: string) => {
    setExpandedDiffs((prev) => ({ ...prev, [path]: !prev[path] }));
  };

  if (updatesQuery.isError) {
    return (
      <ErrorState
        message="Unable to load repository updates intelligence."
        onRetry={() => updatesQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">
            Repository Update Intelligence
          </h1>
          <p className="text-sm text-muted-foreground">
            Track code changes, AST symbol mutations, blast-radius ripples, and AI explanations.
          </p>
        </div>

        <Button
          type="button"
          size="sm"
          onClick={() => analyzeMutation.mutate()}
          disabled={analyzeMutation.isPending || updatesQuery.isLoading}
          className="w-fit whitespace-nowrap shrink-0"
        >
          {analyzeMutation.isPending ? (
            <>
              <Loader2 className="mr-1.5 size-4 animate-spin" />
              Analyzing Updates...
            </>
          ) : (
            <>
              <RefreshCw className="mr-1.5 size-4" />
              Run Update Analysis
            </>
          )}
        </Button>
      </div>

      {/* Sync Status Cards */}
      {updatesQuery.isLoading || !data ? (
        <Skeleton className="h-24 w-full" />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-1.5">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                Currently Analyzed State
              </CardTitle>
            </CardHeader>
            <CardContent className="flex items-center gap-2 font-mono text-lg font-bold">
              <GitCommit className="size-4 text-muted-foreground" />
              {data.currentAnalyzedSha}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-1.5">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                Latest Remote Reference
              </CardTitle>
            </CardHeader>
            <CardContent className="flex items-center gap-2 font-mono text-lg font-bold">
              <GitCommit className="size-4 text-primary" />
              {data.latestRemoteSha}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-1.5">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                Synchronization
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.hasPendingUpdates ? (
                <span className="text-sm font-semibold text-amber-600 dark:text-amber-400">
                  Update Available · Analysis Ready
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="size-4" />
                  Synchronized
                </span>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-1.5">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                Blast Radius Impact
              </CardTitle>
            </CardHeader>
            <CardContent className="flex items-center gap-2 text-lg font-bold font-mono">
              <ShieldAlert className="size-4 text-amber-500" />
              {activeRunDetail
                ? activeRunDetail.impactMetrics.directlyAffected +
                  activeRunDetail.impactMetrics.indirectlyAffected
                : 0}{' '}
              <span className="text-xs font-normal text-muted-foreground">dependents</span>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Layout */}
      {!updatesQuery.isLoading && data && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Left Column: Timeline */}
          <div className="space-y-3 lg:col-span-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-foreground">Update Timeline</h2>
              <span className="text-xs text-muted-foreground">{data.commits.length} runs</span>
            </div>

            <div className="space-y-2">
              {data.commits.map((commit) => {
                const isSelected = activeCommit?.sha === commit.sha;
                return (
                  <button
                    key={commit.sha}
                    type="button"
                    onClick={() => setSelectedCommitSha(commit.sha)}
                    className={cn(
                      'w-full rounded-xl border p-3.5 text-left transition-colors space-y-1.5',
                      isSelected
                        ? 'border-primary bg-accent/40 shadow-sm'
                        : 'border-border bg-card hover:bg-muted/40'
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-bold text-primary">
                        {commit.shortSha}
                      </span>
                      <StatusText status={commit.analysisStatus} />
                    </div>
                    <p className="text-xs font-medium text-foreground line-clamp-2">
                      {commit.message}
                    </p>
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                      <span>{commit.author}</span>
                      <span>{formatRelativeTime(commit.timestamp)}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Column: Multi-tab Explorer */}
          <div className="lg:col-span-8 space-y-4">
            {activeCommit && (
              <Card>
                <CardHeader className="border-b border-border pb-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <CardTitle className="text-base flex items-center gap-2">
                        <span>Commit {activeCommit.shortSha} Analysis</span>
                        <span className="font-mono text-xs font-normal text-muted-foreground">
                          ({activeCommit.sha.slice(0, 12)})
                        </span>
                      </CardTitle>
                      <CardDescription className="mt-0.5">
                        {activeCommit.message}
                      </CardDescription>
                    </div>
                    <StatusText status={activeCommit.analysisStatus} />
                  </div>

                  {/* Tabs */}
                  <div className="flex items-center gap-2 pt-3 border-t border-border/50 mt-3 overflow-x-auto">
                    <button
                      type="button"
                      onClick={() => setActiveTab('files')}
                      className={cn(
                        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                        activeTab === 'files'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted/50 text-muted-foreground hover:bg-muted'
                      )}
                    >
                      <FileDiff className="size-3.5" />
                      Changed Files ({filteredFiles.length})
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveTab('symbols')}
                      className={cn(
                        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                        activeTab === 'symbols'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted/50 text-muted-foreground hover:bg-muted'
                      )}
                    >
                      <Code2 className="size-3.5" />
                      Changed Symbols ({activeRunDetail?.symbolChanges.length ?? 0})
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveTab('impact')}
                      className={cn(
                        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                        activeTab === 'impact'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted/50 text-muted-foreground hover:bg-muted'
                      )}
                    >
                      <Network className="size-3.5" />
                      Blast Radius ({activeRunDetail?.impactRecords.length ?? 0})
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveTab('ai_summary')}
                      className={cn(
                        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                        activeTab === 'ai_summary'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted/50 text-muted-foreground hover:bg-muted'
                      )}
                    >
                      <Sparkles className="size-3.5" />
                      AI Summary & Risks
                    </button>
                  </div>
                </CardHeader>

                <CardContent className="p-4">
                  {/* TAB 1: Changed Files */}
                  {activeTab === 'files' && (
                    <div className="space-y-3">
                      <div className="flex flex-col sm:flex-row gap-2 sm:items-center justify-between">
                        <div className="relative flex-1 max-w-sm">
                          <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                          <Input
                            placeholder="Search changed files..."
                            value={fileSearch}
                            onChange={(e) => setFileSearch(e.target.value)}
                            className="pl-8 h-8 text-xs"
                          />
                        </div>

                        <div className="flex items-center gap-1 overflow-x-auto text-[11px]">
                          {['all', 'source', 'config', 'manifest', 'documentation'].map((cat) => (
                            <button
                              key={cat}
                              type="button"
                              onClick={() => setCategoryFilter(cat)}
                              className={cn(
                                'px-2 py-1 rounded border capitalize transition-colors',
                                categoryFilter === cat
                                  ? 'bg-secondary text-secondary-foreground font-semibold border-secondary'
                                  : 'text-muted-foreground border-transparent hover:bg-muted'
                              )}
                            >
                              {cat}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="divide-y divide-border border rounded-xl overflow-hidden">
                        {filteredFiles.length === 0 ? (
                          <div className="p-6 text-center text-xs text-muted-foreground">
                            No changed files match your filter.
                          </div>
                        ) : (
                          filteredFiles.map((file) => {
                            const badge = CHANGE_BADGE[file.changeType] ?? CHANGE_BADGE.modified;
                            const Icon = badge.icon;
                            const isExpanded = !!expandedDiffs[file.path];

                            return (
                              <div key={file.path} className="p-3 space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                  <div className="flex items-center gap-2 min-w-0">
                                    <span
                                      className={cn(
                                        'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium shrink-0',
                                        badge.classes
                                      )}
                                    >
                                      <Icon className="size-3" />
                                      {badge.label}
                                    </span>
                                    <span className="font-mono text-xs font-semibold truncate">
                                      {file.path}
                                    </span>
                                  </div>

                                  <div className="flex items-center gap-3 shrink-0 font-mono text-xs">
                                    <span className="text-emerald-600 dark:text-emerald-400">
                                      +{file.additions}
                                    </span>
                                    <span className="text-destructive">-{file.deletions}</span>
                                    {file.diffPatch && (
                                      <Button
                                        variant="ghost"
                                        size="xs"
                                        onClick={() => toggleDiff(file.path)}
                                        className="h-6 px-1.5 text-[10px]"
                                      >
                                        {isExpanded ? 'Hide Diff' : 'View Diff'}
                                      </Button>
                                    )}
                                  </div>
                                </div>

                                <p className="text-xs text-muted-foreground">{file.summary}</p>

                                {isExpanded && file.diffPatch && (
                                  <pre className="p-3 bg-muted/60 rounded-lg font-mono text-[11px] overflow-x-auto leading-relaxed border border-border/60">
                                    {file.diffPatch}
                                  </pre>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  )}

                  {/* TAB 2: Changed Symbols */}
                  {activeTab === 'symbols' && (
                    <div className="space-y-3">
                      {!activeRunDetail?.symbolChanges.length ? (
                        <div className="p-8 text-center text-xs text-muted-foreground">
                          No symbol changes (functions, classes, endpoints) were extracted for this update run.
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {activeRunDetail.symbolChanges.map((sym) => (
                            <div
                              key={sym.id}
                              className="p-3 border rounded-xl bg-card/60 space-y-1.5"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                  <span className="font-mono text-xs font-bold text-foreground">
                                    {sym.symbolName}
                                  </span>
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                                    {sym.symbolType}
                                  </span>
                                  {sym.scope && (
                                    <span className="text-[10px] text-muted-foreground">
                                      in scope {sym.scope}
                                    </span>
                                  )}
                                </div>
                                <span
                                  className={cn(
                                    'text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border',
                                    sym.changeType === 'added'
                                      ? 'text-emerald-600 border-emerald-500/20 bg-emerald-500/10'
                                      : sym.changeType === 'deleted'
                                      ? 'text-red-600 border-red-500/20 bg-red-500/10'
                                      : 'text-amber-600 border-amber-500/20 bg-amber-500/10'
                                  )}
                                >
                                  {sym.changeType}
                                </span>
                              </div>

                              {sym.newSignature && (
                                <div className="font-mono text-[11px] bg-muted/50 p-2 rounded border border-border/40">
                                  {sym.oldSignature && sym.changeType === 'modified' && (
                                    <div className="text-muted-foreground line-through opacity-70">
                                      {sym.oldSignature}
                                    </div>
                                  )}
                                  <div className="text-foreground">{sym.newSignature}</div>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 3: Blast Radius Impact */}
                  {activeTab === 'impact' && (
                    <div className="space-y-4">
                      {/* Metrics Summary */}
                      {activeRunDetail && (
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                          <div className="p-3 border rounded-xl bg-card">
                            <span className="text-[11px] text-muted-foreground">Directly Changed</span>
                            <div className="text-lg font-bold font-mono">
                              {activeRunDetail.impactMetrics.directlyChanged}
                            </div>
                          </div>
                          <div className="p-3 border rounded-xl bg-card">
                            <span className="text-[11px] text-muted-foreground">Direct Callers/Deps</span>
                            <div className="text-lg font-bold font-mono text-amber-600 dark:text-amber-400">
                              {activeRunDetail.impactMetrics.directlyAffected}
                            </div>
                          </div>
                          <div className="p-3 border rounded-xl bg-card">
                            <span className="text-[11px] text-muted-foreground">Transitive Chain</span>
                            <div className="text-lg font-bold font-mono text-blue-600 dark:text-blue-400">
                              {activeRunDetail.impactMetrics.indirectlyAffected}
                            </div>
                          </div>
                          <div className="p-3 border rounded-xl bg-card">
                            <span className="text-[11px] text-muted-foreground">Potential Impacts</span>
                            <div className="text-lg font-bold font-mono text-purple-600 dark:text-purple-400">
                              {activeRunDetail.impactMetrics.potentiallyAffected}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* List */}
                      <div className="space-y-2">
                        {!activeRunDetail?.impactRecords.length ? (
                          <div className="p-8 text-center text-xs text-muted-foreground">
                            No downstream impact records identified for this update run.
                          </div>
                        ) : (
                          activeRunDetail.impactRecords.map((rec) => {
                            const badge =
                              IMPACT_LEVEL_BADGE[rec.impactLevel] ?? IMPACT_LEVEL_BADGE.unknown;
                            return (
                              <div
                                key={rec.id}
                                className="p-3 border rounded-xl bg-card/60 flex items-center justify-between gap-3 text-xs"
                              >
                                <div className="space-y-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className="font-mono font-bold text-foreground truncate">
                                      {rec.affectedIdentifier}
                                    </span>
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                                      {rec.affectedType}
                                    </span>
                                  </div>
                                  <p className="text-[11px] text-muted-foreground">
                                    {rec.evidenceReason}
                                  </p>
                                </div>

                                <span
                                  className={cn(
                                    'inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-medium shrink-0',
                                    badge.classes
                                  )}
                                >
                                  {badge.label}
                                </span>
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  )}

                  {/* TAB 4: AI Summary & Risks */}
                  {activeTab === 'ai_summary' && (
                    <div className="space-y-4">
                      {activeRunDetail?.aiSummaryMarkdown ? (
                        <div className="prose prose-sm dark:prose-invert max-w-none p-4 rounded-xl border bg-muted/20">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {activeRunDetail.aiSummaryMarkdown}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <div className="p-8 text-center space-y-3">
                          <Bot className="size-8 mx-auto text-muted-foreground opacity-60" />
                          <p className="text-xs text-muted-foreground">
                            No AI summary generated for this run yet.
                          </p>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => analyzeMutation.mutate()}
                            disabled={analyzeMutation.isPending}
                          >
                            <Sparkles className="size-3.5 mr-1.5" />
                            Generate Grounded Explanation
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
