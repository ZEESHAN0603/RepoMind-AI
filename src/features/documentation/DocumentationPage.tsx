import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Archive,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Clock,
  Download,
  Edit3,
  Eye,
  FileCode,
  FileText,
  History,
  Layers,
  Loader2,
  RefreshCw,
  Save,
  Share2,
  ShieldCheck,
  SplitSquareHorizontal,
  Workflow,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import Markdown from 'react-markdown';
import { useParams } from 'react-router-dom';
import remarkGfm from 'remark-gfm';
import { toast } from 'sonner';
import { ConfidenceBadge } from '@/components/common/ConfidenceBadge';
import { ErrorState } from '@/components/common/ErrorState';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { apiDocumentationService } from '@/services/api/documentation.api';
import { documentationService } from '@/services';
import type { DocSectionType, DocumentationDocument } from '@/types';
import { formatRelativeTime } from '@/utils/formatters';
import { MermaidDiagram } from './MermaidDiagram';

type ViewMode = 'preview' | 'edit' | 'split' | 'history';

interface DocMetadata {
  type: string;
  label: string;
  icon: any;
  description: string;
}

const DOC_METAS: DocMetadata[] = [
  {
    type: 'readme',
    label: 'README Overview',
    icon: FileText,
    description: 'Project summary, tech stack, installation, environment variables, and execution setup.',
  },
  {
    type: 'architecture',
    label: 'System Architecture',
    icon: Layers,
    description: 'Layered component boundaries, interactive Mermaid diagrams, and structural roles.',
  },
  {
    type: 'api',
    label: 'API Reference',
    icon: Share2,
    description: 'Discovered REST route declarations, handlers, parameters, and framework schemas.',
  },
  {
    type: 'execution_flow',
    label: 'Execution Flows',
    icon: Workflow,
    description: 'System entry points, function call chains, and static analysis boundaries.',
  },
  {
    type: 'dependencies',
    label: 'Dependencies & Cycles',
    icon: Zap,
    description: 'Module import relationships, third-party packages, and circular dependency evaluation.',
  },
  {
    type: 'update_changelog',
    label: 'Update Changelog',
    icon: Clock,
    description: 'Historical commits, AST symbol diffs, and blast-radius impact summaries.',
  },
  {
    type: 'code_reference',
    label: 'Code Reference',
    icon: FileCode,
    description: 'Functions, classes, parameters, return types, exceptions, and line-level citations.',
  },
];

export function DocumentationPage() {
  const { id = 'repo-cloud-gateway' } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [selectedType, setSelectedType] = useState<string>('readme');
  const [viewMode, setViewMode] = useState<ViewMode>('preview');
  const [draftContent, setDraftContent] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);

  // Load all repository documents
  const docsQuery = useQuery({
    queryKey: ['repository-docs', id],
    queryFn: () => documentationService.getDocuments(id),
  });

  const activeDoc =
    docsQuery.data?.find((doc) => doc.type === selectedType) ??
    docsQuery.data?.[0] ??
    null;

  useEffect(() => {
    if (activeDoc) {
      setDraftContent(activeDoc.content);
      setIsDirty(false);
    }
  }, [activeDoc]);

  // Save document mutation
  const saveMutation = useMutation({
    mutationFn: () =>
      apiDocumentationService.saveDocument(
        id,
        selectedType,
        draftContent,
        'Manual user edit in Documentation Workspace'
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData(
        ['repository-docs', id],
        (old: DocumentationDocument[] | undefined) =>
          old?.map((d) => (d.type === updated.type ? updated : d)) ?? [updated]
      );
      setIsDirty(false);
      toast.success(`Saved "${updated.title}" as v${updated.versionNumber}.`);
    },
    onError: () => toast.error('Failed to save document modifications.'),
  });

  // Regenerate single section mutation
  const regenerateMutation = useMutation({
    mutationFn: () => apiDocumentationService.regenerateDocument(id, selectedType),
    onSuccess: (fresh) => {
      queryClient.setQueryData(
        ['repository-docs', id],
        (old: DocumentationDocument[] | undefined) =>
          old?.map((d) => (d.type === fresh.type ? fresh : d)) ?? [fresh]
      );
      setDraftContent(fresh.content);
      setIsDirty(false);
      toast.success(`Regenerated "${fresh.title}" from latest repository analysis.`);
    },
    onError: () => toast.error('Failed to regenerate section.'),
  });

  // Generate complete suite mutation
  const generateAllMutation = useMutation({
    mutationFn: () => apiDocumentationService.generateAllDocuments(id),
    onSuccess: (allDocs) => {
      queryClient.setQueryData(['repository-docs', id], allDocs);
      const current = allDocs.find((d) => d.type === selectedType) || allDocs[0];
      if (current) {
        setDraftContent(current.content);
        setIsDirty(false);
      }
      toast.success(`Generated ${allDocs.length} technical documentation sections.`);
    },
    onError: () => toast.error('Full documentation generation failed.'),
  });

  // Approve document mutation
  const approveMutation = useMutation({
    mutationFn: () => apiDocumentationService.approveDocument(id, selectedType),
    onSuccess: (result) => {
      queryClient.setQueryData(
        ['repository-docs', id],
        (old: DocumentationDocument[] | undefined) =>
          old?.map((d) =>
            d.type === selectedType
              ? { ...d, status: 'approved' as const, approvedAt: result.approvedAt }
              : d
          )
      );
      toast.success(`Document marked as approved.`);
    },
    onError: () => toast.error('Approval failed.'),
  });

  // Export handlers
  const handleExportMarkdown = async () => {
    if (!activeDoc) return;
    try {
      await apiDocumentationService.downloadDocument(id, selectedType, 'markdown');
      toast.success(`Downloaded ${selectedType}.md`);
    } catch {
      // Client-side fallback
      const blob = new Blob([draftContent], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${id}-${selectedType}.md`;
      link.click();
      URL.revokeObjectURL(url);
      toast.success(`Exported ${selectedType}.md`);
    }
  };

  const handleExportHTML = async () => {
    if (!activeDoc) return;
    try {
      await apiDocumentationService.downloadDocument(id, selectedType, 'html');
      toast.success(`Downloaded ${selectedType}.html`);
    } catch {
      toast.error('HTML export failed.');
    }
  };

  const handleExportPackage = async () => {
    try {
      await apiDocumentationService.downloadPackage(id);
      toast.success('Downloaded complete documentation package (.zip).');
    } catch {
      toast.error('ZIP package export failed.');
    }
  };

  if (docsQuery.isError) {
    return (
      <ErrorState
        message="Unable to load repository documentation."
        onRetry={() => docsQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Header Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-heading text-2xl font-bold tracking-tight">
              Documentation Workspace
            </h1>
            <Badge variant="outline" className="text-xs font-semibold">
              Phase 10
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Automatic, evidence-grounded technical documentation generated across Phases 3–9.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Generate All */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => generateAllMutation.mutate()}
            disabled={generateAllMutation.isPending || docsQuery.isLoading}
            title="Re-run static intelligence across all 7 documentation sections"
          >
            {generateAllMutation.isPending ? (
              <Loader2 className="mr-1.5 size-3.5 animate-spin" />
            ) : (
              <Zap className="mr-1.5 size-3.5 text-primary" />
            )}
            Generate All
          </Button>

          {/* Regenerate Section */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => regenerateMutation.mutate()}
            disabled={regenerateMutation.isPending || docsQuery.isLoading}
          >
            {regenerateMutation.isPending ? (
              <Loader2 className="mr-1.5 size-3.5 animate-spin" />
            ) : (
              <RefreshCw className="mr-1.5 size-3.5" />
            )}
            Regenerate Section
          </Button>

          {/* Approve Button */}
          {activeDoc && activeDoc.status !== 'approved' && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => approveMutation.mutate()}
              disabled={approveMutation.isPending}
              className="border-emerald-600/40 text-emerald-600 hover:bg-emerald-500/10 dark:text-emerald-400"
            >
              <CheckCircle2 className="mr-1.5 size-3.5 text-emerald-500" />
              Approve
            </Button>
          )}

          {/* Export Dropdown Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="outline" size="sm">
                <Download className="mr-1.5 size-3.5" />
                Export
                <ChevronDown className="ml-1 size-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleExportMarkdown}>
                <FileText className="mr-2 size-4 text-primary" />
                Export Active (.md)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleExportHTML}>
                <FileCode className="mr-2 size-4 text-blue-500" />
                Export Standalone (.html)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleExportPackage}>
                <Archive className="mr-2 size-4 text-emerald-500" />
                Export Complete Package (.zip)
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Save Button */}
          <Button
            type="button"
            size="sm"
            onClick={() => saveMutation.mutate()}
            disabled={!isDirty || saveMutation.isPending}
          >
            {saveMutation.isPending ? (
              <Loader2 className="mr-1.5 size-3.5 animate-spin" />
            ) : (
              <Save className="mr-1.5 size-3.5" />
            )}
            {isDirty ? 'Save Changes' : 'Saved'}
          </Button>
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Document Categories Sidebar */}
        <aside className="space-y-1.5 lg:col-span-3">
          <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Documentation Sections
          </div>
          {docsQuery.isLoading ? (
            <Skeleton className="h-80 w-full" />
          ) : (
            DOC_METAS.map((meta) => {
              const doc = docsQuery.data?.find((d) => d.type === meta.type);
              const active = (doc?.type || meta.type) === selectedType;
              const IconComponent = meta.icon;

              return (
                <button
                  key={meta.type}
                  type="button"
                  onClick={() => setSelectedType(meta.type)}
                  className={cn(
                    'w-full rounded-lg border px-3.5 py-2.5 text-left transition-colors',
                    active
                      ? 'border-primary bg-accent/40 shadow-xs'
                      : 'border-border bg-card hover:bg-muted/40'
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 text-xs font-semibold text-foreground">
                      <IconComponent className="size-3.5 text-primary shrink-0" />
                      {doc?.title || meta.label}
                    </span>
                    {doc && (
                      <span
                        className={cn(
                          'rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase',
                          doc.status === 'approved'
                            ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                            : 'bg-muted text-muted-foreground'
                        )}
                      >
                        {doc.status}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-[11px] text-muted-foreground line-clamp-2">
                    {doc?.description || meta.description}
                  </p>
                </button>
              );
            })
          )}
        </aside>

        {/* Editor & Preview Workspace */}
        <Card className="flex min-h-[620px] flex-col overflow-hidden lg:col-span-9">
          {docsQuery.isLoading || !activeDoc ? (
            <div className="p-6">
              <Skeleton className="h-[550px] w-full" />
            </div>
          ) : (
            <>
              {/* Workspace Header Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-2.5">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="text-sm font-semibold text-foreground truncate">
                    {activeDoc.title}
                  </span>
                  <ConfidenceBadge confidence={activeDoc.confidence} />
                  <Badge variant="outline" className="text-[10px] font-mono">
                    v{activeDoc.versionNumber}
                  </Badge>
                  {activeDoc.status === 'approved' && (
                    <Badge variant="secondary" className="gap-1 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px]">
                      <ShieldCheck className="size-3" />
                      Approved
                    </Badge>
                  )}
                  <span className="hidden sm:inline text-xs text-muted-foreground">
                    Updated {formatRelativeTime(activeDoc.lastUpdated)}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowEvidence(!showEvidence)}
                    className={cn('h-7 text-xs', showEvidence && 'bg-accent text-accent-foreground')}
                  >
                    Evidence
                  </Button>

                  <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
                    <button
                      type="button"
                      onClick={() => setViewMode('preview')}
                      className={cn(
                        'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                        viewMode === 'preview'
                          ? 'bg-card text-foreground shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      <Eye className="size-3.5" />
                      Preview
                    </button>
                    <button
                      type="button"
                      onClick={() => setViewMode('edit')}
                      className={cn(
                        'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                        viewMode === 'edit'
                          ? 'bg-card text-foreground shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      <Edit3 className="size-3.5" />
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => setViewMode('split')}
                      className={cn(
                        'hidden md:inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                        viewMode === 'split'
                          ? 'bg-card text-foreground shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      <SplitSquareHorizontal className="size-3.5" />
                      Split
                    </button>
                    <button
                      type="button"
                      onClick={() => setViewMode('history')}
                      className={cn(
                        'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                        viewMode === 'history'
                          ? 'bg-card text-foreground shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      <History className="size-3.5" />
                      History
                    </button>
                  </div>
                </div>
              </div>

              {/* Source Evidence Collapsible Drawer */}
              {showEvidence && (
                <div className="border-b border-border bg-muted/30 px-4 py-3 text-xs">
                  <div className="font-semibold text-foreground mb-1.5 flex items-center gap-1.5">
                    <BookOpen className="size-3.5 text-primary" />
                    Source Evidence & Verification Citations:
                  </div>
                  <pre className="max-h-36 overflow-auto rounded bg-card p-2 text-[11px] font-mono text-muted-foreground border border-border">
                    {JSON.stringify(activeDoc.sourceEvidence || {}, null, 2)}
                  </pre>
                </div>
              )}

              {/* Content Panel */}
              <div
                className={cn(
                  'grid flex-1 min-h-0',
                  viewMode === 'split' ? 'md:grid-cols-2' : 'grid-cols-1'
                )}
              >
                {/* Edit View */}
                {(viewMode === 'edit' || viewMode === 'split') && (
                  <div
                    className={cn(
                      'flex flex-col p-4',
                      viewMode === 'split' && 'border-b md:border-b-0 md:border-r border-border'
                    )}
                  >
                    <Textarea
                      value={draftContent}
                      onChange={(e) => {
                        setDraftContent(e.target.value);
                        setIsDirty(true);
                      }}
                      aria-label="Markdown documentation editor"
                      className="min-h-[520px] flex-1 resize-none font-mono text-xs leading-relaxed"
                      placeholder="Write or edit documentation Markdown here..."
                    />
                  </div>
                )}

                {/* Preview View */}
                {(viewMode === 'preview' || viewMode === 'split') && (
                  <ScrollArea className="h-[580px] p-6">
                    <article className="space-y-4 text-sm leading-relaxed text-foreground [&_h1]:font-heading [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:tracking-tight [&_h2]:font-heading [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:pt-3 [&_h3]:text-base [&_h3]:font-semibold [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_code]:rounded [&_code]:bg-muted [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:border [&_pre]:border-border [&_pre]:bg-muted/50 [&_pre]:p-3.5 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_blockquote]:rounded-md [&_blockquote]:border [&_blockquote]:border-border [&_blockquote]:bg-muted/40 [&_blockquote]:px-4 [&_blockquote]:py-2.5 [&_blockquote]:text-xs [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-border [&_th]:bg-muted/40 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:text-xs [&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-2 [&_td]:text-xs">
                      <Markdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code(props) {
                            const { className, children, ...rest } = props;
                            const match = /language-(\w+)/.exec(className || '');
                            const lang = match?.[1];
                            const content = String(children).replace(/\n$/, '');

                            if (lang === 'mermaid') {
                              return <MermaidDiagram chart={content} />;
                            }
                            return (
                              <code className={className} {...rest}>
                                {children}
                              </code>
                            );
                          },
                        }}
                      >
                        {draftContent}
                      </Markdown>
                    </article>
                  </ScrollArea>
                )}

                {/* Version History View */}
                {viewMode === 'history' && (
                  <ScrollArea className="h-[580px] p-6">
                    <div className="space-y-4">
                      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                        Document Revision Snapshots
                      </h2>
                      {(!activeDoc.versions || activeDoc.versions.length === 0) ? (
                        <p className="text-xs text-muted-foreground">
                          Currently at version {activeDoc.versionNumber}. Save edits or regenerate to create new version snapshots.
                        </p>
                      ) : (
                        <div className="space-y-3">
                          {activeDoc.versions.map((v) => (
                            <div
                              key={v.id}
                              className="rounded-lg border border-border bg-card p-3.5 space-y-2 text-xs"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-foreground">
                                  Version {v.versionNumber}
                                </span>
                                <span className="text-[11px] text-muted-foreground">
                                  {formatRelativeTime(v.createdAt)}
                                </span>
                              </div>
                              <p className="text-muted-foreground">
                                {v.changeSummary || 'No summary specified.'}
                              </p>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                  setDraftContent(v.content);
                                  setViewMode('preview');
                                  setIsDirty(true);
                                  toast.info(`Loaded Version ${v.versionNumber} content into workspace.`);
                                }}
                                className="h-6 text-[11px]"
                              >
                                Restore into Editor
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                )}
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
