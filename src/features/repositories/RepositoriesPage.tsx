import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Archive,
  ArchiveRestore,
  FolderGit2,
  Lock,
  Plus,
  Search,
  Trash2,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { SampleDataBanner } from '@/components/common/SampleDataBanner';
import { StatusText } from '@/components/common/StatusText';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { APP_ROUTES, getRepositoryRoute } from '@/constants/routes';
import { repositoryService } from '@/services';
import type { AnalysisStatus, Repository } from '@/types';
import { formatRelativeTime } from '@/utils/formatters';

type SortOption = 'recent' | 'name' | 'files';

export function RepositoriesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [languageFilter, setLanguageFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortOption>('recent');
  const [showArchived, setShowArchived] = useState(false);
  const [repoToDelete, setRepoToDelete] = useState<Repository | null>(null);

  const reposQuery = useQuery({
    queryKey: ['repositories'],
    queryFn: () => repositoryService.getRepositories(),
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => repositoryService.toggleArchiveRepository(id),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      toast.success(
        updated.isArchived
          ? `Archived "${updated.name}".`
          : `Restored "${updated.name}".`
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => repositoryService.deleteRepository(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      toast.success(`Removed "${repoToDelete?.name}" from workspace.`);
      setRepoToDelete(null);
    },
  });

  const repositories = reposQuery.data ?? [];

  const availableLanguages = useMemo(() => {
    const langs = new Set<string>();
    repositories.forEach((r) => langs.add(r.language));
    return Array.from(langs).sort();
  }, [repositories]);

  const filteredRepos = useMemo(() => {
    const q = search.trim().toLowerCase();
    return repositories
      .filter((repo) => {
        if (!showArchived && repo.isArchived) return false;
        if (languageFilter !== 'all' && repo.language !== languageFilter) {
          return false;
        }
        if (statusFilter !== 'all' && repo.status !== (statusFilter as AnalysisStatus)) {
          return false;
        }
        if (q) {
          const matches =
            repo.name.toLowerCase().includes(q) ||
            repo.owner.toLowerCase().includes(q) ||
            repo.description.toLowerCase().includes(q);
          if (!matches) return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'name') return a.name.localeCompare(b.name);
        if (sortBy === 'files') return b.fileCount - a.fileCount;
        return (
          new Date(b.lastAnalyzed).getTime() - new Date(a.lastAnalyzed).getTime()
        );
      });
  }, [repositories, showArchived, languageFilter, statusFilter, search, sortBy]);

  if (reposQuery.isError) {
    return (
      <ErrorState
        message="Unable to load repositories."
        onRetry={() => reposQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">
            Repositories
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage connected GitHub repositories and uploaded ZIP archives.
          </p>
        </div>
        <Button asChild size="sm" className="w-fit whitespace-nowrap shrink-0">
          <Link to={APP_ROUTES.REPOSITORIES_ADD}>
            <Plus className="mr-1.5 size-4" />
            Add Repository
          </Link>
        </Button>
      </div>

      <SampleDataBanner />

      {/* Filter Toolbar */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-12">
        <div className="relative lg:col-span-4">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by repository or owner..."
            className="pl-9"
          />
        </div>

        <div className="lg:col-span-2">
          <Select value={languageFilter} onValueChange={setLanguageFilter}>
            <SelectTrigger>
              <SelectValue placeholder="Language" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Languages</SelectItem>
              {availableLanguages.map((lang) => (
                <SelectItem key={lang} value={lang}>
                  {lang}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="lg:col-span-2">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger>
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="analyzing">Analyzing</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="lg:col-span-2">
          <Select
            value={sortBy}
            onValueChange={(val) => setSortBy(val as SortOption)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="recent">Recently Analyzed</SelectItem>
              <SelectItem value="name">Name (A–Z)</SelectItem>
              <SelectItem value="files">File Count</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center lg:col-span-2">
          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
              className="size-4 rounded border-input accent-primary"
            />
            <span>Show archived</span>
          </label>
        </div>
      </div>

      {/* Repository List */}
      {reposQuery.isLoading ? (
        <Card className="p-6 space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </Card>
      ) : filteredRepos.length === 0 ? (
        <EmptyState
          icon={<FolderGit2 className="size-5" />}
          title="No matching repositories"
          description={
            repositories.length === 0
              ? 'Your workspace does not have any repositories yet. Connect a GitHub repository or upload a ZIP archive to begin.'
              : 'No repositories match your current search or filter criteria. Clear filters or add a new repository.'
          }
          actionLabel={
            repositories.length === 0 ? 'Add Repository' : 'Clear Filters'
          }
          onAction={() => {
            if (repositories.length === 0) {
              navigate(APP_ROUTES.REPOSITORIES_ADD);
            } else {
              setSearch('');
              setLanguageFilter('all');
              setStatusFilter('all');
              setShowArchived(false);
            }
          }}
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Repository</th>
                  <th className="px-4 py-3">Language</th>
                  <th className="px-4 py-3">Branch & Commit</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Files</th>
                  <th className="px-4 py-3">Last Analyzed</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredRepos.map((repo) => (
                  <tr
                    key={repo.id}
                    className="hover:bg-muted/30 transition-colors"
                  >
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2">
                        <Link
                          to={getRepositoryRoute(repo.id)}
                          className="font-medium text-foreground hover:text-primary transition-colors"
                        >
                          {repo.owner}/{repo.name}
                        </Link>
                        {repo.isPrivate && (
                          <Lock
                            className="size-3.5 text-muted-foreground shrink-0"
                            aria-label="Private repository"
                          />
                        )}
                        {repo.isArchived && (
                          <span className="text-[11px] font-medium text-muted-foreground">
                            (Archived)
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground line-clamp-1 max-w-md">
                        {repo.description}
                      </p>
                    </td>
                    <td className="px-4 py-3.5 text-xs text-foreground whitespace-nowrap">
                      {repo.language}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-xs text-muted-foreground whitespace-nowrap">
                      {repo.branch} · {repo.commitSha}
                    </td>
                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <StatusText status={repo.status} />
                    </td>
                    <td className="px-4 py-3.5 text-right font-mono text-xs tabular-nums">
                      {repo.fileCount}
                    </td>
                    <td className="px-4 py-3.5 text-xs text-muted-foreground whitespace-nowrap tabular-nums">
                      {formatRelativeTime(repo.lastAnalyzed)}
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button asChild variant="outline" size="xs">
                          <Link to={getRepositoryRoute(repo.id)}>Open</Link>
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => archiveMutation.mutate(repo.id)}
                          aria-label={
                            repo.isArchived
                              ? `Unarchive ${repo.name}`
                              : `Archive ${repo.name}`
                          }
                          title={repo.isArchived ? 'Restore' : 'Archive'}
                        >
                          {repo.isArchived ? (
                            <ArchiveRestore className="size-3.5" />
                          ) : (
                            <Archive className="size-3.5" />
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => setRepoToDelete(repo)}
                          aria-label={`Delete ${repo.name}`}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <ConfirmDialog
        open={Boolean(repoToDelete)}
        onOpenChange={(open) => {
          if (!open) setRepoToDelete(null);
        }}
        title="Delete repository from workspace?"
        description={`This removes "${repoToDelete?.owner}/${repoToDelete?.name}" and its sample index data from your current session.`}
        confirmLabel="Delete Repository"
        destructive
        isLoading={deleteMutation.isPending}
        onConfirm={() => {
          if (repoToDelete) deleteMutation.mutate(repoToDelete.id);
        }}
      />
    </div>
  );
}
