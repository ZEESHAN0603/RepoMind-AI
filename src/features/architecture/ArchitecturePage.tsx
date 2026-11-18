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
import { useQuery } from '@tanstack/react-query';
import {
  Bot,
  Box,
  Cpu,
  Database,
  ExternalLink,
  Focus,
  Globe,
  Layers,
  Lock,
  Map as MapIcon,
  Maximize2,
  Minimize2,
  Monitor,
  Network,
  RotateCcw,
  Search,
  Server,
  ShieldCheck,
  Tag,
  Unlock,
  Wrench,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ConfidenceBadge } from '@/components/common/ConfidenceBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { PageFadeIn } from '@/components/common/MotionPrimitives';
import { Button } from '@/components/ui/button';
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
import { architectureService } from '@/services';
import { useThemeStore } from '@/stores/theme.store';
import type {
  ArchNodeCategory,
  ArchitectureNodeData,
  ArchitectureViewMode,
  GroundingConfidence,
} from '@/types';

type ArchRFNodeData = ArchitectureNodeData & {
  isConnected?: boolean;
  isDimmed?: boolean;
};

type CustomArchNode = Node<Record<string, unknown> & ArchRFNodeData, 'archNode'>;

const ALL_CATEGORIES: ArchNodeCategory[] = [
  'frontend',
  'backend',
  'api',
  'database',
  'authentication',
  'external',
  'internal',
  'utility',
  'ai',
  'worker',
];

const CATEGORY_META: Record<
  ArchNodeCategory,
  { label: string; border: string; badge: string; icon: typeof Box }
> = {
  frontend: {
    label: 'Frontend',
    border: 'border-sky-500/45',
    badge: 'text-sky-600 dark:text-sky-400',
    icon: Monitor,
  },
  backend: {
    label: 'Backend',
    border: 'border-indigo-500/45',
    badge: 'text-indigo-600 dark:text-indigo-400',
    icon: Server,
  },
  api: {
    label: 'API',
    border: 'border-violet-500/45',
    badge: 'text-violet-600 dark:text-violet-400',
    icon: Globe,
  },
  database: {
    label: 'Database',
    border: 'border-amber-500/45',
    badge: 'text-amber-600 dark:text-amber-400',
    icon: Database,
  },
  authentication: {
    label: 'Auth',
    border: 'border-emerald-500/45',
    badge: 'text-emerald-600 dark:text-emerald-400',
    icon: ShieldCheck,
  },
  external: {
    label: 'External',
    border: 'border-rose-500/45 border-dashed',
    badge: 'text-rose-600 dark:text-rose-400',
    icon: ExternalLink,
  },
  internal: {
    label: 'Internal',
    border: 'border-cyan-500/45',
    badge: 'text-cyan-600 dark:text-cyan-400',
    icon: Layers,
  },
  utility: {
    label: 'Utility',
    border: 'border-slate-500/45',
    badge: 'text-slate-600 dark:text-slate-400',
    icon: Wrench,
  },
  ai: {
    label: 'AI Service',
    border: 'border-fuchsia-500/45',
    badge: 'text-fuchsia-600 dark:text-fuchsia-400',
    icon: Bot,
  },
  worker: {
    label: 'Worker',
    border: 'border-orange-500/45',
    badge: 'text-orange-600 dark:text-orange-400',
    icon: Cpu,
  },
};

const VIEW_MODES: { id: ArchitectureViewMode; label: string }[] = [
  { id: 'system', label: 'System Overview' },
  { id: 'frontend', label: 'Frontend Architecture' },
  { id: 'backend', label: 'Backend Architecture' },
  { id: 'api', label: 'API Connections' },
  { id: 'database', label: 'Database Relationships' },
  { id: 'modules', label: 'Module Dependencies' },
];

function ArchNodeComponent({ data, selected }: NodeProps<CustomArchNode>) {
  const meta = CATEGORY_META[data.category] ?? CATEGORY_META.internal;
  const Icon = meta.icon;

  return (
    <div
      className={cn(
        'w-58 rounded-lg border bg-card px-3.5 py-2.5 text-card-foreground shadow-xs transition-all',
        meta.border,
        selected && 'ring-2 ring-primary shadow-md',
        !selected && data.isConnected && 'ring-1 ring-primary/60',
        data.isDimmed && 'opacity-30'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!size-2.5 !bg-primary !border-background"
      />
      <div className="flex items-center justify-between gap-2 pb-1">
        <span
          className={cn(
            'inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider',
            meta.badge
          )}
        >
          <Icon className="size-3" />
          {meta.label}
        </span>
        <ConfidenceBadge confidence={data.confidence} className="px-1.5 py-0 text-[10px]" />
      </div>
      <p className="text-xs font-semibold text-foreground truncate">{data.label}</p>
      <p className="mt-0.5 font-mono text-[10px] text-muted-foreground truncate">
        {data.filePath}
      </p>
      <p className="mt-1 text-[10px] text-muted-foreground truncate">
        Group: {data.group}
      </p>
      <Handle
        type="source"
        position={Position.Right}
        className="!size-2.5 !bg-primary !border-background"
      />
    </div>
  );
}

const nodeTypes = {
  archNode: ArchNodeComponent,
};

function ArchitectureWorkspace() {
  const { id = 'repo-cloud-gateway' } = useParams<{ id: string }>();
  const theme = useThemeStore((state) => state.theme);
  const { zoomIn, zoomOut, fitView, setCenter } = useReactFlow();

  const [viewMode, setViewMode] = useState<ArchitectureViewMode>('system');
  const [search, setSearch] = useState('');
  const [hiddenCategories, setHiddenCategories] = useState<Set<ArchNodeCategory>>(
    new Set()
  );
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [confidenceFilter, setConfidenceFilter] = useState<'all' | GroundingConfidence>(
    'all'
  );
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [dragLocked, setDragLocked] = useState(false);
  const [showMinimap, setShowMinimap] = useState(true);
  const [showEdgeLabels, setShowEdgeLabels] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const graphQuery = useQuery({
    queryKey: ['architecture-graph', id],
    queryFn: () => architectureService.getArchitectureGraph(id),
  });

  const activeViewPayload = useMemo(() => {
    const data = graphQuery.data;
    if (!data) return null;
    return data.views?.[viewMode] ?? {
      viewMode,
      title: 'System Overview',
      subtitle: '',
      nodes: data.nodes,
      edges: data.edges,
    };
  }, [graphQuery.data, viewMode]);

  const availableGroups = useMemo(() => {
    const set = new Set<string>();
    activeViewPayload?.nodes.forEach((n) => set.add(n.group));
    return Array.from(set);
  }, [activeViewPayload]);

  const presentCategories = useMemo(() => {
    const set = new Set<ArchNodeCategory>();
    activeViewPayload?.nodes.forEach((n) => set.add(n.category));
    return ALL_CATEGORIES.filter((c) => set.has(c));
  }, [activeViewPayload]);

  const filteredRawNodes = useMemo(() => {
    const raw = activeViewPayload?.nodes ?? [];
    const q = search.trim().toLowerCase();
    return raw.filter((n) => {
      if (hiddenCategories.has(n.category)) return false;
      if (collapsedGroups.has(n.group)) return false;
      if (
        q &&
        !n.label.toLowerCase().includes(q) &&
        !n.filePath.toLowerCase().includes(q) &&
        !n.group.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [activeViewPayload, hiddenCategories, collapsedGroups, search]);

  const visibleNodeIds = useMemo(
    () => new Set(filteredRawNodes.map((n) => n.id)),
    [filteredRawNodes]
  );

  const computedGraph = useMemo(() => {
    const rawEdges = (activeViewPayload?.edges ?? []).filter((e) => {
      if (!visibleNodeIds.has(e.source) || !visibleNodeIds.has(e.target)) {
        return false;
      }
      if (confidenceFilter !== 'all' && e.confidence !== confidenceFilter) {
        return false;
      }
      return true;
    });

    const connectedNodeIds = new Set<string>();
    if (selectedNodeId) {
      for (const e of rawEdges) {
        if (e.source === selectedNodeId) connectedNodeIds.add(e.target);
        if (e.target === selectedNodeId) connectedNodeIds.add(e.source);
      }
    }

    const nodes: CustomArchNode[] = filteredRawNodes.map((node) => {
      const isSelected = node.id === selectedNodeId;
      const isConnected = connectedNodeIds.has(node.id);
      const isDimmed =
        selectedNodeId !== null && !isSelected && !isConnected;

      return {
        id: node.id,
        type: 'archNode',
        position: node.position,
        selected: isSelected,
        data: {
          ...node,
          isConnected,
          isDimmed,
        },
      };
    });

    const edges: Edge[] = rawEdges.map((edge) => {
      const isConnected =
        selectedNodeId !== null &&
        (edge.source === selectedNodeId || edge.target === selectedNodeId);
      const isDimmed = selectedNodeId !== null && !isConnected;

      const color = isConnected
        ? '#6366f1'
        : edge.confidence === 'inferred'
          ? '#d97706'
          : '#64748b';

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: showEdgeLabels ? edge.label : undefined,
        animated: isConnected,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 16,
          height: 16,
          color,
        },
        style: {
          stroke: color,
          strokeWidth: isConnected ? 2.4 : 1.5,
          strokeDasharray: edge.confidence === 'inferred' ? '5 4' : undefined,
          opacity: isDimmed ? 0.22 : 1,
        },
        labelStyle: {
          fontSize: 10,
          fontFamily: 'JetBrains Mono, monospace',
          fill: theme === 'dark' ? '#cbd5e1' : '#334155',
        },
        labelBgStyle: {
          fill: theme === 'dark' ? '#121620' : '#ffffff',
          fillOpacity: 0.9,
        },
      };
    });

    return { nodes, edges };
  }, [
    activeViewPayload,
    filteredRawNodes,
    visibleNodeIds,
    confidenceFilter,
    selectedNodeId,
    showEdgeLabels,
    theme,
  ]);

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<CustomArchNode>([]);
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

  const handleViewChange = (nextView: ArchitectureViewMode) => {
    setViewMode(nextView);
    setSelectedNodeId(null);
    setCollapsedGroups(new Set());
    setHiddenCategories(new Set());
    setTimeout(() => fitView({ duration: 280, padding: 0.18 }), 80);
  };

  const handleResetLayout = useCallback(() => {
    setHiddenCategories(new Set());
    setCollapsedGroups(new Set());
    setConfidenceFilter('all');
    setSearch('');
    setSelectedNodeId(null);
    setRfNodes(
      (activeViewPayload?.nodes ?? []).map((node) => ({
        id: node.id,
        type: 'archNode',
        position: node.position,
        data: { ...node },
      }))
    );
    setTimeout(() => fitView({ duration: 280, padding: 0.16 }), 60);
  }, [activeViewPayload, setRfNodes, fitView]);

  const handleFocusNode = useCallback(
    (nodeId: string) => {
      const node =
        rfNodes.find((n) => n.id === nodeId) ??
        activeViewPayload?.nodes.find((n) => n.id === nodeId);
      if (!node) return;
      setSelectedNodeId(nodeId);
      setCenter(node.position.x + 115, node.position.y + 40, {
        zoom: 1.05,
        duration: 280,
      });
    },
    [rfNodes, activeViewPayload, setCenter]
  );

  const toggleCategory = (cat: ArchNodeCategory) => {
    setHiddenCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  const toggleGroupCollapse = (group: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  const selectedNode = useMemo(
    () => activeViewPayload?.nodes.find((n) => n.id === selectedNodeId) ?? null,
    [activeViewPayload, selectedNodeId]
  );

  const connectedEdges = useMemo(() => {
    if (!selectedNodeId || !activeViewPayload) {
      return { incoming: [], outgoing: [] };
    }
    return {
      incoming: activeViewPayload.edges.filter((e) => e.target === selectedNodeId),
      outgoing: activeViewPayload.edges.filter((e) => e.source === selectedNodeId),
    };
  }, [selectedNodeId, activeViewPayload]);

  if (graphQuery.isError) {
    return (
      <ErrorState
        message="Unable to load architecture graph."
        onRetry={() => graphQuery.refetch()}
      />
    );
  }

  return (
    <PageFadeIn className="space-y-4">
      {/* Header + 6 Visualization View Tabs */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">
            Architecture Graph
          </h1>
          <p className="text-sm text-muted-foreground">
            {activeViewPayload?.subtitle ||
              'Interactive module dependency and architectural layer visualization.'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-1 rounded-lg bg-muted p-1">
          {VIEW_MODES.map((mode) => (
            <button
              key={mode.id}
              type="button"
              onClick={() => handleViewChange(mode.id)}
              className={cn(
                'rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors whitespace-nowrap',
                viewMode === mode.id
                  ? 'bg-card text-foreground shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* Search, Confidence & Group Collapse Controls */}
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-3.5 surface-card">
        <div className="flex flex-col gap-2.5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search nodes, groups, or paths..."
                className="pl-8 h-8 text-xs"
              />
            </div>

            <Select
              value={confidenceFilter}
              onValueChange={(v) =>
                setConfidenceFilter(v as 'all' | GroundingConfidence)
              }
            >
              <SelectTrigger
                aria-label="Filter relationship confidence"
                className="h-8 w-44 text-xs"
              >
                <SelectValue placeholder="All relationships" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all" className="text-xs">
                  All Relationships
                </SelectItem>
                <SelectItem value="verified" className="text-xs">
                  Verified Static Only
                </SelectItem>
                <SelectItem value="inferred" className="text-xs">
                  Inferred Only
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Group Collapse / Expand Pills */}
          {availableGroups.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="text-muted-foreground font-medium mr-1">
                Groups:
              </span>
              {availableGroups.map((group) => {
                const collapsed = collapsedGroups.has(group);
                return (
                  <button
                    key={group}
                    type="button"
                    onClick={() => toggleGroupCollapse(group)}
                    className={cn(
                      'rounded-md border px-2 py-0.5 text-[11px] font-medium transition-colors',
                      collapsed
                        ? 'border-dashed border-border bg-muted/40 text-muted-foreground line-through'
                        : 'border-border bg-background text-foreground hover:border-primary/40'
                    )}
                    title={collapsed ? `Expand ${group}` : `Collapse ${group}`}
                  >
                    {group}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* 10 Category Hide / Show Filter Strip */}
        <div className="flex flex-wrap items-center gap-1.5 border-t border-border pt-2.5">
          <span className="text-xs font-medium text-muted-foreground mr-1">
            Categories:
          </span>
          {presentCategories.map((cat) => {
            const meta = CATEGORY_META[cat];
            const Icon = meta.icon;
            const hidden = hiddenCategories.has(cat);
            return (
              <button
                key={cat}
                type="button"
                onClick={() => toggleCategory(cat)}
                className={cn(
                  'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium transition-colors',
                  hidden
                    ? 'border-border bg-muted/40 text-muted-foreground opacity-55'
                    : 'border-border bg-background text-foreground hover:border-primary/40'
                )}
              >
                <Icon className={cn('size-3', !hidden && meta.badge)} />
                {meta.label}
              </button>
            );
          })}
          {hiddenCategories.size > 0 && (
            <button
              type="button"
              onClick={() => setHiddenCategories(new Set())}
              className="text-[11px] font-medium text-primary hover:underline ml-1"
            >
              Show all
            </button>
          )}
        </div>
      </div>

      {/* Graph Canvas + Node Details Side Panel */}
      <div
        className={cn(
          'grid grid-cols-1 gap-4 lg:grid-cols-12',
          isFullscreen &&
            'fixed inset-3 z-50 rounded-xl border border-border bg-background p-3 shadow-2xl'
        )}
      >
        <div
          className={cn(
            'relative overflow-hidden rounded-xl border border-border bg-card surface-card',
            isFullscreen ? 'h-full' : 'h-[580px]',
            selectedNode ? 'lg:col-span-8' : 'lg:col-span-12'
          )}
        >
          {/* Floating Control Toolbar */}
          <div className="absolute top-3 right-3 z-10 flex flex-wrap items-center gap-1 rounded-lg border border-border bg-card/95 p-1 shadow-sm backdrop-blur-xs">
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => zoomIn({ duration: 200 })}
              title="Zoom in"
              aria-label="Zoom in"
            >
              <ZoomIn className="size-3.5" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => zoomOut({ duration: 200 })}
              title="Zoom out"
              aria-label="Zoom out"
            >
              <ZoomOut className="size-3.5" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => fitView({ duration: 250, padding: 0.16 })}
              title="Fit view"
              aria-label="Fit view"
            >
              <Focus className="size-3.5" />
            </Button>
            <Button
              type="button"
              variant={dragLocked ? 'secondary' : 'ghost'}
              size="icon-xs"
              onClick={() => setDragLocked((prev) => !prev)}
              title={dragLocked ? 'Unlock node dragging' : 'Lock node dragging'}
              aria-label="Toggle node drag lock"
            >
              {dragLocked ? (
                <Lock className="size-3.5 text-primary" />
              ) : (
                <Unlock className="size-3.5" />
              )}
            </Button>
            <Button
              type="button"
              variant={showMinimap ? 'secondary' : 'ghost'}
              size="icon-xs"
              onClick={() => setShowMinimap((prev) => !prev)}
              title="Toggle minimap"
              aria-label="Toggle minimap"
            >
              <MapIcon className="size-3.5" />
            </Button>
            <Button
              type="button"
              variant={showEdgeLabels ? 'secondary' : 'ghost'}
              size="icon-xs"
              onClick={() => setShowEdgeLabels((prev) => !prev)}
              title="Toggle edge labels"
              aria-label="Toggle edge labels"
            >
              <Tag className="size-3.5" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={handleResetLayout}
              title="Reset layout and filters"
              aria-label="Reset layout"
            >
              <RotateCcw className="size-3.5" />
            </Button>
            {selectedNodeId && (
              <Button
                type="button"
                variant="ghost"
                size="xs"
                onClick={() => setSelectedNodeId(null)}
              >
                Clear
              </Button>
            )}
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => setIsFullscreen((prev) => !prev)}
              title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen graph'}
              aria-label="Toggle fullscreen"
            >
              {isFullscreen ? (
                <Minimize2 className="size-3.5" />
              ) : (
                <Maximize2 className="size-3.5" />
              )}
            </Button>
          </div>

          {graphQuery.isLoading ? (
            <div className="p-6">
              <Skeleton className="h-[520px] w-full" />
            </div>
          ) : rfNodes.length === 0 ? (
            <div className="p-10">
              <EmptyState
                icon={<Network className="size-5" />}
                title="No visible architecture nodes"
                description="All categories or groups are currently filtered out."
                actionLabel="Reset Filters"
                onAction={handleResetLayout}
              />
            </div>
          ) : (
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              nodeTypes={nodeTypes}
              nodesDraggable={!dragLocked}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              colorMode={theme}
              fitView
              onNodeClick={(_event, node) => setSelectedNodeId(node.id)}
              onPaneClick={() => setSelectedNodeId(null)}
            >
              <Background gap={18} size={1} />
              {showMinimap && <MiniMap pannable zoomable />}
            </ReactFlow>
          )}
        </div>

        {selectedNode && (
          <aside
            className={cn(
              'rounded-xl border border-border bg-card p-5 lg:col-span-4 space-y-4 overflow-y-auto surface-card',
              isFullscreen ? 'h-full' : 'max-h-[580px]'
            )}
          >
            <div className="flex items-start justify-between gap-2 border-b border-border pb-3">
              <div className="min-w-0">
                <span
                  className={cn(
                    'text-[11px] font-semibold uppercase tracking-wider',
                    CATEGORY_META[selectedNode.category]?.badge ??
                      'text-muted-foreground'
                  )}
                >
                  {CATEGORY_META[selectedNode.category]?.label ??
                    selectedNode.category}{' '}
                  · {selectedNode.group}
                </span>
                <h2 className="text-base font-bold text-foreground truncate mt-0.5">
                  {selectedNode.label}
                </h2>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => handleFocusNode(selectedNode.id)}
                  title="Center on node"
                  aria-label="Focus selected node"
                >
                  <Focus className="size-3.5" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => setSelectedNodeId(null)}
                  aria-label="Close node details"
                >
                  <X className="size-4" />
                </Button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Evidence</span>
              <ConfidenceBadge confidence={selectedNode.confidence} />
            </div>

            <p className="text-xs leading-relaxed text-foreground">
              {selectedNode.description}
            </p>

            <div className="space-y-1.5">
              <p className="text-xs font-semibold text-foreground">Source File</p>
              <p className="rounded-md border border-border bg-muted/40 px-2.5 py-1.5 font-mono text-[11px] text-foreground break-all">
                {selectedNode.filePath}
              </p>
            </div>

            {selectedNode.exports.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-foreground">
                  Exported Symbols / Endpoints
                </p>
                <ul className="space-y-1 font-mono text-[11px] text-muted-foreground">
                  {selectedNode.exports.map((exp) => (
                    <li key={exp}>· {exp}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="space-y-2 border-t border-border pt-3 text-xs">
              <p className="font-semibold text-foreground">
                Connections ({connectedEdges.incoming.length} in ·{' '}
                {connectedEdges.outgoing.length} out)
              </p>
              <div className="space-y-1">
                {connectedEdges.outgoing.map((edge) => (
                  <button
                    key={edge.id}
                    type="button"
                    onClick={() => handleFocusNode(edge.target)}
                    className="block w-full text-left rounded px-2 py-1 font-mono text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                  >
                    → {edge.target} ({edge.label})
                  </button>
                ))}
                {connectedEdges.incoming.map((edge) => (
                  <button
                    key={edge.id}
                    type="button"
                    onClick={() => handleFocusNode(edge.source)}
                    className="block w-full text-left rounded px-2 py-1 font-mono text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                  >
                    ← {edge.source} ({edge.label})
                  </button>
                ))}
              </div>
            </div>

            <Button asChild size="sm" className="w-full">
              <Link
                to={`${getRepositoryRoute(id, 'explorer')}?file=${encodeURIComponent(selectedNode.filePath)}`}
              >
                Open Source File
                <ExternalLink className="ml-1.5 size-3.5" />
              </Link>
            </Button>
          </aside>
        )}
      </div>
    </PageFadeIn>
  );
}

export function ArchitecturePage() {
  return (
    <ReactFlowProvider>
      <ArchitectureWorkspace />
    </ReactFlowProvider>
  );
}
