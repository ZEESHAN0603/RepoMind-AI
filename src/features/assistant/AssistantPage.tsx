import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  Check,
  Copy,
  FileCode2,
  GitBranch,
  Loader2,
  MessageSquarePlus,
  Send,
  Sparkles,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ConfidenceBadge } from '@/components/common/ConfidenceBadge';
import { ErrorState } from '@/components/common/ErrorState';
import { SampleDataBanner } from '@/components/common/SampleDataBanner';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { getRepositoryRoute } from '@/constants/routes';
import { cn } from '@/lib/utils';
import { assistantService, repositoryService } from '@/services';
import type { AssistantConversation } from '@/types';
import { formatRelativeTime } from '@/utils/formatters';

export function AssistantPage() {
  const { id = 'repo-cloud-gateway' } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [activeConvId, setActiveConvId] = useState<string>('');
  const [promptInput, setPromptInput] = useState('');
  const [sendError, setSendError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const repoQuery = useQuery({
    queryKey: ['repository', id],
    queryFn: () => repositoryService.getRepository(id),
  });

  const convQuery = useQuery({
    queryKey: ['assistant-conversations', id],
    queryFn: () => assistantService.getConversations(id),
  });

  const suggestionsQuery = useQuery({
    queryKey: ['assistant-suggestions', id],
    queryFn: () => assistantService.getSuggestedQuestions(id),
  });

  useEffect(() => {
    const list = convQuery.data;
    if (list && list.length > 0 && !list.some((c) => c.id === activeConvId)) {
      setActiveConvId(list[0].id);
    }
  }, [convQuery.data, activeConvId]);

  const activeConversation =
    convQuery.data?.find((c) => c.id === activeConvId) ?? null;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages.length]);

  const sendMutation = useMutation({
    mutationFn: async (text: string) => {
      const convId = activeConvId || `conv-${id}-${Date.now()}`;
      if (!activeConvId) setActiveConvId(convId);
      return assistantService.sendMessage(id, convId, text);
    },
    onSuccess: () => {
      setSendError(null);
      setPromptInput('');
      queryClient.invalidateQueries({
        queryKey: ['assistant-conversations', id],
      });
    },
    onError: (err) => {
      setSendError(
        err instanceof Error
          ? err.message
          : 'Failed to generate sample assistant response.'
      );
    },
  });

  const handleNewConversation = () => {
    const newId = `conv-${id}-${Date.now()}`;
    const newConv: AssistantConversation = {
      id: newId,
      repositoryId: id,
      title: 'New repository inquiry',
      updatedAt: new Date().toISOString(),
      messages: [],
    };
    queryClient.setQueryData(
      ['assistant-conversations', id],
      (old: AssistantConversation[] | undefined) => [newConv, ...(old ?? [])]
    );
    setActiveConvId(newId);
    setSendError(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = promptInput.trim();
    if (!trimmed || sendMutation.isPending) return;
    setSendError(null);
    sendMutation.mutate(trimmed);
  };

  const handleCopy = async (msgId: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(msgId);
      toast.success('Response copied to clipboard.');
      setTimeout(() => setCopiedId(null), 1600);
    } catch {
      toast.error('Unable to copy response.');
    }
  };

  if (convQuery.isError) {
    return (
      <ErrorState
        message="Unable to load AI Assistant workspace."
        onRetry={() => convQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">
            Repository AI Assistant
          </h1>
          <p className="text-sm text-muted-foreground">
            Ask repository-specific questions with file path and line number citations.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleNewConversation}
          className="w-fit whitespace-nowrap shrink-0"
        >
          <MessageSquarePlus className="mr-1.5 size-4" />
          New Conversation
        </Button>
      </div>

      <SampleDataBanner message="Sample Phase 1 Assistant — Responses below are deterministic mock examples (not live Ollama or Gemini output). Type 'simulate error' to preview error handling." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Conversation History & Context */}
        <aside className="space-y-3 lg:col-span-3">
          {repoQuery.data && (
            <div className="rounded-lg border border-border bg-card p-3.5 space-y-1.5 text-xs">
              <p className="font-medium text-muted-foreground">Active Context</p>
              <p className="font-semibold text-foreground truncate">
                {repoQuery.data.owner}/{repoQuery.data.name}
              </p>
              <p className="flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
                <GitBranch className="size-3" />
                {repoQuery.data.branch} · {repoQuery.data.commitSha}
              </p>
            </div>
          )}

          <div className="rounded-lg border border-border bg-card p-2.5 space-y-1">
            <p className="px-2 py-1 text-xs font-semibold text-muted-foreground">
              Conversations
            </p>
            {convQuery.isLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : (
              convQuery.data?.map((conv) => (
                <button
                  key={conv.id}
                  type="button"
                  onClick={() => {
                    setActiveConvId(conv.id);
                    setSendError(null);
                  }}
                  className={cn(
                    'w-full rounded-md px-2.5 py-2 text-left text-xs transition-colors',
                    conv.id === activeConvId
                      ? 'bg-accent text-accent-foreground font-medium'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <p className="truncate">{conv.title}</p>
                  <p className="mt-0.5 text-[11px] opacity-75 tabular-nums">
                    {formatRelativeTime(conv.updatedAt)}
                  </p>
                </button>
              ))
            )}
          </div>
        </aside>

        {/* Chat Area */}
        <Card className="flex h-[620px] flex-col overflow-hidden lg:col-span-9">
          <ScrollArea className="flex-1 p-4 sm:p-5">
            <div className="space-y-5">
              {(!activeConversation || activeConversation.messages.length === 0) && (
                <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6 text-center space-y-3">
                  <Sparkles className="mx-auto size-6 text-primary" />
                  <div className="space-y-1">
                    <h2 className="text-sm font-semibold text-foreground">
                      Start a repository-grounded inquiry
                    </h2>
                    <p className="mx-auto max-w-md text-xs text-muted-foreground">
                      Select a suggested question below or ask about modules, auth
                      flows, circular dependencies, or API boundaries.
                    </p>
                  </div>
                </div>
              )}

              {activeConversation?.messages.map((msg) => (
                <div
                  key={msg.id}
                  className={cn(
                    'flex flex-col gap-2',
                    msg.role === 'user' ? 'items-end' : 'items-start'
                  )}
                >
                  <div
                    className={cn(
                      'max-w-[92%] sm:max-w-[85%] rounded-xl border px-4 py-3 text-sm space-y-3',
                      msg.role === 'user'
                        ? 'border-primary/30 bg-primary text-primary-foreground'
                        : 'border-border bg-background text-foreground'
                    )}
                  >
                    {msg.role === 'assistant' && (
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-foreground">
                            Sample Assistant Output
                          </span>
                          {msg.confidence && (
                            <ConfidenceBadge confidence={msg.confidence} />
                          )}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="xs"
                          onClick={() => handleCopy(msg.id, msg.content)}
                          className="h-6 px-2 text-xs"
                        >
                          {copiedId === msg.id ? (
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
                      </div>
                    )}

                    <p className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </p>

                    {msg.codeBlock && (
                      <div className="overflow-hidden rounded-lg border border-border bg-card">
                        <div className="border-b border-border bg-muted/40 px-3 py-1.5 font-mono text-[11px] text-muted-foreground">
                          {msg.codeBlock.filePath}
                        </div>
                        <pre className="overflow-x-auto p-3 font-mono text-xs text-foreground">
                          <code>{msg.codeBlock.code}</code>
                        </pre>
                      </div>
                    )}

                    {msg.citations && msg.citations.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        <span className="text-[11px] text-muted-foreground mr-1">
                          Citations:
                        </span>
                        {msg.citations.map((cit) => (
                          <Link
                            key={`${cit.filePath}-${cit.startLine}`}
                            to={`${getRepositoryRoute(id, 'explorer')}?file=${encodeURIComponent(cit.filePath)}`}
                            className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-0.5 font-mono text-[11px] text-primary hover:bg-muted transition-colors"
                          >
                            <FileCode2 className="size-3 shrink-0" />
                            <span>
                              {cit.filePath}:{cit.startLine}–{cit.endLine}
                            </span>
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {sendMutation.isPending && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="size-4 animate-spin text-primary" />
                  <span>Preparing sample repository-grounded response...</span>
                </div>
              )}

              {sendError && (
                <div
                  role="alert"
                  className="flex items-center justify-between gap-3 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-xs text-destructive"
                >
                  <div className="flex items-center gap-2">
                    <AlertCircle className="size-4 shrink-0" />
                    <span>{sendError}</span>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="xs"
                    onClick={() => setSendError(null)}
                  >
                    Dismiss
                  </Button>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </ScrollArea>

          {/* Suggested Questions + Input Bar */}
          <div className="border-t border-border bg-muted/20 p-3 space-y-2.5">
            {suggestionsQuery.data && (
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                {suggestionsQuery.data.map((q) => (
                  <button
                    key={q}
                    type="button"
                    disabled={sendMutation.isPending}
                    onClick={() => sendMutation.mutate(q)}
                    className="rounded-md border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors whitespace-nowrap shrink-0"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}

            <form onSubmit={handleSubmit} className="flex items-center gap-2">
              <Input
                value={promptInput}
                onChange={(e) => setPromptInput(e.target.value)}
                placeholder="Ask about architecture, auth flow, circular imports, or modules..."
                disabled={sendMutation.isPending}
                className="flex-1 bg-card"
              />
              <Button
                type="submit"
                size="sm"
                disabled={!promptInput.trim() || sendMutation.isPending}
                className="shrink-0"
              >
                <Send className="mr-1.5 size-3.5" />
                Send
              </Button>
            </form>
          </div>
        </Card>
      </div>
    </div>
  );
}
