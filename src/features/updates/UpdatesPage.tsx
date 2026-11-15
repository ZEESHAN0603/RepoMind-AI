import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  FileDiff,
  FileMinus,
  FilePlus,
  GitCommit,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ErrorState } from '@/components/common/ErrorState';
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
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { updatesService } from '@/services';
import type { FileChangeType } from '@/types';
import { formatRelativeTime } from '@/utils/formatters';

const REINDEX_STEPS = [
  'Comparing commit tree diff',
  'Re-parsing modified files',
  'Updating dependency & symbol index',
  'Refreshing sample documentation references',
];

const CHANGE_BADGE: Record<
  FileChangeType,
  { label: string; classes: string; icon: typeof FilePlus }
> = {
  added: {
    label: 'Added',
    classes:
      'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/25',
    icon: FilePlus,
  },
  modified: {
    label: 'Modified',
    classes:
      'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/25',
    icon: FileDiff,
  },
  deleted: {
    label: 'Deleted',
    classes:
      'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/25',
    icon: FileMinus,
  },
};

export function UpdatesPage() {
  const { id = 'repo-cloud-gateway' } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [selectedCommitSha, setSelectedCommitSha] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [reindexStep, setReindexStep] = useState(-1);

  const updatesQuery = useQuery({
    queryKey: ['repository-updates', id],
    queryFn: () => updatesService.getRepositoryUpdates(id),
  });

  const reindexMutation = useMutation({
    mutationFn: () => updatesService.triggerIncrementalReindex(id),
    onSuccess: (updated) => {
      queryClient.setQueryData(['repository-updates', id], updated);
      setReindexing(false);
      setReindexStep(-1);
      toast.success('Simulated incremental re-indexing complete.');
    },
    onError: () => {
      setReindexing(false);
      setReindexStep(-1);
      toast.error('Simulated re-indexing failed.');
    },
  });

  const handleRunReindex = async () => {
    setReindexing(true);
    for (let i = 0; i < REINDEX_STEPS.length; i++) {
      setReindexStep(i);
      await new Promise((resolve) => setTimeout(resolve, 350));
    }
    reindexMutation.mutate();
  };

  if (updatesQuery.isError) {
    return (
      <ErrorState
        message="Unable to load repository commit updates."
        onRetry={() => updatesQuery.refetch()}
      />
    );
  }

  const data = updatesQuery.data;
  const activeCommit =
    data?.commits.find((c) => c.sha === selectedCommitSha) ??
    data?.commits[0] ??
    null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">
            Repository Updates
          </h1>
          <p className="text-sm text-muted-foreground">
            Compare indexed commit snapshots and simulate incremental re-indexing.
          </p>
        </div>

        <Button
          type="button"
          size="sm"
          onClick={handleRunReindex}
          disabled={reindexing || updatesQuery.isLoading}
          className="w-fit whitespace-nowrap shrink-0"
        >
          {reindexing ? (
            <>
              <Loader2 className="mr-1.5 size-4 animate-spin" />
              Re-indexing...
            </>
          ) : (
            <>
              <RefreshCw className="mr-1.5 size-4" />
              Run Incremental Re-index
            </>
          )}
        </Button>
      </div>

      <SampleDataBanner message="Phase 1 Update Simulation — Commit history and file diffs use mock data without connecting to live GitHub webhooks." />

      {/* Current vs Latest Commit Banner */}
      {updatesQuery.isLoading || !data ? (
        <Skeleton className="h-24 w-full" />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-1.5">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                Currently Indexed Commit
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
                Latest Sample Remote Commit
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
                Synchronization Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.hasPendingUpdates ? (
                <span className="text-sm font-semibold text-amber-600 dark:text-amber-400">
                  1 commit behind · Incremental update available
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="size-4" />
                  Up to date with {data.latestRemoteSha}
                </span>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Simulated Progress Bar */}
      {reindexing && (
        <Card className="border-primary/40 bg-accent/20">
          <CardContent className="p-4 space-y-2.5">
            <div className="flex items-center justify-between text-xs font-medium">
              <span>Simulating incremental repository re-indexing...</span>
              <span className="font-mono tabular-nums">
                Step {Math.min(reindexStep + 1, REINDEX_STEPS.length)} of{' '}
                {REINDEX_STEPS.length}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-[width] duration-300"
                style={{
                  width: `${((reindexStep + 1) / REINDEX_STEPS.length) * 100}%`,
                }}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {REINDEX_STEPS[reindexStep] ?? 'Finalizing...'}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Commit History & Changed Files */}
      {!updatesQuery.isLoading && data && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="space-y-3 lg:col-span-5">
            <h2 className="text-sm font-semibold text-foreground">
              Commit History
            </h2>
            {data.commits.map((commit) => {
              const isSelected = activeCommit?.sha === commit.sha;
              return (
                <button
                  key={commit.sha}
                  type="button"
                  onClick={() => setSelectedCommitSha(commit.sha)}
                  className={cn(
                    'w-full rounded-xl border p-4 text-left transition-colors space-y-2',
                    isSelected
                      ? 'border-primary bg-accent/35'
                      : 'border-border bg-card hover:bg-muted/40'
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-semibold text-primary">
                      {commit.shortSha}
                    </span>
                    <StatusText status={commit.analysisStatus} />
                  </div>
                  <p className="text-sm font-medium text-foreground">
                    {commit.message}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {commit.author} · {formatRelativeTime(commit.timestamp)} ·{' '}
                    {commit.changedFiles.length} files changed
                  </p>
                </button>
              );
            })}
          </div>

          <div className="lg:col-span-7">
            {activeCommit && (
              <Card>
                <CardHeader className="border-b border-border">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <CardTitle className="text-base">
                        Commit {activeCommit.shortSha} Diff Summary
                      </CardTitle>
                      <CardDescription className="mt-0.5">
                        {activeCommit.message}
                      </CardDescription>
                    </div>
                    <StatusText status={activeCommit.analysisStatus} />
                  </div>
                  <p className="pt-2 text-xs text-muted-foreground">
                    {activeCommit.impactSummary}
                  </p>
                </CardHeader>

                <CardContent className="divide-y divide-border p-0">
                  {activeCommit.changedFiles.map((file) => {
                    const badge = CHANGE_BADGE[file.changeType];
                    const Icon = badge.icon;
                    return (
                      <div key={file.path} className="p-4 space-y-1.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <span
                              className={cn(
                                'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium shrink-0',
                                badge.classes
                              )}
                            >
                              <Icon className="size-3" />
                              {badge.label}
                            </span>
                            <span className="font-mono text-xs font-medium text-foreground truncate">
                              {file.path}
                            </span>
                          </div>

                          <span className="font-mono text-xs tabular-nums shrink-0">
                            <span className="text-emerald-600 dark:text-emerald-400">
                              +{file.additions}
                            </span>{' '}
                            <span className="text-muted-foreground">/</span>{' '}
                            <span className="text-destructive">
                              -{file.deletions}
                            </span>
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {file.summary}
                        </p>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
