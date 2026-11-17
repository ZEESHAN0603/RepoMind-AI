import {
  Background,
  type Edge,
  Handle,
  MarkerType,
  MiniMap,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertOctagon,
  AlertTriangle,
  Box,
  Boxes,
  CheckCircle2,
  ExternalLink,
  FileCode2,
  Focus,
  Maximize2,
  Package,
  RefreshCw,
  RotateCcw,
  Search,
  Server,
  Share2,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ConfidenceBadge } from '@/components/common/ConfidenceBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { PageFadeIn } from '@/components/common/MotionPrimitives';
import { SampleDataBanner } from '@/components/common/SampleDataBanner';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { getRepositoryRoute } from '@/constants/routes';
import { cn } from '@/lib/utils';
import { dependencyService, repositoryService } from '@/services';
import { useThemeStore } from '@/stores/theme.store';
import type {
  CycleSeverity,
  DependencyCategory,
  DependencyModuleNode,
  DependencyNodeType,
} from '@/types';
import { formatRelativeTime } from '@/utils/formatters';

type DepNodeData = DependencyModuleNode & {
  inCycle?: boolean;
  isSelectedCycle?: boolean;
  isDirectDep?: boolean;
  isDependent?: boolean;
  isDimmed?: boolean;
};

type DepRFNode = Node<Record<string, unknown> & DepNodeData, 'depNode'>;

const NODE_TYPE_ICON: Record<DependencyNodeType, typeof Box> = {
  module: Boxes,
  file: FileCode2,
  package: Package,
  service: Server,
};

const SEVERITY_BADGE: Record<
  CycleSeverity,
  { label: string; classes: string }
> = {
  high: {
    label: 'High Severity',
    classes:
      'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/30',
  },
  medium: {
    label: 'Medium Severity',
    classes:
      'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30',
  },
  low: {
    label: 'Low Severity',
    classes: 'bg-muted text-muted-foreground border-border',
  },
};

function DependencyModuleCard({ data, selected }: NodeProps<DepRFNode>) {
  const Icon = NODE_TYPE_ICON[data.nodeType];

  return (
    <div
      className={cn(
        'w-56 rounded-lg border bg-card px-3 py-2.5 text-card-foreground shadow-xs transition-all',
        data.category === 'external' ? 'border-dashed border-slate-500/50' : 'border-border',
        data.isSelectedCycle && 'border-red-500 ring-2 ring-red-500/60 bg-red-500/5',
        !data.isSelectedCycle && data.inCycle && 'border-red-500/50',
        selected && !data.isSelectedCycle && 'ring-2 ring-primary',
        !selected && data.isDirectDep && 'ring-1 ring-indigo-500/70',
        !selected && data.isDependent && 'ring-1 ring-sky-500/70',
        data.isDimmed && 'opacity-30'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!size-2 !bg-primary !border-background"
      />
      <div className="flex items-center justify-between gap-2 pb-1">
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          <Icon className="size-3 text-primary" />
          {data.nodeType}
        </span>
        <span className="text-[10px] font-mono text-muted-foreground">
          {data.language}
        </span>
      </div>
      <p className="font-mono text-xs font-semibold text-foreground truncate">
        {data.label}
      </p>
      <p className="mt-0.5 font-mono text-[10px] text-muted-foreground truncate">
        {data.filePath}
      </p>
      <Handle
        type="source"
        position={Position.Right}
        className="!size-2 !bg-primary !border-background"
      />
    </div>
  );
}

const nodeTypes = {
  depNode: DependencyModuleCard,
};

function DependenciesWorkspace() {
  const { id = 'repo-cloud-gateway' } = useParams<{ id: string }>();
  const theme = useThemeStore((state) => state.theme);
  const queryClient = useQueryClient();
  const { zoomIn, zoomOut, fitView, setCenter } = useReactFlow();

  const [categoryFilter, setCategoryFilter] = useState<'all' | DependencyCategory>('all');
  const [languageFilter, setLanguageFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null);

  const repoQuery = useQuery({
    queryKey: ['repository', id],
    queryFn: () => repositoryService.getRepository(id),
  });

  const depQuery = useQuery({
    queryKey: ['dependency-analysis', id],
    queryFn: () => dependencyService.getDependencyAnalysis(id),
  });

  const refreshMutation = useMutation({
    mutationFn: () => dependencyService.refreshDependencyAnalysis(id),
    onSuccess: (updated) => {
      queryClient.setQueryData(['dependency-analysis', id], updated);
      toast.success('Sample dependency analysis refreshed.');
    },
    onError: () => {
      toast.error('Failed to refresh dependency analysis.');
    },
  });

  const data = depQuery.data;

  const availableLanguages = useMemo(() => {
    const set = new Set<string>();
    data?.nodes.forEach((n) => set.add(n.language));
    return Array.from(set);
  }, [data]);

  const selectedCycle = useMemo(
    () => data?.cycles.find((c) => c.id === selectedCycleId) ?? null,
    [data, selectedCycleId]
  );

  const selectedCycleNodeSet = useMemo(() => {
    if (!selectedCycle) return new Set<string>();
    return new Set(selectedCycle.cyclePath);
  }, [selectedCycle]);

  const allCycleNodeSet = useMemo(() => {
    const set = new Set<string>();
    data?.cycles.forEach((c) => c.cyclePath.forEach((m) => set.add(m)));
    return set;
  }, [data]);

  const filteredRelationships = useMemo(() => {
    const items = data?.relationships ?? [];
    const q = search.trim().toLowerCase();
    return items.filter((rel) => {
      if (categoryFilter !== 'all' && rel.category !== categoryFilter) {
        return false;
      }
      if (languageFilter !== 'all' && rel.language !== languageFilter) {
        return false;
      }
      if (q) {
        return (
          rel.sourceModule.toLowerCase().includes(q) ||
          rel.targetModule.toLowerCase().includes(q) ||
          rel.importSpecifiers.some((s) => s.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [data, categoryFilter, languageFilter, search]);

  const computedGraph = useMemo(() => {
    if (!data) return { nodes: [] as DepRFNode[], edges: [] as Edge[] };

    const activeModuleNames = new Set(
      filteredRelationships.flatMap((r) => [r.sourceModule, r.targetModule, r.sourcePath, r.targetPath].filter(Boolean))
    );

    const visibleModuleNodes = data.nodes.filter((n) => {
      if (languageFilter !== 'all' && n.language !== languageFilter) {
        return activeModuleNames.has(n.id);
      }
      if (search.trim() || categoryFilter !== 'all') {
        return activeModuleNames.has(n.id);
      }
      return true;
    });

    const directDeps = new Set<string>();
    const dependents = new Set<string>();
    if (selectedNodeId) {
      for (const rel of filteredRelationships) {
        if (rel.sourceModule === selectedNodeId || rel.sourcePath === selectedNodeId) {
          directDeps.add(rel.targetModule);
          if (rel.targetPath) directDeps.add(rel.targetPath);
        }
        if (rel.targetModule === selectedNodeId || rel.targetPath === selectedNodeId) {
          dependents.add(rel.sourceModule);
          if (rel.sourcePath) dependents.add(rel.sourcePath);
        }
      }
    }

    const rfNodes: DepRFNode[] = visibleModuleNodes.map((node) => {
      const isSelected = node.id === selectedNodeId;
      const isDirectDep = directDeps.has(node.id);
      const isDependent = dependents.has(node.id);
      const isSelectedCycle = selectedCycleNodeSet.has(node.id);

      let isDimmed = false;
      if (selectedCycle) {
        isDimmed = !isSelectedCycle;
      } else if (selectedNodeId) {
        isDimmed = !isSelected && !isDirectDep && !isDependent;
      }

      return {
        id: node.id,
        type: 'depNode',
        position: node.position,
        selected: isSelected,
        data: {
          ...node,
          inCycle: allCycleNodeSet.has(node.id),
          isSelectedCycle,
          isDirectDep,
          isDependent,
          isDimmed,
        },
      };
    });

    const visibleIds = new Set(rfNodes.map((n) => n.id));

    const rfEdges: Edge[] = filteredRelationships
      .filter((rel) => {
        const src = visibleIds.has(rel.sourceModule) ? rel.sourceModule : (visibleIds.has(rel.sourcePath) ? rel.sourcePath : null);
        const tgt = visibleIds.has(rel.targetModule) ? rel.targetModule : (visibleIds.has(rel.targetPath) ? rel.targetPath : null);
        return Boolean(src && tgt);
      })
      .map((rel) => {
        const src = (visibleIds.has(rel.sourceModule) ? rel.sourceModule : rel.sourcePath) as string;
        const tgt = (visibleIds.has(rel.targetModule) ? rel.targetModule : rel.targetPath) as string;
        const isCycleRel = rel.category === 'circular';
        const isPartOfSelectedCycle =
          selectedCycle !== null &&
          (selectedCycleNodeSet.has(src) || selectedCycleNodeSet.has(rel.sourceModule)) &&
          (selectedCycleNodeSet.has(tgt) || selectedCycleNodeSet.has(rel.targetModule)) &&
          isCycleRel;

        const isNodeConnected =
          selectedNodeId !== null &&
          (src === selectedNodeId || tgt === selectedNodeId || rel.sourceModule === selectedNodeId || rel.targetModule === selectedNodeId);

        let isDimmed = false;
        if (selectedCycle) {
          isDimmed = !isPartOfSelectedCycle;
        } else if (selectedNodeId) {
          isDimmed = !isNodeConnected;
        }

        const strokeColor =
          isCycleRel || isPartOfSelectedCycle
            ? '#ef4444'
            : tgt === selectedNodeId || rel.targetModule === selectedNodeId
              ? '#0ea5e9'
              : '#6366f1';

        return {
          id: rel.id,
          source: src,
          target: tgt,
          label: rel.importSpecifiers[0] ?? rel.category,
          animated: isPartOfSelectedCycle || isCycleRel || isNodeConnected,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 15,
            height: 15,
            color: strokeColor,
          },
          style: {
            stroke: strokeColor,
            strokeWidth: isPartOfSelectedCycle ? 2.8 : isCycleRel || isNodeConnected ? 2.1 : 1.4,
            strokeDasharray: rel.category === 'external' ? '4 4' : undefined,
            opacity: isDimmed ? 0.16 : 1,
          },
          labelStyle: {
            fontSize: 10,
            fontFamily: 'JetBrains Mono, monospace',
            fill: theme === 'dark' ? '#cbd5e1' : '#334155',
          },
          labelBgStyle: {
            fill: theme === 'dark' ? '#121620' : '#ffffff',
            fillOpacity: 0.92,
          },
        };
      });

    return { nodes: rfNodes, edges: rfEdges };
  }, [
    data,
    filteredRelationships,
    languageFilter,
    search,
    categoryFilter,
    selectedNodeId,
    selectedCycle,
    selectedCycleNodeSet,
    allCycleNodeSet,
    theme,
  ]);

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<DepRFNode>([]);
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    setRfNodes((prev) => {
      const posMap = new Map(prev.map((n) => [n.id, n.position]));
      return computedGraph.nodes.map((node) => ({
        ...node,
        position: posMap.get(node.id) ?? node.position,
      }));
    });
    setRfEdges(computedGraph.edges);
  }, [computedGraph, setRfNodes, setRfEdges]);

  const handleFocusNode = useCallback(
    (nodeId: string) => {
      const target =
        rfNodes.find((n) => n.id === nodeId) ??
        data?.nodes.find((n) => n.id === nodeId);
      if (!target) return;
      setSelectedCycleId(null);
      setSelectedNodeId(nodeId);
      setCenter(target.position.x + 112, target.position.y + 38, {
        zoom: 1.05,
        duration: 280,
      });
    },
    [rfNodes, data, setCenter]
  );

  const handleSelectCycle = useCallback(
    (cycleId: string) => {
      if (selectedCycleId === cycleId) {
        setSelectedCycleId(null);
        return;
      }
      setCategoryFilter('all');
      setLanguageFilter('all');
      setSearch('');
      setSelectedNodeId(null);
      setSelectedCycleId(cycleId);
      const cycle = data?.cycles.find((c) => c.id === cycleId);
      const firstNode = data?.nodes.find((n) => n.id === cycle?.cyclePath[0]);
      if (firstNode) {
        setTimeout(() => {
          setCenter(firstNode.position.x + 140, firstNode.position.y + 40, {
            zoom: 0.95,
            duration: 300,
          });
        }, 60);
      }
    },
    [selectedCycleId, data, setCenter]
  );

  const selectedNodeInfo = useMemo(() => {
    if (!selectedNodeId || !data) return null;
    const node = data.nodes.find((n) => n.id === selectedNodeId);
    if (!node) return null;
    const outgoing = data.relationships.filter((r) => r.sourceModule === selectedNodeId);
    const incoming = data.relationships.filter((r) => r.targetModule === selectedNodeId);
    return { node, outgoing, incoming };
  }, [selectedNodeId, data]);

  const selectedCycleRelationships = useMemo(() => {
    if (!selectedCycle || !data) return [];
    return data.relationships.filter(
      (r) =>
        r.category === 'circular' &&
        selectedCycleNodeSet.has(r.sourceModule) &&
        selectedCycleNodeSet.has(r.targetModule)
    );
  }, [selectedCycle, data, selectedCycleNodeSet]);

  if (depQuery.isError) {
    return (
      <ErrorState
        message="Unable to load dependency analysis."
        onRetry={() => depQuery.refetch()}
      />
    );
  }

  return (
    <PageFadeIn className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono font-medium text-primary">
              {repoQuery.data
                ? `${repoQuery.data.owner}/${repoQuery.data.name}`
                : id}
            </span>
            <span>·</span>
            <span>
              Last analyzed:{' '}
              {data ? formatRelativeTime(data.lastAnalyzed) : 'Loading...'}
            </span>
          </div>
          <h1 className="font-heading text-2xl font-bold tracking-tight mt-0.5">
            Dependency Analysis
          </h1>
          <p className="text-sm text-muted-foreground">
            Inspect internal/external module imports, explore dependency paths, and
            isolate circular import cycles.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending || depQuery.isLoading}
          className="w-fit whitespace-nowrap shrink-0"
        >
          <RefreshCw
            className={cn(
              'mr-1.5 size-3.5',
              refreshMutation.isPending && 'animate-spin'
            )}
          />
          {refreshMutation.isPending ? 'Refreshing...' : 'Refresh Analysis'}
        </Button>
      </div>

      <SampleDataBanner message="Sample Dependency Report — Circular dependencies, import edges, and refactoring suggestions shown below are Phase 1 sample records rather than real static analysis findings." />

      {/* 5 Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <Card>
          <CardHeader className="pb-1.5">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Total Modules
            </CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-2xl font-bold tabular-nums">
            {depQuery.isLoading ? '—' : data?.totalModules}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-1.5">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Total Dependencies
            </CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-2xl font-bold tabular-nums">
            {depQuery.isLoading ? '—' : data?.totalImports}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-1.5">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Internal Dependencies
            </CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-2xl font-bold tabular-nums">
            {depQuery.isLoading ? '—' : data?.internalCount}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-1.5">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              External Dependencies
            </CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-2xl font-bold tabular-nums">
            {depQuery.isLoading ? '—' : data?.externalCount}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-1.5">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Circular Dependencies
            </CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-2xl font-bold text-destructive tabular-nums">
            {depQuery.isLoading ? '—' : data?.circularCount}
          </CardContent>
        </Card>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search modules or symbols..."
              className="pl-8 h-8 text-xs"
            />
          </div>

          <Select value={languageFilter} onValueChange={setLanguageFilter}>
            <SelectTrigger aria-label="Filter by language" className="h-8 w-40 text-xs">
              <SelectValue placeholder="All Languages" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all" className="text-xs">
                All Languages
              </SelectItem>
              {availableLanguages.map((lang) => (
                <SelectItem key={lang} value={lang} className="text-xs">
                  {lang}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-wrap items-center gap-1 rounded-lg bg-muted p-1">
          {(['all', 'internal', 'external', 'circular'] as const).map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setCategoryFilter(cat)}
              className={cn(
                'rounded-md px-3 py-1 text-xs font-medium capitalize transition-colors whitespace-nowrap',
                categoryFilter === cat
                  ? 'bg-card text-foreground shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {cat === 'all' ? 'All Imports' : cat}
            </button>
          ))}
        </div>
      </div>

      {/* Interactive Dependency Graph + Inspector */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card
          className={cn(
            'overflow-hidden py-0 flex flex-col h-[480px]',
            selectedNodeInfo || selectedCycle ? 'lg:col-span-8' : 'lg:col-span-12'
          )}
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5 shrink-0">
            <div>
              <p className="text-sm font-semibold text-foreground">
                Interactive Dependency Graph
              </p>
              <p className="text-xs text-muted-foreground">
                Click any module node to highlight incoming & outgoing dependencies,
                or select a cycle below to isolate red edges
              </p>
            </div>
            <div className="flex items-center gap-1">
              {selectedNodeId && (
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  onClick={() => handleFocusNode(selectedNodeId)}
                >
                  <Focus className="mr-1 size-3" />
                  Focus
                </Button>
              )}
              <Button
                type="button"
                variant="outline"
                size="icon-xs"
                onClick={() => zoomIn({ duration: 200 })}
                aria-label="Zoom in"
              >
                <ZoomIn className="size-3.5" />
              </Button>
              <Button
                type="button"
                variant="outline"
                size="icon-xs"
                onClick={() => zoomOut({ duration: 200 })}
                aria-label="Zoom out"
              >
                <ZoomOut className="size-3.5" />
              </Button>
              <Button
                type="button"
                variant="outline"
                size="icon-xs"
                onClick={() => fitView({ duration: 250, padding: 0.16 })}
                aria-label="Fit graph to view"
              >
                <Maximize2 className="size-3.5" />
              </Button>
              <Button
                type="button"
                variant="outline"
                size="xs"
                onClick={() => {
                  setSelectedNodeId(null);
                  setSelectedCycleId(null);
                  setRfNodes(computedGraph.nodes);
                  setTimeout(() => fitView({ duration: 250, padding: 0.16 }), 40);
                }}
              >
                <RotateCcw className="mr-1 size-3" />
                Reset
              </Button>
            </div>
          </div>

          <div className="relative flex-1 bg-background/50">
            {depQuery.isLoading ? (
              <div className="p-6">
                <Skeleton className="h-[390px] w-full" />
              </div>
            ) : rfNodes.length === 0 ? (
              <div className="p-8">
                <EmptyState
                  icon={<Share2 className="size-5" />}
                  title="No matching dependency modules"
                  description="Adjust your search, language, or category filter to view modules."
                  actionLabel="Reset Filters"
                  onAction={() => {
                    setSearch('');
                    setCategoryFilter('all');
                    setLanguageFilter('all');
                  }}
                />
              </div>
            ) : (
              <ReactFlow
                nodes={rfNodes}
                edges={rfEdges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                colorMode={theme}
                fitView
                onNodeClick={(_e, node) => {
                  setSelectedCycleId(null);
                  setSelectedNodeId(node.id);
                }}
                onPaneClick={() => {
                  setSelectedNodeId(null);
                  setSelectedCycleId(null);
                }}
              >
                <Background gap={16} size={1} />
                <MiniMap pannable zoomable />
              </ReactFlow>
            )}
          </div>
        </Card>

        {/* Right Side Details Panel: Node Inspector OR Selected Cycle Details */}
        {selectedCycle ? (
          <Card className="lg:col-span-4 h-[480px] flex flex-col py-0 overflow-hidden border-red-500/40">
            <CardHeader className="border-b border-border px-4 py-3 shrink-0 bg-red-500/5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-[11px] font-mono font-semibold text-destructive uppercase">
                    Cycle Details · {selectedCycle.id}
                  </span>
                  <CardTitle className="text-sm font-bold mt-0.5">
                    {selectedCycle.affectedCount} Modules in Cycle
                  </CardTitle>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => setSelectedCycleId(null)}
                  aria-label="Close cycle details"
                >
                  <X className="size-4" />
                </Button>
              </div>
            </CardHeader>

            <CardContent className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
              <div>
                <p className="font-semibold text-foreground mb-1">
                  Complete Cycle Path
                </p>
                <div className="rounded-md border border-red-500/30 bg-red-500/5 px-2.5 py-2 font-mono text-[11px] text-foreground break-words">
                  {selectedCycle.cyclePath.join(' → ')}
                </div>
              </div>

              <div>
                <p className="font-semibold text-foreground mb-1">
                  Dependency Relationships
                </p>
                <div className="space-y-1.5">
                  {selectedCycleRelationships.map((rel) => (
                    <div
                      key={rel.id}
                      className="rounded border border-border bg-muted/40 px-2.5 py-1.5 font-mono text-[11px]"
                    >
                      <span className="text-foreground">{rel.sourceModule}</span>{' '}
                      <span className="text-destructive">→</span>{' '}
                      <span className="text-foreground">{rel.targetModule}</span>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        imports: {rel.importSpecifiers.join(', ')}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <p className="font-semibold text-foreground mb-1">
                  Potential Impact
                </p>
                <p className="text-muted-foreground leading-relaxed">
                  {selectedCycle.impact}
                </p>
              </div>

              <div>
                <p className="font-semibold text-foreground mb-1">
                  Suggested Refactoring Direction
                </p>
                <p className="rounded-md border border-border bg-muted/40 p-2.5 text-foreground leading-relaxed">
                  {selectedCycle.recommendation}
                </p>
              </div>

              <div>
                <p className="font-semibold text-foreground mb-1.5">
                  Files Involved
                </p>
                <div className="flex flex-col gap-1.5">
                  {selectedCycle.filePaths.map((fp) => (
                    <Button
                      key={fp}
                      asChild
                      variant="outline"
                      size="xs"
                      className="justify-between font-mono"
                    >
                      <Link
                        to={`${getRepositoryRoute(id, 'explorer')}?file=${encodeURIComponent(fp)}`}
                      >
                        <span className="truncate">{fp}</span>
                        <ExternalLink className="ml-1.5 size-3 shrink-0" />
                      </Link>
                    </Button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          selectedNodeInfo && (
            <Card className="lg:col-span-4 h-[480px] flex flex-col py-0 overflow-hidden">
              <CardHeader className="border-b border-border px-4 py-3 shrink-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {selectedNodeInfo.node.nodeType} · {selectedNodeInfo.node.language}
                    </span>
                    <CardTitle className="font-mono text-sm font-bold truncate mt-0.5">
                      {selectedNodeInfo.node.label}
                    </CardTitle>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => setSelectedNodeId(null)}
                    aria-label="Close module details"
                  >
                    <X className="size-4" />
                  </Button>
                </div>
              </CardHeader>

              <CardContent className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
                <div>
                  <p className="font-semibold text-foreground mb-1">Source Path</p>
                  <p className="rounded border border-border bg-muted/40 px-2.5 py-1.5 font-mono text-[11px] break-all">
                    {selectedNodeInfo.node.filePath}
                  </p>
                </div>

                <div>
                  <p className="font-semibold text-foreground mb-1.5">
                    Outgoing Dependencies ({selectedNodeInfo.outgoing.length})
                  </p>
                  {selectedNodeInfo.outgoing.length === 0 ? (
                    <p className="text-muted-foreground">No outgoing imports.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {selectedNodeInfo.outgoing.map((rel) => (
                        <button
                          key={rel.id}
                          type="button"
                          onClick={() => handleFocusNode(rel.targetModule)}
                          className="flex w-full items-center justify-between rounded border border-border bg-background px-2.5 py-1.5 text-left hover:border-primary/50"
                        >
                          <span className="font-mono text-[11px] font-medium truncate">
                            → {rel.targetModule}
                          </span>
                          <span className="text-[10px] font-mono text-muted-foreground ml-2 shrink-0">
                            {rel.importSpecifiers[0]}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <p className="font-semibold text-foreground mb-1.5">
                    Incoming Dependents ({selectedNodeInfo.incoming.length})
                  </p>
                  {selectedNodeInfo.incoming.length === 0 ? (
                    <p className="text-muted-foreground">No incoming dependents.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {selectedNodeInfo.incoming.map((rel) => (
                        <button
                          key={rel.id}
                          type="button"
                          onClick={() => handleFocusNode(rel.sourceModule)}
                          className="flex w-full items-center justify-between rounded border border-border bg-background px-2.5 py-1.5 text-left hover:border-primary/50"
                        >
                          <span className="font-mono text-[11px] font-medium truncate">
                            ← {rel.sourceModule}
                          </span>
                          <span className="text-[10px] font-mono text-muted-foreground ml-2 shrink-0">
                            {rel.importSpecifiers[0]}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {selectedNodeInfo.node.category === 'internal' && (
                  <Button asChild size="sm" className="w-full">
                    <Link
                      to={`${getRepositoryRoute(id, 'explorer')}?file=${encodeURIComponent(selectedNodeInfo.node.filePath)}`}
                    >
                      Open Source File
                      <ExternalLink className="ml-1.5 size-3.5" />
                    </Link>
                  </Button>
                )}
              </CardContent>
            </Card>
          )
        )}
      </div>

      {/* Circular Dependency Detection Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertTriangle className="size-4 text-destructive" />
            Circular Dependency Detection (Sample Records)
          </CardTitle>
          <CardDescription>
            Click any cycle card below to highlight its nodes and edges in red on the
            dependency graph and inspect refactoring guidance.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {depQuery.isLoading ? (
            <Skeleton className="h-36 w-full lg:col-span-2" />
          ) : (
            data?.cycles.map((cycle) => {
              const sev = SEVERITY_BADGE[cycle.severity];
              const isSelected = selectedCycleId === cycle.id;
              return (
                <div
                  key={cycle.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSelectCycle(cycle.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSelectCycle(cycle.id);
                    }
                  }}
                  className={cn(
                    'rounded-lg border p-4 space-y-3 text-left transition-all cursor-pointer',
                    isSelected
                      ? 'border-red-500 bg-red-500/5 ring-1 ring-red-500/50'
                      : 'border-border bg-background hover:border-red-500/40'
                  )}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-foreground">
                        {cycle.id.toUpperCase()}
                      </span>
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
                          sev.classes
                        )}
                      >
                        <AlertOctagon className="size-3" />
                        {sev.label}
                      </span>
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {cycle.affectedCount} modules
                      </span>
                    </div>
                    <ConfidenceBadge confidence={cycle.confidence} />
                  </div>

                  <div className="rounded-md bg-muted/50 px-3 py-2 font-mono text-xs text-foreground overflow-x-auto whitespace-nowrap">
                    {cycle.cyclePath.join('  →  ')}
                  </div>

                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {cycle.description}
                  </p>

                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {cycle.filePaths.map((filePath) => (
                        <Button
                          key={filePath}
                          asChild
                          variant="outline"
                          size="xs"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Link
                            to={`${getRepositoryRoute(id, 'explorer')}?file=${encodeURIComponent(filePath)}`}
                            className="font-mono"
                          >
                            {filePath}
                            <ExternalLink className="ml-1 size-3" />
                          </Link>
                        </Button>
                      ))}
                    </div>
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-primary">
                      {isSelected ? (
                        <>
                          <CheckCircle2 className="size-3.5" />
                          Highlighted in graph
                        </>
                      ) : (
                        'Highlight in graph'
                      )}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      {/* Import Relationships Table */}
      {filteredRelationships.length > 0 && (
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle className="text-base">Import Relationships</CardTitle>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-y border-border bg-muted/40 text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5">Source Module</th>
                  <th className="px-4 py-2.5">Target Module</th>
                  <th className="px-4 py-2.5">Category</th>
                  <th className="px-4 py-2.5">Language</th>
                  <th className="px-4 py-2.5">Imported Symbols</th>
                  <th className="px-4 py-2.5">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredRelationships.map((rel) => (
                  <tr
                    key={rel.id}
                    className="hover:bg-muted/30 cursor-pointer"
                    onClick={() => handleFocusNode(rel.sourceModule)}
                  >
                    <td className="px-4 py-3 font-mono">
                      <Link
                        to={`${getRepositoryRoute(id, 'explorer')}?file=${encodeURIComponent(rel.sourcePath)}`}
                        onClick={(e) => e.stopPropagation()}
                        className="text-primary hover:underline"
                      >
                        {rel.sourceModule}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-foreground">
                      {rel.targetModule}
                    </td>
                    <td className="px-4 py-3 capitalize">
                      <span
                        className={cn(
                          'font-medium',
                          rel.category === 'circular'
                            ? 'text-destructive'
                            : 'text-muted-foreground'
                        )}
                      >
                        {rel.category}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {rel.language}
                    </td>
                    <td className="px-4 py-3 font-mono text-muted-foreground">
                      {rel.importSpecifiers.join(', ')}
                    </td>
                    <td className="px-4 py-3">
                      <ConfidenceBadge confidence={rel.confidence} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </PageFadeIn>
  );
}

export function DependenciesPage() {
  return (
    <ReactFlowProvider>
      <DependenciesWorkspace />
    </ReactFlowProvider>
  );
}
