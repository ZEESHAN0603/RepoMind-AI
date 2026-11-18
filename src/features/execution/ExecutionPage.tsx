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
  Activity,
  AlertTriangle,
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  Brain,
  Check,
  ChevronDown,
  ChevronRight,
  Code2,
  Copy,
  Database,
  Expand,
  ExternalLink,
  FileCode2,
  FolderTree,
  Globe,
  History,
  Layers,
  ListOrdered,
  Loader2,
  Maximize2,
  Minimize2,
  Play,
  RotateCcw,
  Search,
  Shrink,
  Sparkles,
  Workflow,
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
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
import { executionService, repositoryService } from '@/services';
import { useThemeStore } from '@/stores/theme.store';
import type {
  ExecutionExplanationResponse,
  ExecutionFunctionSymbol,
  ExecutionGraphNode,
  ExecutionNodeType,
  ExecutionStatus,
} from '@/types';

type ExecRFNodeData = ExecutionGraphNode & {
  isHighlighted?: boolean;
  isIncoming?: boolean;
  isOutgoing?: boolean;
  isDimmed?: boolean;
  hasHiddenCallees?: boolean;
  hasHiddenCallers?: boolean;
};

type ExecRFNode = Node<Record<string, unknown> & ExecRFNodeData, 'execNode'>;

const NODE_TYPE_META: Record<
  ExecutionNodeType,
  { label: string; icon: typeof Code2; accent: string }
> = {
  function: {
    label: 'Function',
    icon: Code2,
    accent: 'border-indigo-500/40',
  },
  api: {
    label: 'API Endpoint',
    icon: Globe,
    accent: 'border-violet-500/45',
  },
  method: {
    label: 'Class Method',
    icon: Layers,
    accent: 'border-sky-500/45',
  },
  database: {
    label: 'Database Op',
    icon: Database,
    accent: 'border-amber-500/45',
  },
  external: {
    label: 'External Call',
    icon: ExternalLink,
    accent: 'border-rose-500/45',
  },
};

const STATUS_DOT: Record<ExecutionStatus, string> = {
  verified: 'bg-emerald-500',
  inferred: 'bg-amber-500',
  unresolved: 'bg-slate-400',
};

function ExecutionNodeCard({ data, selected }: NodeProps<ExecRFNode>) {
  const meta = NODE_TYPE_META[data.nodeType];
  const Icon = meta.icon;

  return (
    <div
      className={cn(
        'w-60 rounded-lg border bg-card px-3.5 py-2.5 text-card-foreground shadow-xs transition-all',
        meta.accent,
        selected && 'ring-2 ring-primary shadow-md',
        !selected && data.isIncoming && 'ring-1 ring-sky-500/70',
        !selected && data.isOutgoing && 'ring-1 ring-indigo-500/70',
        data.isDimmed && 'opacity-35'
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!size-2.5 !bg-primary !border-background"
      />
      <div className="flex items-center justify-between gap-2 pb-1">
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          <Icon className="size-3 text-primary" />
          {meta.label}
        </span>
        <span className="inline-flex items-center gap-1 text-[10px] font-medium text-muted-foreground capitalize">
          <span className={cn('size-1.5 rounded-full', STATUS_DOT[data.status])} />
          {data.status}
        </span>
      </div>
      <p className="font-mono text-xs font-semibold text-foreground truncate">
        {data.label}
      </p>
      <p className="mt-0.5 font-mono text-[10px] text-muted-foreground truncate">
        {data.filePath}:{data.lineNumber}
      </p>
      {(data.hasHiddenCallers || data.hasHiddenCallees) && (
        <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-primary font-medium">
          {data.hasHiddenCallers && <span>+ Callers collapsed</span>}
          {data.hasHiddenCallees && <span>+ Callees collapsed</span>}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!size-2.5 !bg-primary !border-background"
      />
    </div>
  );
}

const nodeTypes = {
  execNode: ExecutionNodeCard,
};

function ExecutionTracingWorkspace() {
  const { id = 'repo-cloud-gateway' } = useParams<{ id: string }>();
  const theme = useThemeStore((state) => state.theme);
  const { zoomIn, zoomOut, fitView, setCenter } = useReactFlow();

  const repoQuery = useQuery({
    queryKey: ['repository', id],
    queryFn: () => repositoryService.getRepository(id),
  });

  const workspaceQuery = useQuery({
    queryKey: ['execution-workspace', id],
    queryFn: () => executionService.getExecutionWorkspace(id),
  });

  const [selectedEntryId, setSelectedEntryId] = useState<string>('');
  const [traceHistory, setTraceHistory] = useState<string[]>([]);
  const [fnSearch, setFnSearch] = useState('');
  const [endpointSearch, setEndpointSearch] = useState('');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());
  const [collapsedFileGroups, setCollapsedFileGroups] = useState<Set<string>>(
    new Set()
  );
  const [viewMode, setViewMode] = useState<'graph' | 'steps'>('graph');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isExplaining, setIsExplaining] = useState(false);
  const [explanation, setExplanation] = useState<ExecutionExplanationResponse | null>(null);
  const [isExplainOpen, setIsExplainOpen] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const traces = workspaceQuery.data?.traces ?? [];
  const functions = workspaceQuery.data?.functions ?? [];

  const filteredTraces = useMemo(() => {
    const eq = endpointSearch.trim().toLowerCase();
    if (!eq) return traces;
    return traces.filter(
      (t) =>
        t.flow.entryPoint.toLowerCase().includes(eq) ||
        t.flow.title.toLowerCase().includes(eq)
    );
  }, [traces, endpointSearch]);

  useEffect(() => {
    if (traces.length > 0 && !traces.some((t) => t.flow.id === selectedEntryId)) {
      const firstId = traces[0].flow.id;
      setSelectedEntryId(firstId);
      setTraceHistory([firstId]);
      setExpandedNodeIds(new Set(traces[0].nodes.map((n) => n.id)));
      setSelectedNodeId(traces[0].nodes[0]?.id ?? null);
    }
  }, [traces, selectedEntryId]);

  const activeTrace = useMemo(
    () =>
      traces.find((t) => t.flow.id === selectedEntryId) ?? traces[0] ?? null,
    [traces, selectedEntryId]
  );

  const handleRunTrace = useCallback(
    (entryId: string) => {
      const target = traces.find((t) => t.flow.id === entryId);
      if (!target) return;
      setSelectedEntryId(entryId);
      setExpandedNodeIds(new Set(target.nodes.map((n) => n.id)));
      setSelectedNodeId(target.nodes[0]?.id ?? null);
      setTraceHistory((prev) => [
        entryId,
        ...prev.filter((item) => item !== entryId),
      ].slice(0, 6));
      toast.success(`Traced execution entry: ${target.flow.entryPoint}`);
      setTimeout(() => {
        fitView({ duration: 280, padding: 0.18 });
      }, 60);
    },
    [traces, fitView]
  );

  const handleExplainFlow = useCallback(async () => {
    if (!activeTrace) return;
    setIsExplaining(true);
    setIsExplainOpen(true);
    try {
      const res = await executionService.explainExecutionFlow?.(id, {
        flowId: activeTrace.flow.id,
        symbolId: selectedNodeId ?? activeTrace.flow.rootNodeId,
      });
      if (res) {
        setExplanation(res);
        toast.success('AI execution explanation generated');
      }
    } catch {
      toast.error('Failed to generate AI execution flow explanation');
    } finally {
      setIsExplaining(false);
    }
  }, [id, activeTrace, selectedNodeId]);

  const handleTriggerAnalysis = useCallback(async () => {
    setIsAnalyzing(true);
    try {
      const res = await executionService.analyzeExecution?.(id);
      if (res) {
        toast.success(
          `Analysis completed: ${res.calls_extracted || 0} calls extracted, ${res.traces_generated || 0} traces generated`
        );
        workspaceQuery.refetch();
      }
    } catch {
      toast.error('Failed to trigger execution analysis');
    } finally {
      setIsAnalyzing(false);
    }
  }, [id, workspaceQuery]);

  // Functions grouped by file path in Left Explorer
  const groupedFunctions = useMemo(() => {
    const q = fnSearch.trim().toLowerCase();
    const filtered = functions.filter((fn) => {
      if (!q) return true;
      return (
        fn.name.toLowerCase().includes(q) ||
        fn.filePath.toLowerCase().includes(q) ||
        fn.nodeType.toLowerCase().includes(q)
      );
    });

    const groups = new Map<string, ExecutionFunctionSymbol[]>();
    for (const fn of filtered) {
      const list = groups.get(fn.filePath) ?? [];
      list.push(fn);
      groups.set(fn.filePath, list);
    }
    return Array.from(groups.entries());
  }, [functions, fnSearch]);

  // Visible nodes & edges filtered by expand/collapse state
  const computedGraph = useMemo(() => {
    if (!activeTrace) return { nodes: [] as ExecRFNode[], edges: [] as Edge[] };

    const visibleNodes = activeTrace.nodes.filter((n) =>
      expandedNodeIds.has(n.id)
    );
    const visibleIds = new Set(visibleNodes.map((n) => n.id));

    const connectedEdges = activeTrace.edges.filter(
      (e) => visibleIds.has(e.source) && visibleIds.has(e.target)
    );

    const incomingSet = new Set<string>();
    const outgoingSet = new Set<string>();
    if (selectedNodeId) {
      for (const e of connectedEdges) {
        if (e.target === selectedNodeId) incomingSet.add(e.source);
        if (e.source === selectedNodeId) outgoingSet.add(e.target);
      }
    }

    const rfNodes: ExecRFNode[] = visibleNodes.map((n) => {
      const isSelected = n.id === selectedNodeId;
      const isIncoming = incomingSet.has(n.id);
      const isOutgoing = outgoingSet.has(n.id);
      const isDimmed =
        selectedNodeId !== null && !isSelected && !isIncoming && !isOutgoing;

      const hasHiddenCallers = activeTrace.edges.some(
        (e) => e.target === n.id && !visibleIds.has(e.source)
      );
      const hasHiddenCallees = activeTrace.edges.some(
        (e) => e.source === n.id && !visibleIds.has(e.target)
      );

      return {
        id: n.id,
        type: 'execNode',
        position: n.position,
        selected: isSelected,
        data: {
          ...n,
          isIncoming,
          isOutgoing,
          isDimmed,
          hasHiddenCallers,
          hasHiddenCallees,
        },
      };
    });

    const rfEdges: Edge[] = connectedEdges.map((edge) => {
      const isOutgoing =
        selectedNodeId !== null && edge.source === selectedNodeId;
      const isIncoming =
        selectedNodeId !== null && edge.target === selectedNodeId;
      const isActiveEdge = isOutgoing || isIncoming;
      const isDimmed = selectedNodeId !== null && !isActiveEdge;

      const strokeColor = isOutgoing
        ? '#6366f1'
        : isIncoming
          ? '#0ea5e9'
          : edge.status === 'unresolved'
            ? '#ef4444'
            : edge.status === 'inferred'
              ? '#d97706'
              : '#64748b';

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        animated: isActiveEdge || edge.status === 'inferred',
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 15,
          height: 15,
          color: strokeColor,
        },
        style: {
          stroke: strokeColor,
          strokeWidth: isActiveEdge ? 2.4 : 1.5,
          strokeDasharray:
            edge.status === 'inferred' || edge.status === 'unresolved'
              ? '5 4'
              : undefined,
          opacity: isDimmed ? 0.22 : 1,
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
  }, [activeTrace, expandedNodeIds, selectedNodeId, theme]);

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<ExecRFNode>([]);
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Sync nodes & edges while preserving dragged positions for existing node IDs
  useEffect(() => {
    setRfNodes((prevNodes) => {
      const prevPos = new Map(prevNodes.map((n) => [n.id, n.position]));
      return computedGraph.nodes.map((node) => ({
        ...node,
        position: prevPos.get(node.id) ?? node.position,
      }));
    });
    setRfEdges(computedGraph.edges);
  }, [computedGraph, setRfNodes, setRfEdges]);

  const focusNodeInGraph = useCallback(
    (nodeId: string) => {
      // Switch trace if the function is not in the currently active trace
      const inCurrent = activeTrace?.nodes.some((n) => n.id === nodeId);
      if (!inCurrent) {
        const ownerTrace = traces.find((t) =>
          t.nodes.some((n) => n.id === nodeId)
        );
        if (ownerTrace) {
          setSelectedEntryId(ownerTrace.flow.id);
          setExpandedNodeIds(new Set(ownerTrace.nodes.map((n) => n.id)));
          setSelectedNodeId(nodeId);
          setTraceHistory((prev) =>
            [ownerTrace.flow.id, ...prev.filter((x) => x !== ownerTrace.flow.id)].slice(0, 6)
          );
          const target = ownerTrace.nodes.find((n) => n.id === nodeId);
          if (target) {
            setTimeout(() => {
              setCenter(target.position.x + 120, target.position.y + 40, {
                zoom: 1,
                duration: 300,
              });
            }, 80);
          }
          return;
        }
      }

      setExpandedNodeIds((prev) => {
        const next = new Set(prev);
        next.add(nodeId);
        return next;
      });
      setSelectedNodeId(nodeId);
      const existing =
        rfNodes.find((n) => n.id === nodeId) ??
        activeTrace?.nodes.find((n) => n.id === nodeId);
      if (existing) {
        setCenter(existing.position.x + 120, existing.position.y + 40, {
          zoom: 1.05,
          duration: 300,
        });
      }
    },
    [activeTrace, traces, rfNodes, setCenter]
  );

  const handleResetLayout = useCallback(() => {
    if (!activeTrace) return;
    setExpandedNodeIds(new Set(activeTrace.nodes.map((n) => n.id)));
    setRfNodes(computedGraph.nodes);
    setTimeout(() => {
      fitView({ duration: 280, padding: 0.16 });
    }, 50);
  }, [activeTrace, computedGraph.nodes, setRfNodes, fitView]);

  const handleExpandCallers = useCallback(() => {
    if (!activeTrace || !selectedNodeId) return;
    const callerIds = activeTrace.edges
      .filter((e) => e.target === selectedNodeId)
      .map((e) => e.source);
    if (callerIds.length === 0) {
      toast.info('No direct callers found for this node in this trace.');
      return;
    }
    setExpandedNodeIds((prev) => {
      const next = new Set(prev);
      callerIds.forEach((cid) => next.add(cid));
      return next;
    });
    toast.success(`Expanded ${callerIds.length} caller node(s).`);
  }, [activeTrace, selectedNodeId]);

  const handleExpandCallees = useCallback(() => {
    if (!activeTrace || !selectedNodeId) return;
    const calleeIds = activeTrace.edges
      .filter((e) => e.source === selectedNodeId)
      .map((e) => e.target);
    if (calleeIds.length === 0) {
      toast.info('No direct callees found for this node in this trace.');
      return;
    }
    setExpandedNodeIds((prev) => {
      const next = new Set(prev);
      calleeIds.forEach((cid) => next.add(cid));
      return next;
    });
    toast.success(`Expanded ${calleeIds.length} callee node(s).`);
  }, [activeTrace, selectedNodeId]);

  const handleCollapseBranch = useCallback(() => {
    if (!activeTrace || !selectedNodeId) return;
    const downstreamIds = new Set<string>();
    const queue = [selectedNodeId];
    while (queue.length > 0) {
      const curr = queue.shift()!;
      for (const e of activeTrace.edges) {
        if (e.source === curr && !downstreamIds.has(e.target)) {
          downstreamIds.add(e.target);
          queue.push(e.target);
        }
      }
    }
    if (downstreamIds.size === 0) {
      toast.info('This node has no expanded downstream nodes to collapse.');
      return;
    }
    setExpandedNodeIds((prev) => {
      const next = new Set(prev);
      downstreamIds.forEach((d) => next.delete(d));
      return next;
    });
    toast.info(`Collapsed ${downstreamIds.size} downstream node(s).`);
  }, [activeTrace, selectedNodeId]);

  const selectedDetails = useMemo(() => {
    if (!selectedNodeId) return null;
    const fromTrace = activeTrace?.nodes.find((n) => n.id === selectedNodeId);
    if (fromTrace) return fromTrace;
    const fromFn = functions.find((f) => f.id === selectedNodeId);
    if (!fromFn) return null;
    return {
      id: fromFn.id,
      label: fromFn.name,
      nodeType: fromFn.nodeType,
      filePath: fromFn.filePath,
      lineNumber: fromFn.lineNumber,
      parameters: fromFn.parameters,
      returnType: fromFn.returnType,
      description: fromFn.description,
      status: fromFn.status,
      callers: fromFn.callers,
      callees: fromFn.callees,
      relatedFunctions: fromFn.relatedFunctions,
      codeSnippet: fromFn.codeSnippet,
    };
  }, [selectedNodeId, activeTrace, functions]);

  const fnNameById = useMemo(
    () => new Map(functions.map((f) => [f.id, f.name])),
    [functions]
  );

  const handleCopyDetails = async () => {
    if (!selectedDetails) return;
    const text = [
      `Function: ${selectedDetails.label}${selectedDetails.parameters}`,
      `Return Type: ${selectedDetails.returnType}`,
      `File: ${selectedDetails.filePath}:${selectedDetails.lineNumber}`,
      `Status: ${selectedDetails.status}`,
      `Description: ${selectedDetails.description}`,
    ].join('\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(selectedDetails.id);
      toast.success('Function details copied to clipboard.');
      setTimeout(() => setCopiedId(null), 1800);
    } catch {
      toast.error('Clipboard access unavailable in this browser context.');
    }
  };

  if (workspaceQuery.isError) {
    return (
      <ErrorState
        message="Unable to load execution trace workspace."
        onRetry={() => workspaceQuery.refetch()}
      />
    );
  }

  return (
    <PageFadeIn className="space-y-4">
      {/* Top Section */}
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 surface-card">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="font-mono font-medium text-primary">
                {repoQuery.data
                  ? `${repoQuery.data.owner}/${repoQuery.data.name}`
                  : id}
              </span>
              <span>·</span>
              <span>Execution Flow Tracing</span>
            </div>
            <h1 className="font-heading text-2xl font-bold tracking-tight mt-0.5">
              Execution Flow Tracing
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleExplainFlow}
              disabled={!activeTrace || isExplaining}
              className="h-8 gap-1.5 border-primary/30 text-xs font-medium text-primary hover:bg-primary/10"
            >
              {isExplaining ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Sparkles className="size-3.5" />
              )}
              Explain with AI
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleTriggerAnalysis}
              disabled={isAnalyzing}
              className="h-8 gap-1.5 text-xs font-medium"
            >
              {isAnalyzing ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <RotateCcw className="size-3.5" />
              )}
              Re-analyze Flow
            </Button>

            <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
              <button
                type="button"
                onClick={() => setViewMode('graph')}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors whitespace-nowrap',
                  viewMode === 'graph'
                    ? 'bg-card text-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <Workflow className="size-3.5" />
                Graph View
              </button>
              <button
                type="button"
                onClick={() => setViewMode('steps')}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors whitespace-nowrap',
                  viewMode === 'steps'
                    ? 'bg-card text-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <ListOrdered className="size-3.5" />
                Step-by-Step
              </button>
            </div>
          </div>
        </div>

        {/* Search & Entry Point Controls */}
        <div className="grid grid-cols-1 gap-2.5 md:grid-cols-12">
          <div className="relative md:col-span-3">
            <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={fnSearch}
              onChange={(e) => setFnSearch(e.target.value)}
              placeholder="Search function..."
              aria-label="Search function"
              className="h-8 pl-8 text-xs"
            />
          </div>

          <div className="relative md:col-span-3">
            <Globe className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={endpointSearch}
              onChange={(e) => setEndpointSearch(e.target.value)}
              placeholder="Search API endpoint..."
              aria-label="Search API endpoint"
              className="h-8 pl-8 text-xs font-mono"
            />
          </div>

          <div className="md:col-span-4">
            <Select
              value={selectedEntryId}
              onValueChange={(val) => handleRunTrace(val)}
            >
              <SelectTrigger
                aria-label="Select execution entry point"
                className="h-8 w-full text-xs"
              >
                <SelectValue placeholder="Select execution entry point" />
              </SelectTrigger>
              <SelectContent>
                {(filteredTraces.length > 0 ? filteredTraces : traces).map(
                  (trace) => (
                    <SelectItem
                      key={trace.flow.id}
                      value={trace.flow.id}
                      className="text-xs"
                    >
                      <span className="font-medium">{trace.flow.title}</span>
                      <span className="ml-2 font-mono text-muted-foreground">
                        ({trace.flow.entryPoint})
                      </span>
                    </SelectItem>
                  )
                )}
              </SelectContent>
            </Select>
          </div>

          <div className="md:col-span-2">
            <Button
              type="button"
              size="sm"
              className="h-8 w-full whitespace-nowrap"
              onClick={() => activeTrace && handleRunTrace(activeTrace.flow.id)}
              disabled={!activeTrace}
            >
              <Play className="mr-1.5 size-3.5" />
              Trace
            </Button>
          </div>
        </div>

        {/* Execution Path History */}
        {traceHistory.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-t border-border pt-2.5 text-xs">
            <span className="inline-flex items-center gap-1 text-muted-foreground font-medium">
              <History className="size-3.5" />
              Path History:
            </span>
            {traceHistory.map((histId) => {
              const t = traces.find((item) => item.flow.id === histId);
              if (!t) return null;
              const isCurrent = histId === activeTrace?.flow.id;
              return (
                <button
                  key={histId}
                  type="button"
                  onClick={() => handleRunTrace(histId)}
                  className={cn(
                    'rounded-md border px-2 py-0.5 font-mono text-[11px] transition-colors',
                    isCurrent
                      ? 'border-primary/50 bg-accent text-accent-foreground font-semibold'
                      : 'border-border bg-background text-muted-foreground hover:text-foreground'
                  )}
                >
                  {t.flow.entryPoint}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {workspaceQuery.isLoading ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <Skeleton className="h-[580px] lg:col-span-3" />
          <Skeleton className="h-[580px] lg:col-span-6" />
          <Skeleton className="h-[580px] lg:col-span-3" />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* Left Panel — Function Explorer */}
          <Card className="lg:col-span-3 flex flex-col h-[580px] py-0">
            <CardHeader className="border-b border-border px-4 py-3 shrink-0">
              <CardTitle className="flex items-center justify-between text-sm font-semibold">
                <span className="inline-flex items-center gap-1.5">
                  <FolderTree className="size-4 text-primary" />
                  Function Explorer
                </span>
                <span className="font-mono text-xs text-muted-foreground tabular-nums">
                  {functions.length}
                </span>
              </CardTitle>
            </CardHeader>

            <ScrollArea className="flex-1 p-2">
              {groupedFunctions.length === 0 ? (
                <div className="py-10 text-center text-xs text-muted-foreground">
                  No functions match &ldquo;{fnSearch}&rdquo;.
                </div>
              ) : (
                <div className="space-y-2">
                  {groupedFunctions.map(([filePath, fileFns]) => {
                    const isFileCollapsed = collapsedFileGroups.has(filePath);
                    return (
                      <div
                        key={filePath}
                        className="rounded-lg border border-border/70 bg-background/60"
                      >
                        <button
                          type="button"
                          onClick={() =>
                            setCollapsedFileGroups((prev) => {
                              const next = new Set(prev);
                              if (next.has(filePath)) next.delete(filePath);
                              else next.add(filePath);
                              return next;
                            })
                          }
                          className="flex w-full items-center gap-1.5 px-2.5 py-2 text-left text-[11px] font-mono text-muted-foreground hover:text-foreground"
                        >
                          {isFileCollapsed ? (
                            <ChevronRight className="size-3.5 shrink-0" />
                          ) : (
                            <ChevronDown className="size-3.5 shrink-0" />
                          )}
                          <FileCode2 className="size-3.5 text-primary shrink-0" />
                          <span className="truncate font-medium text-foreground">
                            {filePath}
                          </span>
                        </button>

                        {!isFileCollapsed && (
                          <div className="border-t border-border/60 p-1 space-y-0.5">
                            {fileFns.map((fn) => {
                              const active = fn.id === selectedNodeId;
                              const meta = NODE_TYPE_META[fn.nodeType];
                              return (
                                <button
                                  key={fn.id}
                                  type="button"
                                  onClick={() => focusNodeInGraph(fn.id)}
                                  className={cn(
                                    'flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left transition-colors',
                                    active
                                      ? 'bg-accent text-accent-foreground'
                                      : 'hover:bg-muted/70'
                                  )}
                                >
                                  <div className="min-w-0">
                                    <p className="font-mono text-xs font-medium truncate">
                                      {fn.name}
                                    </p>
                                    <p className="text-[10px] text-muted-foreground truncate">
                                      {meta.label} · L{fn.lineNumber}
                                    </p>
                                  </div>
                                  <span
                                    className={cn(
                                      'size-2 rounded-full shrink-0',
                                      STATUS_DOT[fn.status]
                                    )}
                                    title={`Status: ${fn.status}`}
                                  />
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </ScrollArea>
          </Card>

          {/* Center Panel — Interactive Execution Graph or Step-by-Step */}
          <Card className="lg:col-span-5 xl:col-span-6 flex flex-col h-[580px] py-0 overflow-hidden">
            {viewMode === 'graph' ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-card px-3.5 py-2.5 shrink-0">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-foreground truncate">
                      {activeTrace?.flow.title ?? 'Execution Graph'}
                    </p>
                    <p className="font-mono text-[11px] text-muted-foreground truncate">
                      {activeTrace?.flow.entryPoint}
                    </p>
                  </div>

                  {/* Graph Interaction Toolbar */}
                  <div className="flex flex-wrap items-center gap-1">
                    <Button
                      type="button"
                      variant="outline"
                      size="icon-xs"
                      onClick={() => zoomIn({ duration: 200 })}
                      title="Zoom in"
                      aria-label="Zoom in"
                    >
                      <ZoomIn className="size-3.5" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon-xs"
                      onClick={() => zoomOut({ duration: 200 })}
                      title="Zoom out"
                      aria-label="Zoom out"
                    >
                      <ZoomOut className="size-3.5" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon-xs"
                      onClick={() => fitView({ duration: 250, padding: 0.16 })}
                      title="Fit graph to screen"
                      aria-label="Fit graph to screen"
                    >
                      <Maximize2 className="size-3.5" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="xs"
                      onClick={handleResetLayout}
                      title="Reset node positions and expand all"
                    >
                      <RotateCcw className="mr-1 size-3" />
                      Reset
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="xs"
                      onClick={handleExpandCallers}
                      disabled={!selectedNodeId}
                    >
                      <Expand className="mr-1 size-3" />
                      Callers
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="xs"
                      onClick={handleExpandCallees}
                      disabled={!selectedNodeId}
                    >
                      <Expand className="mr-1 size-3" />
                      Callees
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="xs"
                      onClick={handleCollapseBranch}
                      disabled={!selectedNodeId}
                    >
                      <Shrink className="mr-1 size-3" />
                      Collapse
                    </Button>
                  </div>
                </div>

                <div className="relative flex-1 bg-background/50">
                  {rfNodes.length === 0 ? (
                    <div className="p-8">
                      <EmptyState
                        icon={<Activity className="size-5" />}
                        title="No nodes visible"
                        description="Reset the trace layout to restore all execution nodes."
                        actionLabel="Reset Layout"
                        onAction={handleResetLayout}
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
                      onNodeClick={(_e, node) => setSelectedNodeId(node.id)}
                      onPaneClick={() => setSelectedNodeId(null)}
                    >
                      <Background gap={18} size={1} />
                      <MiniMap pannable zoomable />
                    </ReactFlow>
                  )}

                  {/* Legend Overlay */}
                  <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card/95 px-3 py-1.5 text-[11px] text-muted-foreground backdrop-blur-xs">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="size-2 rounded-full bg-emerald-500" />
                      Verified
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <span className="size-2 rounded-full bg-amber-500" />
                      Inferred
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <span className="size-2 rounded-full bg-slate-400" />
                      Unresolved
                    </span>
                  </div>
                </div>
              </>
            ) : (
              <>
                <CardHeader className="border-b border-border px-4 py-3 shrink-0">
                  <CardTitle className="text-sm font-semibold">
                    Step-by-Step Execution Sequence · {activeTrace?.flow.title}
                  </CardTitle>
                </CardHeader>
                <ScrollArea className="flex-1 p-4">
                  <div className="space-y-3">
                    {activeTrace?.flow.steps.map((step) => {
                      const active = step.nodeId === selectedNodeId;
                      return (
                        <button
                          key={step.stepOrder}
                          type="button"
                          onClick={() => {
                            setSelectedNodeId(step.nodeId);
                          }}
                          className={cn(
                            'w-full rounded-lg border p-3.5 text-left transition-colors space-y-2',
                            active
                              ? 'border-primary bg-accent/40'
                              : 'border-border bg-background hover:bg-muted/40'
                          )}
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="flex size-6 items-center justify-center rounded bg-primary/15 font-mono text-xs font-semibold text-primary tabular-nums">
                                {String(step.stepOrder).padStart(2, '0')}
                              </span>
                              <span className="font-mono text-xs font-semibold text-foreground truncate">
                                {step.functionName}
                              </span>
                            </div>
                            <ConfidenceBadge confidence={step.status} />
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {step.description}
                          </p>
                          <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] text-muted-foreground">
                            <span className="inline-flex items-center gap-1">
                              {step.caller} <ArrowRight className="size-3" />{' '}
                              {step.callee}
                            </span>
                            <span>
                              {step.filePath}:{step.lineNumber}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </ScrollArea>
              </>
            )}
          </Card>

          {/* Right Panel — Execution Details */}
          <Card className="lg:col-span-4 xl:col-span-3 flex flex-col h-[580px] py-0">
            <CardHeader className="border-b border-border px-4 py-3 shrink-0">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-sm font-semibold">
                  Execution Details
                </CardTitle>
                {selectedDetails && (
                  <Button
                    type="button"
                    variant="outline"
                    size="xs"
                    onClick={handleCopyDetails}
                  >
                    {copiedId === selectedDetails.id ? (
                      <>
                        <Check className="mr-1 size-3 text-emerald-500" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="mr-1 size-3" />
                        Copy
                      </>
                    )}
                  </Button>
                )}
              </div>
            </CardHeader>

            <ScrollArea className="flex-1 p-4">
              {!selectedDetails ? (
                <div className="py-12 text-center text-xs text-muted-foreground">
                  Select a node in the execution graph or Function Explorer to inspect
                  parameters, callers, callees, and source preview.
                </div>
              ) : (
                <div className="space-y-4 text-xs">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                        {NODE_TYPE_META[selectedDetails.nodeType].label}
                      </span>
                      <ConfidenceBadge confidence={selectedDetails.status} />
                    </div>
                    <h2 className="font-mono text-base font-bold text-foreground break-all">
                      {selectedDetails.label}
                    </h2>
                    <p className="font-mono text-[11px] text-muted-foreground break-all">
                      {selectedDetails.filePath} · Line {selectedDetails.lineNumber}
                    </p>
                  </div>

                  <p className="leading-relaxed text-foreground">
                    {selectedDetails.description}
                  </p>

                  <div className="rounded-lg border border-border bg-muted/40 p-2.5 space-y-1.5 font-mono text-[11px]">
                    <div>
                      <span className="text-muted-foreground">Params: </span>
                      <span className="text-foreground break-all">
                        {selectedDetails.parameters}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Returns: </span>
                      <span className="text-primary font-medium break-all">
                        {selectedDetails.returnType}
                      </span>
                    </div>
                  </div>

                  {/* Callers */}
                  <div className="space-y-1.5">
                    <p className="font-semibold text-foreground inline-flex items-center gap-1">
                      <ArrowDownLeft className="size-3.5 text-sky-500" />
                      Callers ({selectedDetails.callers.length})
                    </p>
                    {selectedDetails.callers.length === 0 ? (
                      <p className="text-muted-foreground">
                        Entry point (no upstream callers)
                      </p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {selectedDetails.callers.map((callerId) => (
                          <button
                            key={callerId}
                            type="button"
                            onClick={() => focusNodeInGraph(callerId)}
                            className="rounded-md border border-border bg-background px-2 py-1 font-mono text-[11px] text-foreground hover:border-primary/50 hover:text-primary transition-colors"
                          >
                            {fnNameById.get(callerId) ?? callerId}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Callees */}
                  <div className="space-y-1.5">
                    <p className="font-semibold text-foreground inline-flex items-center gap-1">
                      <ArrowUpRight className="size-3.5 text-indigo-500" />
                      Callees ({selectedDetails.callees.length})
                    </p>
                    {selectedDetails.callees.length === 0 ? (
                      <p className="text-muted-foreground">
                        Terminal step (no downstream callees)
                      </p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {selectedDetails.callees.map((calleeId) => (
                          <button
                            key={calleeId}
                            type="button"
                            onClick={() => focusNodeInGraph(calleeId)}
                            className="rounded-md border border-border bg-background px-2 py-1 font-mono text-[11px] text-foreground hover:border-primary/50 hover:text-primary transition-colors"
                          >
                            {fnNameById.get(calleeId) ?? calleeId}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Related Functions */}
                  {selectedDetails.relatedFunctions.length > 0 && (
                    <div className="space-y-1.5">
                      <p className="font-semibold text-foreground">
                        Related Functions
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedDetails.relatedFunctions.map((rel) => (
                          <span
                            key={rel}
                            className="rounded border border-border bg-muted/40 px-2 py-0.5 font-mono text-[11px] text-muted-foreground"
                          >
                            {rel}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Source Code Preview */}
                  <div className="space-y-1.5">
                    <p className="font-semibold text-foreground">
                      Source Code Preview
                    </p>
                    <pre className="overflow-x-auto rounded-lg border border-border bg-muted/60 p-3 font-mono text-[11px] leading-relaxed text-foreground">
                      <code>{selectedDetails.codeSnippet}</code>
                    </pre>
                  </div>

                  <Button asChild size="sm" className="w-full">
                    <Link
                      to={`${getRepositoryRoute(id, 'explorer')}?file=${encodeURIComponent(selectedDetails.filePath)}`}
                    >
                      Open in Project Explorer
                      <ExternalLink className="ml-1.5 size-3.5" />
                    </Link>
                  </Button>
                </div>
              )}
            </ScrollArea>
          </Card>
        </div>
      )}
      {/* AI Explanation Modal */}
      <Dialog open={isExplainOpen} onOpenChange={setIsExplainOpen}>
        <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col p-6">
          <DialogHeader className="border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <div className="flex size-7 items-center justify-center rounded-lg bg-primary/15 text-primary">
                <Brain className="size-4" />
              </div>
              <div>
                <DialogTitle className="text-base font-semibold">
                  AI Grounded Execution Flow Explanation
                </DialogTitle>
                <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                  Trace: {activeTrace?.flow.title} ({activeTrace?.flow.entryPoint})
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <ScrollArea className="flex-1 pr-3 pt-3">
            {isExplaining ? (
              <div className="flex flex-col items-center justify-center py-12 gap-3 text-muted-foreground">
                <Loader2 className="size-8 animate-spin text-primary" />
                <p className="text-sm font-medium">Synthesizing execution flow using source static evidence...</p>
                <p className="text-xs text-muted-foreground">Analyzing caller-callee bindings and cross-file paths</p>
              </div>
            ) : explanation ? (
              <div className="space-y-4 text-xs">
                {/* Summary */}
                <div className="rounded-lg border border-border bg-card p-3.5 space-y-1.5">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-primary">
                    Flow Summary
                  </span>
                  <p className="text-sm leading-relaxed text-foreground">
                    {explanation.summary}
                  </p>
                </div>

                {/* Verified Steps */}
                <div className="space-y-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Verified Execution Sequence ({explanation.verifiedSteps.length} steps)
                  </span>
                  <div className="space-y-2">
                    {explanation.verifiedSteps.map((st) => (
                      <div
                        key={st.stepIndex}
                        className="rounded-lg border border-border bg-background p-3 space-y-1.5"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="flex size-5 items-center justify-center rounded bg-primary/15 font-mono text-[10px] font-semibold text-primary">
                              {st.stepIndex}
                            </span>
                            <span className="font-mono text-xs font-semibold text-foreground">
                              {st.caller} → {st.callee}
                            </span>
                          </div>
                          <ConfidenceBadge confidence={st.confidence as any} />
                        </div>
                        <p className="text-xs text-muted-foreground">{st.explanation}</p>
                        <p className="font-mono text-[10px] text-muted-foreground">
                          {st.sourceFile}:{st.sourceLine}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Uncertainties & Static Limits */}
                {explanation.uncertainties && explanation.uncertainties.length > 0 && (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3.5 space-y-2">
                    <div className="flex items-center gap-1.5 text-amber-500 font-semibold text-xs">
                      <AlertTriangle className="size-4 shrink-0" />
                      Static Analysis Boundaries & Uncertainties
                    </div>
                    <ul className="list-disc list-inside space-y-1 text-muted-foreground text-[11px]">
                      {explanation.uncertainties.map((u, i) => (
                        <li key={i}>{u}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-2 border-t border-border">
                  <span>Provider: {explanation.providerUsed}</span>
                  <span className="text-emerald-500">Grounding: 100% Static Source Evidence</span>
                </div>
              </div>
            ) : null}
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </PageFadeIn>
  );
}

export function ExecutionPage() {
  return (
    <ReactFlowProvider>
      <ExecutionTracingWorkspace />
    </ReactFlowProvider>
  );
}
