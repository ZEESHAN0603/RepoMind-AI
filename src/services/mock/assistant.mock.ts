import type { AssistantService } from '@/services/api/intelligence.service';
import type { AssistantConversation, AssistantMessage } from '@/types';
import { simulateNetworkDelay } from './delay';

const SUGGESTED_QUESTIONS: string[] = [
  'Explain the overall project architecture.',
  'Where is authentication handled?',
  'Trace the login execution flow.',
  'Which modules depend on the database?',
  'Are there circular dependencies?',
  'Explain this function.',
  'How does the frontend communicate with the backend?',
];

const conversationsStore: Record<string, AssistantConversation[]> = {};

function createInitialConversations(repositoryId: string): AssistantConversation[] {
  return [
    {
      id: `conv-${repositoryId}-1`,
      repositoryId,
      title: 'Gateway auth & rate limiting overview',
      updatedAt: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
      messages: [
        {
          id: 'msg-1',
          role: 'user',
          content: 'Where is authentication handled?',
          timestamp: new Date(Date.now() - 1000 * 60 * 20).toISOString(),
        },
        {
          id: 'msg-2',
          role: 'assistant',
          confidence: 'verified',
          isSampleOutput: true,
          timestamp: new Date(Date.now() - 1000 * 60 * 19).toISOString(),
          content:
            'Sample Phase 1 response: Request authentication is enforced in `requireAuth` inside `src/middleware/auth.middleware.ts`. It extracts the Bearer token, validates JWT claims via `verifyJwtClaims`, and checks `sessionService.isTokenRevoked` before calling `next()`.',
          citations: [
            {
              filePath: 'src/middleware/auth.middleware.ts',
              startLine: 11,
              endLine: 39,
            },
            {
              filePath: 'src/services/token-validator.service.ts',
              startLine: 10,
              endLine: 22,
            },
          ],
          codeBlock: {
            language: 'typescript',
            filePath: 'src/middleware/auth.middleware.ts',
            code: `const claims = await verifyJwtClaims(token);\nconst isRevoked = await sessionService.isTokenRevoked(claims.jti);\nif (isRevoked) {\n  res.status(401).json({ error: 'Session has been revoked' });\n  return;\n}`,
          },
        },
      ],
    },
  ];
}

function buildMockAssistantReply(prompt: string): Omit<AssistantMessage, 'id' | 'role' | 'timestamp'> {
  const lower = prompt.toLowerCase();

  if (lower.includes('circular')) {
    return {
      confidence: 'verified',
      isSampleOutput: true,
      content:
        'Sample Phase 1 response: Yes — sample static analysis flags 2 circular import paths. The primary high-severity cycle connects `src/services/session.service.ts` and `src/services/token-validator.service.ts`. Extracting `normalizeTokenId` into a standalone utility breaks the cycle cleanly.',
      citations: [
        { filePath: 'src/services/session.service.ts', startLine: 1, endLine: 14 },
        { filePath: 'src/services/token-validator.service.ts', startLine: 8, endLine: 12 },
      ],
    };
  }

  if (lower.includes('architecture') || lower.includes('communicate')) {
    return {
      confidence: 'verified',
      isSampleOutput: true,
      content:
        'Sample Phase 1 response: Incoming HTTP traffic enters `createApp()` in `src/server.ts`, routes through `proxyRouter` (`/api/v1/:service/*`), passes sequentially through `requireAuth` and `tenantRateLimit`, and resolves the upstream cluster base URL.',
      citations: [
        { filePath: 'src/server.ts', startLine: 5, endLine: 12 },
        { filePath: 'src/routes/proxy.router.ts', startLine: 12, endLine: 30 },
      ],
      codeBlock: {
        language: 'typescript',
        filePath: 'src/routes/proxy.router.ts',
        code: `proxyRouter.all(\n  '/v1/:service/*',\n  requireAuth,\n  tenantRateLimit,\n  async (req, res) => { /* ... */ }\n);`,
      },
    };
  }

  if (lower.includes('database') || lower.includes('session')) {
    return {
      confidence: 'inferred',
      isSampleOutput: true,
      content:
        'Sample Phase 1 response (Inferred): `SessionService` (`src/services/session.service.ts`) owns token revocation lookups, while `auth.middleware.ts` consumes it on every authenticated request. In production deployment, this maps to the session/revocation store.',
      citations: [
        { filePath: 'src/services/session.service.ts', startLine: 5, endLine: 17 },
        { filePath: 'src/middleware/auth.middleware.ts', startLine: 25, endLine: 29 },
      ],
    };
  }

  if (lower.includes('trace') || lower.includes('flow') || lower.includes('login') || lower.includes('auth')) {
    return {
      confidence: 'verified',
      isSampleOutput: true,
      content:
        'Sample Phase 1 response: The request execution path starts at `proxyRouter` (line 12), calls `requireAuth` (line 13), delegates to `verifyJwtClaims` (line 12), verifies revocation in `SessionService.isTokenRevoked` (line 6), and enforces quotas in `tenantRateLimit` (line 11).',
      citations: [
        { filePath: 'src/middleware/auth.middleware.ts', startLine: 11, endLine: 36 },
        { filePath: 'src/services/rate-limiter.service.ts', startLine: 11, endLine: 28 },
      ],
    };
  }

  return {
    confidence: 'inferred',
    isSampleOutput: true,
    content: `Sample Phase 1 response for "${prompt}": Based on the indexed sample modules, this behavior spans \`src/routes/proxy.router.ts\` and \`src/middleware/auth.middleware.ts\`. In Phase 4, this assistant will stream grounded answers from your local Ollama model or Gemini fallback using repository embeddings.`,
    citations: [
      { filePath: 'src/server.ts', startLine: 5, endLine: 12 },
      { filePath: 'src/routes/proxy.router.ts', startLine: 12, endLine: 25 },
    ],
  };
}

export const mockAssistantService: AssistantService = {
  async getConversations(repositoryId: string) {
    await simulateNetworkDelay(180);
    if (!conversationsStore[repositoryId]) {
      conversationsStore[repositoryId] = createInitialConversations(repositoryId);
    }
    return structuredClone(conversationsStore[repositoryId]);
  },

  async getSuggestedQuestions(_repositoryId: string) {
    return [...SUGGESTED_QUESTIONS];
  },

  async sendMessage(repositoryId: string, conversationId: string, prompt: string) {
    await simulateNetworkDelay(550);

    if (prompt.trim().toLowerCase() === 'simulate error') {
      throw new Error(
        'Sample error state: Primary Ollama provider timed out and fallback is disabled in this test.'
      );
    }

    const userMsg: AssistantMessage = {
      id: `msg-u-${Date.now()}`,
      role: 'user',
      content: prompt,
      timestamp: new Date().toISOString(),
    };

    const replyMeta = buildMockAssistantReply(prompt);
    const assistantMsg: AssistantMessage = {
      id: `msg-a-${Date.now() + 1}`,
      role: 'assistant',
      timestamp: new Date().toISOString(),
      ...replyMeta,
    };

    const list =
      conversationsStore[repositoryId] ?? createInitialConversations(repositoryId);
    const existing = list.find((c) => c.id === conversationId);

    if (existing) {
      existing.messages.push(userMsg, assistantMsg);
      existing.updatedAt = assistantMsg.timestamp;
      if (existing.messages.length <= 2) {
        existing.title = prompt.slice(0, 44);
      }
    } else {
      list.unshift({
        id: conversationId,
        repositoryId,
        title: prompt.slice(0, 44),
        updatedAt: assistantMsg.timestamp,
        messages: [userMsg, assistantMsg],
      });
    }

    conversationsStore[repositoryId] = list;
    return structuredClone(assistantMsg);
  },
};
