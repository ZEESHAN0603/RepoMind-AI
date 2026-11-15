import Editor, { type OnMount } from '@monaco-editor/react';
import { useQuery } from '@tanstack/react-query';
import {
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  FileCode,
  Folder,
  FolderOpen,
  Search,
  Sparkles,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ConfidenceBadge } from '@/components/common/ConfidenceBadge';
import { ErrorState } from '@/components/common/ErrorState';
import { SampleDataBanner } from '@/components/common/SampleDataBanner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { explorerService } from '@/services';
import { useThemeStore } from '@/stores/theme.store';
import type { CodeSymbol, RepositoryFileNode } from '@/types';

const DEFAULT_FILE = 'src/middleware/auth.middleware.ts';

function filterTree(
  nodes: RepositoryFileNode[],
  query: string
): RepositoryFileNode[] {
  if (!query.trim()) return nodes;
  const q = query.trim().toLowerCase();
  const result: RepositoryFileNode[] = [];

  for (const node of nodes) {
    if (node.type === 'file') {
      if (
        node.name.toLowerCase().includes(q) ||
        node.path.toLowerCase().includes(q)
      ) {
        result.push(node);
      }
    } else if (node.children) {
      const filteredChildren = filterTree(node.children, query);
      if (filteredChildren.length > 0) {
        result.push({ ...node, children: filteredChildren });
      }
    }
  }
  return result;
}

export function ExplorerPage() {
  const { id = 'repo-cloud-gateway' } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const theme = useThemeStore((state) => state.theme);

  const requestedFile = searchParams.get('file') || DEFAULT_FILE;
  const [openTabs, setOpenTabs] = useState<string[]>([
    requestedFile,
    ...(requestedFile !== 'src/routes/proxy.router.ts'
      ? ['src/routes/proxy.router.ts']
      : []),
  ]);
  const [activeFile, setActiveFile] = useState<string>(requestedFile);
  const [fileSearch, setFileSearch] = useState('');
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({
    src: true,
    'src/routes': true,
    'src/middleware': true,
    'src/services': true,
  });
  const [selectedSymbol, setSelectedSymbol] = useState<CodeSymbol | null>(null);
  const [copied, setCopied] = useState(false);
  const [mobilePanel, setMobilePanel] = useState<'files' | 'code' | 'ai'>('code');

  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);

  useEffect(() => {
    const paramFile = searchParams.get('file');
    if (paramFile && paramFile !== activeFile) {
      setActiveFile(paramFile);
      setOpenTabs((prev) =>
        prev.includes(paramFile) ? prev : [...prev, paramFile]
      );
    }
  }, [searchParams, activeFile]);

  const treeQuery = useQuery({
    queryKey: ['file-tree', id],
    queryFn: () => explorerService.getFileTree(id),
  });

  const fileQuery = useQuery({
    queryKey: ['file-intelligence', id, activeFile],
    queryFn: () => explorerService.getFileIntelligence(id, activeFile),
    enabled: Boolean(activeFile),
  });

  useEffect(() => {
    setSelectedSymbol(null);
  }, [activeFile]);

  const filteredTree = useMemo(
    () => filterTree(treeQuery.data ?? [], fileSearch),
    [treeQuery.data, fileSearch]
  );

  const openFile = (path: string) => {
    setActiveFile(path);
    setOpenTabs((prev) => (prev.includes(path) ? prev : [...prev, path]));
    setSearchParams({ file: path }, { replace: true });
    setMobilePanel('code');
  };

  const closeTab = (path: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setOpenTabs((prev) => {
      const next = prev.filter((item) => item !== path);
      if (activeFile === path && next.length > 0) {
        const fallback = next[next.length - 1];
        setActiveFile(fallback);
        setSearchParams({ file: fallback }, { replace: true });
      }
      return next;
    });
  };

  const jumpToLine = (line: number) => {
    if (editorRef.current) {
      editorRef.current.revealLineInCenter(line);
      editorRef.current.setPosition({ lineNumber: line, column: 1 });
      editorRef.current.focus();
    }
  };

  const handleCopyCode = async () => {
    if (!fileQuery.data?.content) return;
    try {
      await navigator.clipboard.writeText(fileQuery.data.content);
      setCopied(true);
      toast.success('Source code copied to clipboard.');
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast.error('Unable to copy to clipboard.');
    }
  };

  const toggleFolder = (path: string) => {
    setExpandedFolders((prev) => ({ ...prev, [path]: !prev[path] }));
  };

  const renderNodes = (nodes: RepositoryFileNode[], depth = 0) =>
    nodes.map((node) => {
      if (node.type === 'folder') {
        const isOpen = fileSearch.trim().length > 0 || Boolean(expandedFolders[node.path]);
        return (
          <div key={node.id}>
            <button
              type="button"
              onClick={() => toggleFolder(node.path)}
              style={{ paddingLeft: `${8 + depth * 12}px` }}
              className="flex w-full items-center gap-1.5 rounded-md py-1.5 pr-2 text-left text-xs font-medium text-foreground hover:bg-muted transition-colors"
            >
              {isOpen ? (
                <ChevronDown className="size-3.5 text-muted-foreground shrink-0" />
              ) : (
                <ChevronRight className="size-3.5 text-muted-foreground shrink-0" />
              )}
              {isOpen ? (
                <FolderOpen className="size-3.5 text-primary shrink-0" />
              ) : (
                <Folder className="size-3.5 text-primary shrink-0" />
              )}
              <span className="truncate">{node.name}</span>
            </button>
            {isOpen && node.children && renderNodes(node.children, depth + 1)}
          </div>
        );
      }

      const isSelected = activeFile === node.path;
      return (
        <button
          key={node.id}
          type="button"
          onClick={() => openFile(node.path)}
          style={{ paddingLeft: `${24 + depth * 12}px` }}
          className={cn(
            'flex w-full items-center gap-1.5 rounded-md py-1.5 pr-2 text-left text-xs transition-colors',
            isSelected
              ? 'bg-accent text-accent-foreground font-medium'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          )}
        >
          <FileCode className="size-3.5 shrink-0" />
          <span className="truncate font-mono">{node.name}</span>
        </button>
      );
    });

  if (treeQuery.isError) {
    return (
      <ErrorState
        message="Unable to load repository file tree."
        onRetry={() => treeQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-heading text-xl font-bold tracking-tight">
            Project Explorer
          </h1>
          <p className="text-xs text-muted-foreground">
            Browse repository files, inspect source code, and review grounded module
            explanations.
          </p>
        </div>

        {/* Mobile/Tablet Panel Switcher */}
        <div className="flex items-center gap-1 rounded-lg bg-muted p-1 lg:hidden">
          {(['files', 'code', 'ai'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setMobilePanel(tab)}
              className={cn(
                'flex-1 rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors',
                mobilePanel === tab
                  ? 'bg-card text-foreground shadow-xs'
                  : 'text-muted-foreground'
              )}
            >
              {tab === 'ai' ? 'Explanation' : tab}
            </button>
          ))}
        </div>
      </div>

      <SampleDataBanner />

      {/* Three-Panel Workspace */}
      <div className="grid grid-cols-1 overflow-hidden rounded-xl border border-border bg-card lg:h-[680px] lg:grid-cols-12">
        {/* Panel 1: File Explorer */}
        <section
          aria-label="File Explorer"
          className={cn(
            'flex flex-col border-b border-border lg:col-span-3 lg:border-b-0 lg:border-r',
            mobilePanel === 'files' ? 'flex h-[520px] lg:h-full' : 'hidden lg:flex'
          )}
        >
          <div className="border-b border-border p-2.5">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={fileSearch}
                onChange={(e) => setFileSearch(e.target.value)}
                placeholder="Filter files..."
                className="h-8 pl-8 text-xs"
              />
            </div>
          </div>
          <ScrollArea className="flex-1 p-2">
            {treeQuery.isLoading ? (
              <div className="space-y-2 p-2">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-5 w-4/5" />
              </div>
            ) : filteredTree.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-muted-foreground">
                No files match &ldquo;{fileSearch}&rdquo;.
              </p>
            ) : (
              <div className="space-y-0.5">{renderNodes(filteredTree)}</div>
            )}
          </ScrollArea>
        </section>

        {/* Panel 2: Code Viewer */}
        <section
          aria-label="Code Viewer"
          className={cn(
            'flex min-w-0 flex-col border-b border-border lg:col-span-6 lg:border-b-0 lg:border-r',
            mobilePanel === 'code' ? 'flex h-[560px] lg:h-full' : 'hidden lg:flex'
          )}
        >
          {/* Tabs Bar */}
          <div className="flex items-center justify-between gap-2 border-b border-border bg-muted/30 px-2 py-1.5">
            <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
              {openTabs.map((tabPath) => {
                const fileName = tabPath.split('/').pop() ?? tabPath;
                const active = tabPath === activeFile;
                return (
                  <div
                    key={tabPath}
                    onClick={() => openFile(tabPath)}
                    role="tab"
                    aria-selected={active}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') openFile(tabPath);
                    }}
                    className={cn(
                      'group flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-mono cursor-pointer whitespace-nowrap shrink-0',
                      active
                        ? 'border-border bg-card text-foreground font-medium'
                        : 'border-transparent text-muted-foreground hover:bg-muted'
                    )}
                  >
                    <span>{fileName}</span>
                    {openTabs.length > 1 && (
                      <button
                        type="button"
                        onClick={(e) => closeTab(tabPath, e)}
                        aria-label={`Close ${fileName}`}
                        className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                      >
                        <X className="size-3" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={handleCopyCode}
              disabled={!fileQuery.data}
              className="shrink-0"
            >
              {copied ? (
                <>
                  <Check className="mr-1 size-3.5 text-emerald-500" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="mr-1 size-3.5" />
                  Copy
                </>
              )}
            </Button>
          </div>

          {/* Symbols Strip */}
          {fileQuery.data && fileQuery.data.symbols.length > 0 && (
            <div className="flex items-center gap-1.5 overflow-x-auto border-b border-border px-3 py-1.5 text-xs">
              <span className="text-[11px] font-medium text-muted-foreground shrink-0">
                Symbols:
              </span>
              {fileQuery.data.symbols.map((sym) => (
                <button
                  key={sym.id}
                  type="button"
                  onClick={() => {
                    setSelectedSymbol(sym);
                    jumpToLine(sym.startLine);
                  }}
                  className={cn(
                    'rounded px-2 py-0.5 font-mono text-[11px] transition-colors whitespace-nowrap shrink-0',
                    selectedSymbol?.id === sym.id
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground hover:bg-accent'
                  )}
                >
                  {sym.name} (L{sym.startLine})
                </button>
              ))}
            </div>
          )}

          {/* Monaco Code Editor */}
          <div className="relative flex-1 min-h-0">
            {fileQuery.isLoading ? (
              <div className="p-4 space-y-2">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            ) : fileQuery.isError ? (
              <div className="p-6">
                <ErrorState
                  message="Could not load file contents."
                  onRetry={() => fileQuery.refetch()}
                />
              </div>
            ) : (
              <Editor
                height="100%"
                language={fileQuery.data?.language ?? 'typescript'}
                value={fileQuery.data?.content ?? ''}
                theme={theme === 'dark' ? 'vs-dark' : 'vs'}
                onMount={(editor) => {
                  editorRef.current = editor;
                }}
                options={{
                  readOnly: true,
                  minimap: { enabled: false },
                  fontSize: 13,
                  fontFamily: 'JetBrains Mono, monospace',
                  lineNumbers: 'on',
                  scrollBeyondLastLine: false,
                  padding: { top: 12, bottom: 12 },
                  automaticLayout: true,
                }}
              />
            )}
          </div>
        </section>

        {/* Panel 3: AI Explanation */}
        <section
          aria-label="AI Explanation"
          className={cn(
            'flex flex-col lg:col-span-3',
            mobilePanel === 'ai' ? 'flex h-[520px] lg:h-full' : 'hidden lg:flex'
          )}
        >
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <div className="flex items-center gap-1.5">
              <Sparkles className="size-3.5 text-primary" />
              <h2 className="text-xs font-semibold text-foreground">
                Code Intelligence (Sample)
              </h2>
            </div>
            {fileQuery.data && (
              <ConfidenceBadge confidence={fileQuery.data.confidence} />
            )}
          </div>

          <ScrollArea className="flex-1 p-4">
            {fileQuery.isLoading || !fileQuery.data ? (
              <div className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : (
              <div className="space-y-5 text-xs">
                <div className="space-y-1.5">
                  <p className="font-mono text-[11px] text-muted-foreground break-all">
                    {fileQuery.data.path}
                  </p>
                  <p className="leading-relaxed text-foreground">
                    {fileQuery.data.explanation}
                  </p>
                </div>

                {selectedSymbol && (
                  <div className="rounded-lg border border-primary/30 bg-accent/40 p-3 space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono font-semibold text-foreground">
                        {selectedSymbol.name}
                      </span>
                      <ConfidenceBadge confidence={selectedSymbol.confidence} />
                    </div>
                    <p className="text-[11px] text-muted-foreground capitalize">
                      {selectedSymbol.kind} · Lines {selectedSymbol.startLine}–
                      {selectedSymbol.endLine}
                    </p>
                    <p className="leading-relaxed text-foreground">
                      {selectedSymbol.summary}
                    </p>
                  </div>
                )}

                {fileQuery.data.sourceReferences.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="font-semibold text-foreground">
                      Source References
                    </h3>
                    <div className="space-y-1">
                      {fileQuery.data.sourceReferences.map((ref) => (
                        <button
                          key={`${ref.label}-${ref.line}`}
                          type="button"
                          onClick={() => {
                            jumpToLine(ref.line);
                            setMobilePanel('code');
                          }}
                          className="flex w-full items-center justify-between rounded-md border border-border px-2.5 py-1.5 text-left hover:bg-muted transition-colors"
                        >
                          <span className="text-foreground truncate">
                            {ref.label}
                          </span>
                          <span className="font-mono text-[11px] text-primary shrink-0 ml-2">
                            L{ref.line}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <h3 className="font-semibold text-foreground">Related Files</h3>
                  <div className="space-y-1">
                    {fileQuery.data.relatedFiles.map((relPath) => (
                      <button
                        key={relPath}
                        type="button"
                        onClick={() => openFile(relPath)}
                        className="block w-full truncate rounded-md border border-border px-2.5 py-1.5 text-left font-mono text-[11px] text-primary hover:bg-muted transition-colors"
                      >
                        {relPath}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <h3 className="font-semibold text-foreground">
                    Detected Imports
                  </h3>
                  <ul className="space-y-1 font-mono text-[11px] text-muted-foreground">
                    {fileQuery.data.dependencies.map((dep) => (
                      <li key={dep} className="truncate">
                        · {dep}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </ScrollArea>
        </section>
      </div>
    </div>
  );
}
