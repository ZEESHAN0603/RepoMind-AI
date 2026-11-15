import type { ExplorerService } from '@/services/api/intelligence.service';
import type { FileIntelligence, RepositoryFileNode } from '@/types';
import { simulateNetworkDelay } from './delay';

const DEFAULT_TREE: RepositoryFileNode[] = [
  {
    id: 'folder-src',
    name: 'src',
    path: 'src',
    type: 'folder',
    children: [
      {
        id: 'folder-routes',
        name: 'routes',
        path: 'src/routes',
        type: 'folder',
        children: [
          {
            id: 'file-proxy-router',
            name: 'proxy.router.ts',
            path: 'src/routes/proxy.router.ts',
            type: 'file',
            language: 'typescript',
            sizeBytes: 2840,
          },
          {
            id: 'file-auth-router',
            name: 'auth.router.ts',
            path: 'src/routes/auth.router.ts',
            type: 'file',
            language: 'typescript',
            sizeBytes: 1960,
          },
        ],
      },
      {
        id: 'folder-middleware',
        name: 'middleware',
        path: 'src/middleware',
        type: 'folder',
        children: [
          {
            id: 'file-auth-middleware',
            name: 'auth.middleware.ts',
            path: 'src/middleware/auth.middleware.ts',
            type: 'file',
            language: 'typescript',
            sizeBytes: 3120,
          },
          {
            id: 'file-error-middleware',
            name: 'error.middleware.ts',
            path: 'src/middleware/error.middleware.ts',
            type: 'file',
            language: 'typescript',
            sizeBytes: 1410,
          },
        ],
      },
      {
        id: 'folder-services',
        name: 'services',
        path: 'src/services',
        type: 'folder',
        children: [
          {
            id: 'file-rate-limiter',
            name: 'rate-limiter.service.ts',
            path: 'src/services/rate-limiter.service.ts',
            type: 'file',
            language: 'typescript',
            sizeBytes: 2490,
          },
          {
            id: 'file-session-service',
            name: 'session.service.ts',
            path: 'src/services/session.service.ts',
            type: 'file',
            language: 'typescript',
            sizeBytes: 2150,
          },
          {
            id: 'file-token-validator',
            name: 'token-validator.service.ts',
            path: 'src/services/token-validator.service.ts',
            type: 'file',
            language: 'typescript',
            sizeBytes: 1840,
          },
        ],
      },
      {
        id: 'file-server',
        name: 'server.ts',
        path: 'src/server.ts',
        type: 'file',
        language: 'typescript',
        sizeBytes: 1620,
      },
    ],
  },
  {
    id: 'file-package-json',
    name: 'package.json',
    path: 'package.json',
    type: 'file',
    language: 'json',
    sizeBytes: 980,
  },
  {
    id: 'file-readme',
    name: 'README.md',
    path: 'README.md',
    type: 'file',
    language: 'markdown',
    sizeBytes: 1520,
  },
];

const FILE_INTELLIGENCE_MAP: Record<string, FileIntelligence> = {
  'src/middleware/auth.middleware.ts': {
    path: 'src/middleware/auth.middleware.ts',
    language: 'typescript',
    confidence: 'verified',
    explanation:
      'Sample analysis: This Express middleware extracts Bearer JWT tokens from incoming requests, delegates cryptographic verification to verifyToken(), checks active session revocation via SessionStore, and attaches the authenticated TenantContext onto req.auth.',
    relatedFiles: [
      'src/services/token-validator.service.ts',
      'src/services/session.service.ts',
      'src/routes/proxy.router.ts',
    ],
    dependencies: [
      'express',
      '../services/token-validator.service',
      '../services/session.service',
    ],
    sourceReferences: [
      { label: 'Token header extraction', line: 14 },
      { label: 'Session revocation lookup', line: 27 },
      { label: 'Tenant context attachment', line: 34 },
    ],
    symbols: [
      {
        id: 'sym-require-auth',
        name: 'requireAuth',
        kind: 'function',
        startLine: 11,
        endLine: 41,
        signature:
          'export async function requireAuth(req: Request, res: Response, next: NextFunction): Promise<void>',
        summary:
          'Validates Authorization header, verifies JWT claims, and blocks revoked sessions with HTTP 401.',
        confidence: 'verified',
      },
      {
        id: 'sym-extract-bearer',
        name: 'extractBearerToken',
        kind: 'function',
        startLine: 43,
        endLine: 51,
        signature:
          'function extractBearerToken(headerValue?: string): string | null',
        summary:
          'Parses "Bearer <token>" scheme safely without throwing on malformed headers.',
        confidence: 'verified',
      },
    ],
    content: `import type { NextFunction, Request, Response } from 'express';
import { verifyJwtClaims } from '../services/token-validator.service';
import { sessionService } from '../services/session.service';

export interface AuthenticatedRequest extends Request {
  auth?: {
    userId: string;
    tenantId: string;
    scopes: string[];
  };
}

export async function requireAuth(
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): Promise<void> {
  const token = extractBearerToken(req.headers.authorization);
  if (!token) {
    res.status(401).json({ error: 'Missing bearer authorization token' });
    return;
  }

  try {
    const claims = await verifyJwtClaims(token);
    const isRevoked = await sessionService.isTokenRevoked(claims.jti);
    if (isRevoked) {
      res.status(401).json({ error: 'Session has been revoked' });
      return;
    }

    req.auth = {
      userId: claims.sub,
      tenantId: claims.tenantId,
      scopes: claims.scopes,
    };
    next();
  } catch (error) {
    next(error);
  }
}

function extractBearerToken(headerValue?: string): string | null {
  if (!headerValue) return null;
  const [scheme, credentials] = headerValue.split(' ');
  if (scheme?.toLowerCase() !== 'bearer' || !credentials) {
    return null;
  }
  return credentials.trim();
}
`,
  },

  'src/routes/proxy.router.ts': {
    path: 'src/routes/proxy.router.ts',
    language: 'typescript',
    confidence: 'verified',
    explanation:
      'Sample analysis: Defines the primary API gateway forwarding router. Every proxied route passes sequentially through requireAuth and tenantRateLimit before dispatching to upstream targets.',
    relatedFiles: [
      'src/middleware/auth.middleware.ts',
      'src/services/rate-limiter.service.ts',
      'src/server.ts',
    ],
    dependencies: [
      'express',
      '../middleware/auth.middleware',
      '../services/rate-limiter.service',
    ],
    sourceReferences: [
      { label: 'Middleware chain registration', line: 10 },
      { label: 'Upstream cluster resolution', line: 18 },
    ],
    symbols: [
      {
        id: 'sym-proxy-router',
        name: 'proxyRouter',
        kind: 'endpoint',
        startLine: 8,
        endLine: 33,
        signature: 'export const proxyRouter: Router',
        summary: 'Mounts /v1/:service/* wildcard route with auth + rate limiting.',
        confidence: 'verified',
      },
      {
        id: 'sym-resolve-upstream',
        name: 'resolveUpstreamTarget',
        kind: 'function',
        startLine: 35,
        endLine: 44,
        signature: 'function resolveUpstreamTarget(serviceKey: string): string | null',
        summary: 'Looks up static upstream base URL for a given service key.',
        confidence: 'inferred',
      },
    ],
    content: `import { Router } from 'express';
import { requireAuth, type AuthenticatedRequest } from '../middleware/auth.middleware';
import { tenantRateLimit } from '../services/rate-limiter.service';

export const proxyRouter = Router();

const UPSTREAM_REGISTRY: Record<string, string> = {
  billing: 'http://billing-service.internal:4100',
  analytics: 'http://analytics-service.internal:4200',
};

proxyRouter.all(
  '/v1/:service/*',
  requireAuth,
  tenantRateLimit,
  async (req: AuthenticatedRequest, res) => {
    const serviceKey = req.params.service;
    const targetBase = resolveUpstreamTarget(serviceKey);

    if (!targetBase) {
      res.status(404).json({ error: \`Unknown upstream service: \${serviceKey}\` });
      return;
    }

    res.json({
      proxiedTo: targetBase,
      tenantId: req.auth?.tenantId ?? null,
      path: req.path,
    });
  }
);

function resolveUpstreamTarget(serviceKey: string): string | null {
  return UPSTREAM_REGISTRY[serviceKey] ?? null;
}
`,
  },

  'src/services/rate-limiter.service.ts': {
    path: 'src/services/rate-limiter.service.ts',
    language: 'typescript',
    confidence: 'verified',
    explanation:
      'Sample analysis: Implements per-tenant sliding-window rate limiting. Attaches X-RateLimit-Remaining response headers and returns HTTP 429 when tenant quota is exceeded.',
    relatedFiles: ['src/routes/proxy.router.ts', 'src/middleware/auth.middleware.ts'],
    dependencies: ['express'],
    sourceReferences: [
      { label: 'Quota evaluation', line: 17 },
      { label: '429 rejection branch', line: 24 },
    ],
    symbols: [
      {
        id: 'sym-tenant-rate-limit',
        name: 'tenantRateLimit',
        kind: 'function',
        startLine: 11,
        endLine: 32,
        signature:
          'export async function tenantRateLimit(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void>',
        summary: 'Checks sliding-window quota per tenantId before forwarding.',
        confidence: 'verified',
      },
    ],
    content: `import type { NextFunction, Response } from 'express';
import type { AuthenticatedRequest } from '../middleware/auth.middleware';

const WINDOW_LIMIT = 120;
const tenantHitCounters = new Map<string, number>();

export async function tenantRateLimit(
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): Promise<void> {
  const tenantId = req.auth?.tenantId ?? 'anonymous';
  const currentCount = (tenantHitCounters.get(tenantId) ?? 0) + 1;
  tenantHitCounters.set(tenantId, currentCount);

  const remaining = Math.max(0, WINDOW_LIMIT - currentCount);
  res.setHeader('X-RateLimit-Remaining', String(remaining));

  if (currentCount > WINDOW_LIMIT) {
    res.status(429).json({
      error: 'Tenant request quota exceeded',
      retryAfterSeconds: 60,
    });
    return;
  }

  next();
}
`,
  },

  'src/services/session.service.ts': {
    path: 'src/services/session.service.ts',
    language: 'typescript',
    confidence: 'inferred',
    explanation:
      'Sample analysis: Maintains active user sessions and revokes tokens on logout. Note: imports token-validator.service, forming part of a sample circular dependency chain.',
    relatedFiles: [
      'src/services/token-validator.service.ts',
      'src/middleware/auth.middleware.ts',
    ],
    dependencies: ['./token-validator.service'],
    sourceReferences: [{ label: 'Revocation check', line: 13 }],
    symbols: [
      {
        id: 'sym-session-service-obj',
        name: 'SessionService',
        kind: 'class',
        startLine: 5,
        endLine: 25,
        signature: 'export class SessionService',
        summary: 'Tracks revoked token JTIs and rotates refresh sessions.',
        confidence: 'verified',
      },
    ],
    content: `import { normalizeTokenId } from './token-validator.service';

const revokedTokenIds = new Set<string>();

export class SessionService {
  async isTokenRevoked(jti: string): Promise<boolean> {
    const normalized = normalizeTokenId(jti);
    return revokedTokenIds.has(normalized);
  }

  async revokeToken(jti: string): Promise<void> {
    const normalized = normalizeTokenId(jti);
    revokedTokenIds.add(normalized);
  }
}

export const sessionService = new SessionService();
`,
  },

  'src/services/token-validator.service.ts': {
    path: 'src/services/token-validator.service.ts',
    language: 'typescript',
    confidence: 'verified',
    explanation:
      'Sample analysis: Validates JWT payloads and normalizes token identifiers. Imports SessionService for fallback key lookup, illustrating a mutual import cycle.',
    relatedFiles: ['src/services/session.service.ts', 'src/middleware/auth.middleware.ts'],
    dependencies: ['./session.service'],
    sourceReferences: [{ label: 'JWT verification entrypoint', line: 10 }],
    symbols: [
      {
        id: 'sym-verify-jwt',
        name: 'verifyJwtClaims',
        kind: 'function',
        startLine: 10,
        endLine: 22,
        signature: 'export async function verifyJwtClaims(token: string): Promise<JwtClaims>',
        summary: 'Parses and verifies token claims (sample implementation).',
        confidence: 'verified',
      },
    ],
    content: `export interface JwtClaims {
  sub: string;
  jti: string;
  tenantId: string;
  scopes: string[];
}

export function normalizeTokenId(jti: string): string {
  return jti.trim().toLowerCase();
}

export async function verifyJwtClaims(token: string): Promise<JwtClaims> {
  if (!token || token.length < 10) {
    throw new Error('Invalid JWT format');
  }
  return {
    sub: 'usr_104',
    jti: 'tok_98f1',
    tenantId: 'ten_acme',
    scopes: ['gateway:read', 'gateway:write'],
  };
}
`,
  },

  'src/server.ts': {
    path: 'src/server.ts',
    language: 'typescript',
    confidence: 'verified',
    explanation:
      'Sample analysis: Express server entry point registering JSON parsing, proxy routes, and centralized error middleware.',
    relatedFiles: ['src/routes/proxy.router.ts', 'src/middleware/error.middleware.ts'],
    dependencies: ['express', './routes/proxy.router', './middleware/error.middleware'],
    sourceReferences: [{ label: 'Router mount', line: 8 }],
    symbols: [
      {
        id: 'sym-bootstrap',
        name: 'createApp',
        kind: 'function',
        startLine: 5,
        endLine: 14,
        signature: 'export function createApp()',
        summary: 'Configures and returns the Express application instance.',
        confidence: 'verified',
      },
    ],
    content: `import express from 'express';
import { proxyRouter } from './routes/proxy.router';
import { errorHandler } from './middleware/error.middleware';

export function createApp() {
  const app = express();
  app.use(express.json());
  app.use('/api', proxyRouter);
  app.use(errorHandler);
  return app;
}
`,
  },
};

export const mockExplorerService: ExplorerService = {
  async getFileTree(_repositoryId: string) {
    await simulateNetworkDelay(200);
    return DEFAULT_TREE;
  },

  async getFileIntelligence(_repositoryId: string, filePath: string) {
    await simulateNetworkDelay(200);
    const matched = FILE_INTELLIGENCE_MAP[filePath];
    if (matched) {
      return matched;
    }

    const extension = filePath.split('.').pop() ?? 'text';
    const languageMap: Record<string, string> = {
      ts: 'typescript',
      tsx: 'typescript',
      js: 'javascript',
      py: 'python',
      go: 'go',
      json: 'json',
      md: 'markdown',
    };

    return {
      path: filePath,
      language: languageMap[extension] ?? 'plaintext',
      confidence: 'inferred',
      explanation: `Sample Phase 1 explanation for "${filePath}". Detailed static symbol extraction will be generated by the Phase 3 code intelligence engine.`,
      relatedFiles: ['src/server.ts', 'src/routes/proxy.router.ts'],
      dependencies: ['express'],
      sourceReferences: [{ label: 'File header', line: 1 }],
      symbols: [
        {
          id: `sym-default-${filePath}`,
          name: filePath.split('/').pop() ?? 'module',
          kind: 'function',
          startLine: 1,
          endLine: 12,
          signature: `// Sample preview for ${filePath}`,
          summary: 'Placeholder sample symbol metadata.',
          confidence: 'unknown',
        },
      ],
      content: `// Sample file preview: ${filePath}\n// Phase 1 frontend uses mock repository contents.\n\nexport const SAMPLE_FILE_PATH = '${filePath}';\n`,
    };
  },
};
