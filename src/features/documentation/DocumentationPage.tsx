import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BookOpen,
  Download,
  Edit3,
  Eye,
  Loader2,
  RefreshCw,
  Save,
  SplitSquareHorizontal,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import Markdown from 'react-markdown';
import { useParams } from 'react-router-dom';
import remarkGfm from 'remark-gfm';
import { toast } from 'sonner';
import { ConfidenceBadge } from '@/components/common/ConfidenceBadge';
import { ErrorState } from '@/components/common/ErrorState';
import { SampleDataBanner } from '@/components/common/SampleDataBanner';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { documentationService } from '@/services';
import type { DocSectionType } from '@/types';
import { formatRelativeTime } from '@/utils/formatters';
import { MermaidDiagram } from './MermaidDiagram';

type ViewMode = 'preview' | 'edit' | 'split';

const DOC_ORDER: DocSectionType[] = [
  'readme',
  'architecture',
  'module',
  'api',
  'database',
  'onboarding',
];

export function DocumentationPage() {
  const { id = 'repo-cloud-gateway' } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [selectedType, setSelectedType] = useState<DocSectionType>('architecture');
  const [viewMode, setViewMode] = useState<ViewMode>('preview');
  const [draftContent, setDraftContent] = useState('');
  const [isDirty, setIsDirty] = useState(false);

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

  const saveMutation = useMutation({
    mutationFn: () =>
      documentationService.saveDocument(id, selectedType, draftContent),
    onSuccess: (updated) => {
      queryClient.setQueryData(
        ['repository-docs', id],
        (old: typeof docsQuery.data) =>
          old?.map((d) => (d.type === updated.type ? updated : d)) ?? [updated]
      );
      setIsDirty(false);
      toast.success(`Saved "${updated.title}" (mock Phase 1 storage).`);
    },
    onError: () => toast.error('Failed to save documentation.'),
  });

  const regenerateMutation = useMutation({
    mutationFn: () => documentationService.regenerateDocument(id, selectedType),
    onSuccess: (fresh) => {
      queryClient.setQueryData(
        ['repository-docs', id],
        (old: typeof docsQuery.data) =>
          old?.map((d) => (d.type === fresh.type ? fresh : d)) ?? [fresh]
      );
      setDraftContent(fresh.content);
      setIsDirty(false);
      toast.success(`Regenerated sample "${fresh.title}".`);
    },
    onError: () => toast.error('Failed to regenerate documentation.'),
  });

  const handleExportMarkdown = () => {
    if (!activeDoc) return;
    const blob = new Blob([draftContent], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${id}-${activeDoc.type}.md`;
    link.click();
    URL.revokeObjectURL(url);
    toast.success(`Exported ${activeDoc.type}.md`);
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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">
            Documentation Center
          </h1>
          <p className="text-sm text-muted-foreground">
            Edit, preview, regenerate, and export technical repository documentation.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
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
            Regenerate
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleExportMarkdown}
            disabled={!activeDoc}
          >
            <Download className="mr-1.5 size-3.5" />
            Export .md
          </Button>
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

      <SampleDataBanner message="Sample Documentation — Markdown and Mermaid diagrams shown here are sample Phase 1 documents. Edits persist in memory during this session." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Document Selector */}
        <aside className="space-y-1.5 lg:col-span-3">
          {docsQuery.isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            DOC_ORDER.map((type) => {
              const doc = docsQuery.data?.find((d) => d.type === type);
              if (!doc) return null;
              const active = doc.type === selectedType;
              return (
                <button
                  key={doc.id}
                  type="button"
                  onClick={() => setSelectedType(doc.type)}
                  className={cn(
                    'w-full rounded-lg border px-3.5 py-2.5 text-left transition-colors',
                    active
                      ? 'border-primary bg-accent/40'
                      : 'border-border bg-card hover:bg-muted/40'
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 text-xs font-semibold text-foreground">
                      <BookOpen className="size-3.5 text-primary shrink-0" />
                      {doc.title}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-muted-foreground line-clamp-2">
                    {doc.description}
                  </p>
                </button>
              );
            })
          )}
        </aside>

        {/* Editor / Preview Workspace */}
        <Card className="flex min-h-[580px] flex-col overflow-hidden lg:col-span-9">
          {docsQuery.isLoading || !activeDoc ? (
            <div className="p-6">
              <Skeleton className="h-[500px] w-full" />
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-2.5">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="text-sm font-semibold text-foreground truncate">
                    {activeDoc.title}
                  </span>
                  <ConfidenceBadge confidence={activeDoc.confidence} />
                  <span className="hidden sm:inline text-xs text-muted-foreground">
                    Updated {formatRelativeTime(activeDoc.lastUpdated)}
                  </span>
                </div>

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
                </div>
              </div>

              <div
                className={cn(
                  'grid flex-1 min-h-0',
                  viewMode === 'split' ? 'md:grid-cols-2' : 'grid-cols-1'
                )}
              >
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
                      aria-label="Markdown editor"
                      className="min-h-[480px] flex-1 resize-none font-mono text-xs leading-relaxed"
                    />
                  </div>
                )}

                {(viewMode === 'preview' || viewMode === 'split') && (
                  <ScrollArea className="h-[540px] p-6">
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
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
