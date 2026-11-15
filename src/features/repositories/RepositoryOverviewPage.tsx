import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  BookOpen,
  ExternalLink,
  Folder,
  FolderTree,
  GitBranch,
  GitCommit,
  GitCompare,
  Lock,
  MessageSquareCode,
  Network,
  Share2,
} from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { ConfidenceBadge } from '@/components/common/ConfidenceBadge';
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
import { getRepositoryRoute } from '@/constants/routes';
import { explorerService, repositoryService } from '@/services';
import type { RepositoryFileNode } from '@/types';
import { formatRelativeTime } from '@/utils/formatters';

function renderFolderPreview(nodes: RepositoryFileNode[], depth = 0) {
  return nodes.slice(0, 6).map((node) => (
    <div key={node.id} style={{ paddingLeft: `${depth * 14}px` }}>
      <div className="flex items-center gap-2 py-1 text-xs text-foreground">
        {node.type === 'folder' ? (
          <Folder className="size-3.5 text-primary shrink-0" />
        ) : (
          <span className="size-1.5 rounded-full bg-muted-foreground/60 ml-1 mr-1 shrink-0" />
        )}
        <span className="font-mono truncate">{node.name}</span>
      </div>
      {node.children && depth < 1 && renderFolderPreview(node.children, depth + 1)}
    </div>
  ));
}

export function RepositoryOverviewPage() {
  const { id = 'repo-cloud-gateway' } = useParams<{ id: string }>();

  const overviewQuery = useQuery({
    queryKey: ['repository-overview', id],
    queryFn: () => repositoryService.getRepositoryOverview(id),
  });

  const treeQuery = useQuery({
    queryKey: ['file-tree', id],
    queryFn: () => explorerService.getFileTree(id),
  });

  if (overviewQuery.isError) {
    return (
      <ErrorState
        message={
          overviewQuery.error instanceof Error
            ? overviewQuery.error.message
            : 'Failed to load repository overview.'
        }
        onRetry={() => overviewQuery.refetch()}
      />
    );
  }

  if (overviewQuery.isLoading || !overviewQuery.data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24 w-full" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const { repository, recentCommits, importantModules, dependencyStats } =
    overviewQuery.data;

  const quickLinks = [
    {
      label: 'Project Explorer',
      desc: 'Browse files, symbols & code explanations',
      to: getRepositoryRoute(id, 'explorer'),
      icon: FolderTree,
    },
    {
      label: 'Architecture Graph',
      desc: 'Interactive module & boundary map',
      to: getRepositoryRoute(id, 'architecture'),
      icon: Network,
    },
    {
      label: 'Execution Tracing',
      desc: 'Step-by-step caller & callee flows',
      to: getRepositoryRoute(id, 'execution'),
      icon: Activity,
    },
    {
      label: 'Dependencies',
      desc: 'Imports & circular cycle analysis',
      to: getRepositoryRoute(id, 'dependencies'),
      icon: Share2,
    },
    {
      label: 'Updates',
      desc: 'Commit diffs & incremental indexing',
      to: getRepositoryRoute(id, 'updates'),
      icon: GitCompare,
    },
    {
      label: 'Documentation',
      desc: 'Markdown & Mermaid technical specs',
      to: getRepositoryRoute(id, 'docs'),
      icon: BookOpen,
    },
    {
      label: 'AI Assistant',
      desc: 'Sample Q&A with code citations',
      to: getRepositoryRoute(id, 'assistant'),
      icon: MessageSquareCode,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header Summary */}
      <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2 min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="font-heading text-2xl font-bold tracking-tight">
              {repository.owner}/{repository.name}
            </h1>
            {repository.isPrivate && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Lock className="size-3.5" /> Private
              </span>
            )}
            <StatusText status={repository.status} />
          </div>
          <p className="max-w-3xl text-sm text-muted-foreground">
            {repository.description}
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1 font-mono">
              <GitBranch className="size-3.5" /> {repository.branch}
            </span>
            <span className="inline-flex items-center gap-1 font-mono">
              <GitCommit className="size-3.5" /> {repository.commitSha}
            </span>
            <span>Analyzed {formatRelativeTime(repository.lastAnalyzed)}</span>
            {repository.sourceType === 'github' && (
              <a
                href={repository.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                <span>GitHub URL</span>
                <ExternalLink className="size-3" />
              </a>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Button asChild size="sm">
            <Link to={getRepositoryRoute(id, 'explorer')}>
              <FolderTree className="mr-1.5 size-4" />
              Open Explorer
            </Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link to={getRepositoryRoute(id, 'assistant')}>
              <MessageSquareCode className="mr-1.5 size-4" />
              Ask Assistant
            </Link>
          </Button>
        </div>
      </div>

      <SampleDataBanner />

      {/* Stats Strip */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-1.5">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Total Files / Folders
            </CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-xl font-bold tabular-nums">
            {repository.fileCount}{' '}
            <span className="text-sm font-normal text-muted-foreground">
              / {repository.folderCount} folders
            </span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-1.5">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Primary Language
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xl font-bold">
            {repository.language}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-1.5">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Detected Frameworks
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm font-medium text-foreground">
            {repository.frameworks.join(' · ')}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-1.5">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Dependency Summary
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-0.5 tabular-nums">
            <p className="font-mono text-sm font-semibold text-foreground">
              {dependencyStats.internalModules} internal ·{' '}
              {dependencyStats.externalPackages} external
            </p>
            <p className="text-amber-600 dark:text-amber-400">
              {dependencyStats.circularCycles} circular cycle(s) flagged
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Feature Links */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {quickLinks.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.to}
              to={item.to}
              className="group flex items-start gap-3 rounded-lg border border-border bg-card p-3.5 hover:border-primary/50 hover:bg-muted/30 transition-colors"
            >
              <Icon className="mt-0.5 size-4 text-primary shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                  {item.label}
                </p>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Detailed Panels */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-7">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Important Modules</CardTitle>
              <CardDescription>
                Key files and architectural entry points identified in sample index
              </CardDescription>
            </CardHeader>
            <CardContent className="divide-y divide-border p-0">
              {importantModules.map((mod) => (
                <div
                  key={mod.path}
                  className="flex flex-col gap-2 px-6 py-3.5 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 space-y-0.5">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`${getRepositoryRoute(id, 'explorer')}?file=${encodeURIComponent(mod.path)}`}
                        className="text-sm font-semibold text-foreground hover:text-primary"
                      >
                        {mod.name}
                      </Link>
                      <ConfidenceBadge confidence={mod.confidence} />
                    </div>
                    <p className="font-mono text-xs text-muted-foreground truncate">
                      {mod.path} · {mod.symbolCount} symbols
                    </p>
                    <p className="text-xs text-muted-foreground">{mod.role}</p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base">Recent Commits</CardTitle>
                <CardDescription>Sample commit history snapshot</CardDescription>
              </div>
              <Button asChild variant="ghost" size="sm">
                <Link to={getRepositoryRoute(id, 'updates')}>
                  View Updates
                </Link>
              </Button>
            </CardHeader>
            <CardContent className="divide-y divide-border p-0">
              {recentCommits.map((commit) => (
                <div
                  key={commit.sha}
                  className="flex items-start justify-between gap-4 px-6 py-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {commit.message}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {commit.author} · {commit.filesChanged} files changed ·{' '}
                      {formatRelativeTime(commit.date)}
                    </p>
                  </div>
                  <span className="font-mono text-xs text-muted-foreground shrink-0">
                    {commit.sha}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Language Breakdown</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {Object.entries(repository.languages).map(([lang, pct]) => (
                <div key={lang} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-foreground">{lang}</span>
                    <span className="font-mono text-muted-foreground tabular-nums">
                      {pct}%
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-primary"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base">Folder Structure Preview</CardTitle>
                <CardDescription>Top-level project layout</CardDescription>
              </div>
              <Button asChild variant="outline" size="xs">
                <Link to={getRepositoryRoute(id, 'explorer')}>Browse All</Link>
              </Button>
            </CardHeader>
            <CardContent>
              {treeQuery.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : (
                <div className="rounded-md border border-border bg-muted/30 p-3">
                  {renderFolderPreview(treeQuery.data ?? [])}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
