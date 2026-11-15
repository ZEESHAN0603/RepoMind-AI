import type { ExecutionService } from '@/services/api/intelligence.service';
import type {
  ExecutionEntryGraph,
  ExecutionFlow,
  ExecutionFunctionSymbol,
  ExecutionGraphEdge,
  ExecutionGraphNode,
  ExecutionTraceWorkspace,
} from '@/types';
import { simulateNetworkDelay } from './delay';

const SAMPLE_FUNCTIONS: ExecutionFunctionSymbol[] = [
  {
    id: 'fn-login-trigger',
    name: 'User Login',
    filePath: 'src/client/auth-form.tsx',
    lineNumber: 18,
    nodeType: 'function',
    parameters: '(credentials: LoginCredentials)',
    returnType: 'Promise<AuthSession>',
    description:
      'Submits user email and password payload from the frontend login form to the gateway authentication endpoint.',
    status: 'inferred',
    callers: [],
    callees: ['fn-login-api'],
    relatedFunctions: ['Login API', 'Return Response'],
    codeSnippet: `export async function submitUserLogin(credentials: LoginCredentials): Promise<AuthSession> {
  const res = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  });
  return res.json();
}`,
  },
  {
    id: 'fn-login-api',
    name: 'Login API',
    filePath: 'src/routes/auth.router.ts',
    lineNumber: 14,
    nodeType: 'api',
    parameters: '(req: Request, res: Response, next: NextFunction)',
    returnType: 'Promise<void>',
    description:
      'Express POST /api/v1/auth/login route entry point handling schema validation and forwarding to AuthController.',
    status: 'verified',
    callers: ['fn-login-trigger'],
    callees: ['fn-auth-controller'],
    relatedFunctions: ['User Login', 'Auth Controller'],
    codeSnippet: `authRouter.post('/login', async (req, res, next) => {
  try {
    const result = await authController.login(req.body);
    res.status(200).json(result);
  } catch (err) {
    next(err);
  }
});`,
  },
  {
    id: 'fn-auth-controller',
    name: 'Auth Controller',
    filePath: 'src/controllers/auth.controller.ts',
    lineNumber: 22,
    nodeType: 'method',
    parameters: '(payload: { email: string; password: string })',
    returnType: 'Promise<LoginResponseDto>',
    description:
      'Orchestrates credential verification, user profile loading, JWT issuance, and standardized HTTP response construction.',
    status: 'verified',
    callers: ['fn-login-api'],
    callees: ['fn-validate-credentials', 'fn-generate-jwt', 'fn-return-response'],
    relatedFunctions: ['Validate Credentials', 'Generate JWT', 'Return Response'],
    codeSnippet: `async login(payload: LoginInput): Promise<LoginResponseDto> {
  const user = await this.validateCredentials(payload.email, payload.password);
  const token = await this.jwtService.generateJwt(user);
  return this.buildLoginResponse(user, token);
}`,
  },
  {
    id: 'fn-validate-credentials',
    name: 'Validate Credentials',
    filePath: 'src/controllers/auth.controller.ts',
    lineNumber: 46,
    nodeType: 'method',
    parameters: '(email: string, password: string)',
    returnType: 'Promise<AuthenticatedUser>',
    description:
      'Verifies password hash integrity against the persisted account fetched by UserService.',
    status: 'verified',
    callers: ['fn-auth-controller'],
    callees: ['fn-user-service'],
    relatedFunctions: ['Auth Controller', 'User Service'],
    codeSnippet: `private async validateCredentials(email: string, password: string) {
  const user = await userService.findByEmail(email);
  if (!user || !(await comparePassword(password, user.passwordHash))) {
    throw new UnauthorizedError('Invalid credentials');
  }
  return user;
}`,
  },
  {
    id: 'fn-user-service',
    name: 'User Service',
    filePath: 'src/services/user.service.ts',
    lineNumber: 19,
    nodeType: 'method',
    parameters: '(email: string)',
    returnType: 'Promise<UserRecord | null>',
    description:
      'Normalizes email identifier and queries the primary user repository with tenant scoping.',
    status: 'verified',
    callers: ['fn-validate-credentials'],
    callees: ['fn-database-query'],
    relatedFunctions: ['Validate Credentials', 'Database Query'],
    codeSnippet: `async findByEmail(email: string): Promise<UserRecord | null> {
  const normalized = email.trim().toLowerCase();
  return this.db.queryUserByEmail(normalized);
}`,
  },
  {
    id: 'fn-database-query',
    name: 'Database Query',
    filePath: 'src/db/user.repository.ts',
    lineNumber: 28,
    nodeType: 'database',
    parameters: '(normalizedEmail: string)',
    returnType: 'Promise<UserRecord | null>',
    description:
      'Executes parameterized SQL SELECT against users and permissions tables.',
    status: 'verified',
    callers: ['fn-user-service'],
    callees: [],
    relatedFunctions: ['User Service'],
    codeSnippet: `async queryUserByEmail(email: string): Promise<UserRecord | null> {
  const rows = await pool.query(
    'SELECT id, email, password_hash, role FROM users WHERE email = $1 LIMIT 1',
    [email]
  );
  return rows[0] ?? null;
}`,
  },
  {
    id: 'fn-generate-jwt',
    name: 'Generate JWT',
    filePath: 'src/services/token-validator.service.ts',
    lineNumber: 54,
    nodeType: 'function',
    parameters: '(user: AuthenticatedUser)',
    returnType: 'Promise<SignedToken>',
    description:
      'Signs RS256 access token with sub, role, tenantId, and unique JTI claim for revocation tracking.',
    status: 'verified',
    callers: ['fn-auth-controller'],
    callees: ['fn-return-response'],
    relatedFunctions: ['Auth Controller', 'SessionService.isTokenRevoked'],
    codeSnippet: `export async function generateJwt(user: AuthenticatedUser): Promise<SignedToken> {
  const jti = crypto.randomUUID();
  return signToken({ sub: user.id, role: user.role, jti }, { expiresIn: '15m' });
}`,
  },
  {
    id: 'fn-return-response',
    name: 'Return Response',
    filePath: 'src/controllers/auth.controller.ts',
    lineNumber: 71,
    nodeType: 'function',
    parameters: '(user: AuthenticatedUser, token: SignedToken)',
    returnType: 'LoginResponseDto',
    description:
      'Strips sensitive credential hashes and serializes token + session expiry metadata.',
    status: 'verified',
    callers: ['fn-auth-controller', 'fn-generate-jwt'],
    callees: [],
    relatedFunctions: ['Auth Controller', 'Generate JWT'],
    codeSnippet: `buildLoginResponse(user: AuthenticatedUser, token: SignedToken): LoginResponseDto {
  return {
    accessToken: token.value,
    expiresAt: token.expiresAt,
    user: { id: user.id, email: user.email, role: user.role },
  };
}`,
  },
  {
    id: 'fn-create-app',
    name: 'createApp',
    filePath: 'src/server.ts',
    lineNumber: 8,
    nodeType: 'function',
    parameters: '()',
    returnType: 'Express.Application',
    description:
      'Bootstraps Express application, configures JSON middleware, and mounts /api proxy routes.',
    status: 'verified',
    callers: [],
    callees: ['fn-proxy-router'],
    relatedFunctions: ['proxyRouter', 'requireAuth'],
    codeSnippet: `export function createApp() {
  const app = express();
  app.use(express.json());
  app.use('/api', proxyRouter);
  return app;
}`,
  },
  {
    id: 'fn-proxy-router',
    name: 'proxyRouter',
    filePath: 'src/routes/proxy.router.ts',
    lineNumber: 12,
    nodeType: 'api',
    parameters: '(req: AuthenticatedRequest, res: Response)',
    returnType: 'Promise<void>',
    description:
      'Dispatches /v1/:service/* requests through authentication, tenant rate limiting, and upstream forwarding.',
    status: 'verified',
    callers: ['fn-create-app'],
    callees: ['fn-require-auth', 'fn-tenant-rate-limit', 'fn-resolve-upstream'],
    relatedFunctions: ['requireAuth', 'tenantRateLimit', 'resolveUpstreamTarget'],
    codeSnippet: `proxyRouter.all('/v1/:service/*', requireAuth, tenantRateLimit, async (req, res) => {
  const target = resolveUpstreamTarget(req.params.service);
  return upstreamHttpForward(target, req, res);
});`,
  },
  {
    id: 'fn-require-auth',
    name: 'requireAuth',
    filePath: 'src/middleware/auth.middleware.ts',
    lineNumber: 13,
    nodeType: 'function',
    parameters: '(req: Request, res: Response, next: NextFunction)',
    returnType: 'Promise<void>',
    description:
      'Extracts Bearer token, validates JWT claims, and confirms the token JTI has not been revoked.',
    status: 'verified',
    callers: ['fn-proxy-router'],
    callees: ['fn-verify-jwt', 'fn-is-token-revoked'],
    relatedFunctions: ['verifyJwtClaims', 'SessionService.isTokenRevoked'],
    codeSnippet: `export async function requireAuth(req: Request, res: Response, next: NextFunction) {
  const token = extractBearerToken(req.headers.authorization);
  const claims = verifyJwtClaims(token);
  if (await sessionService.isTokenRevoked(claims.jti)) {
    return res.status(401).json({ error: 'Token revoked' });
  }
  req.auth = claims;
  next();
}`,
  },
  {
    id: 'fn-verify-jwt',
    name: 'verifyJwtClaims',
    filePath: 'src/services/token-validator.service.ts',
    lineNumber: 12,
    nodeType: 'function',
    parameters: '(token: string)',
    returnType: 'JwtClaims',
    description:
      'Verifies JWT signature, issuer claim, and expiration timestamp; returns decoded sub, jti, and tenantId.',
    status: 'verified',
    callers: ['fn-require-auth'],
    callees: [],
    relatedFunctions: ['requireAuth', 'normalizeTokenId'],
    codeSnippet: `export function verifyJwtClaims(token: string): JwtClaims {
  const payload = decodeAndVerify(token, PUBLIC_KEY);
  if (!payload.sub || !payload.jti) throw new InvalidTokenError();
  return payload;
}`,
  },
  {
    id: 'fn-is-token-revoked',
    name: 'SessionService.isTokenRevoked',
    filePath: 'src/services/session.service.ts',
    lineNumber: 6,
    nodeType: 'database',
    parameters: '(jti: string)',
    returnType: 'Promise<boolean>',
    description:
      'Normalizes token identifier and checks Redis / session revocation store.',
    status: 'verified',
    callers: ['fn-require-auth'],
    callees: ['fn-normalize-token'],
    relatedFunctions: ['normalizeTokenId', 'SessionService.revokeToken'],
    codeSnippet: `async isTokenRevoked(jti: string): Promise<boolean> {
  const key = normalizeTokenId(jti);
  return this.revokedSet.has(key);
}`,
  },
  {
    id: 'fn-tenant-rate-limit',
    name: 'tenantRateLimit',
    filePath: 'src/services/rate-limiter.service.ts',
    lineNumber: 11,
    nodeType: 'function',
    parameters: '(req: AuthenticatedRequest, res: Response, next: NextFunction)',
    returnType: 'Promise<void>',
    description:
      'Increments sliding-window quota counter for req.auth.tenantId and sets X-RateLimit-Remaining.',
    status: 'verified',
    callers: ['fn-proxy-router'],
    callees: [],
    relatedFunctions: ['proxyRouter'],
    codeSnippet: `export function tenantRateLimit(req: AuthenticatedRequest, res: Response, next: NextFunction) {
  const remaining = slidingWindow.consume(req.auth.tenantId);
  res.setHeader('X-RateLimit-Remaining', String(remaining));
  if (remaining < 0) return res.status(429).json({ error: 'Rate limit exceeded' });
  next();
}`,
  },
  {
    id: 'fn-resolve-upstream',
    name: 'resolveUpstreamTarget',
    filePath: 'src/routes/proxy.router.ts',
    lineNumber: 35,
    nodeType: 'function',
    parameters: '(serviceKey: string)',
    returnType: 'string',
    description:
      'Resolves logical service identifier to internal cluster target base URL.',
    status: 'inferred',
    callers: ['fn-proxy-router'],
    callees: ['fn-upstream-forward'],
    relatedFunctions: ['upstreamHttpForward'],
    codeSnippet: `function resolveUpstreamTarget(serviceKey: string): string {
  const target = UPSTREAM_REGISTRY[serviceKey];
  if (!target) throw new UnknownServiceError(serviceKey);
  return target;
}`,
  },
  {
    id: 'fn-upstream-forward',
    name: 'upstreamHttpForward',
    filePath: 'src/routes/proxy.router.ts',
    lineNumber: 24,
    nodeType: 'external',
    parameters: '(targetUrl: string, req: Request, res: Response)',
    returnType: 'Promise<void>',
    description:
      'Forwards request to external microservice cluster outside repository boundary.',
    status: 'unresolved',
    callers: ['fn-resolve-upstream'],
    callees: [],
    relatedFunctions: ['resolveUpstreamTarget'],
    codeSnippet: `async function upstreamHttpForward(targetUrl: string, req: Request, res: Response) {
  // External network call to downstream microservice (outside repo AST)
  return httpClient.pipe(targetUrl + req.path, req, res);
}`,
  },
  {
    id: 'fn-revoke-token',
    name: 'SessionService.revokeToken',
    filePath: 'src/services/session.service.ts',
    lineNumber: 11,
    nodeType: 'method',
    parameters: '(jti: string)',
    returnType: 'Promise<void>',
    description:
      'Invalidates an active session JTI during logout or security rotation.',
    status: 'inferred',
    callers: [],
    callees: ['fn-normalize-token'],
    relatedFunctions: ['normalizeTokenId', 'SessionService.isTokenRevoked'],
    codeSnippet: `async revokeToken(jti: string): Promise<void> {
  const key = normalizeTokenId(jti);
  this.revokedSet.add(key);
}`,
  },
  {
    id: 'fn-normalize-token',
    name: 'normalizeTokenId',
    filePath: 'src/services/token-validator.service.ts',
    lineNumber: 8,
    nodeType: 'function',
    parameters: '(jti: string)',
    returnType: 'string',
    description:
      'Trims whitespace and normalizes JTI strings to lowercase before store lookup.',
    status: 'verified',
    callers: ['fn-is-token-revoked', 'fn-revoke-token'],
    callees: [],
    relatedFunctions: ['verifyJwtClaims'],
    codeSnippet: `export function normalizeTokenId(jti: string): string {
  return jti.trim().toLowerCase();
}`,
  },
];

const FN_MAP = new Map<string, ExecutionFunctionSymbol>(
  SAMPLE_FUNCTIONS.map((f) => [f.id, f])
);

function toGraphNode(
  fnId: string,
  position: { x: number; y: number },
  depth: number
): ExecutionGraphNode {
  const fn = FN_MAP.get(fnId)!;
  return {
    id: fn.id,
    label: fn.name,
    nodeType: fn.nodeType,
    filePath: fn.filePath,
    lineNumber: fn.lineNumber,
    parameters: fn.parameters,
    returnType: fn.returnType,
    description: fn.description,
    status: fn.status,
    callers: fn.callers,
    callees: fn.callees,
    relatedFunctions: fn.relatedFunctions,
    codeSnippet: fn.codeSnippet,
    position,
    depth,
  };
}

function buildUserLoginTrace(): ExecutionEntryGraph {
  const nodes: ExecutionGraphNode[] = [
    toGraphNode('fn-login-trigger', { x: 260, y: 20 }, 0),
    toGraphNode('fn-login-api', { x: 260, y: 140 }, 1),
    toGraphNode('fn-auth-controller', { x: 260, y: 260 }, 2),
    toGraphNode('fn-validate-credentials', { x: 70, y: 390 }, 3),
    toGraphNode('fn-user-service', { x: 70, y: 515 }, 4),
    toGraphNode('fn-database-query', { x: 70, y: 640 }, 5),
    toGraphNode('fn-generate-jwt', { x: 450, y: 390 }, 3),
    toGraphNode('fn-return-response', { x: 450, y: 515 }, 4),
  ];

  const edges: ExecutionGraphEdge[] = [
    {
      id: 'e-login-1',
      source: 'fn-login-trigger',
      target: 'fn-login-api',
      label: 'POST /api/v1/auth/login',
      status: 'inferred',
      dataPassed: '{ email, password }',
    },
    {
      id: 'e-login-2',
      source: 'fn-login-api',
      target: 'fn-auth-controller',
      label: 'authController.login()',
      status: 'verified',
      dataPassed: 'LoginInput',
    },
    {
      id: 'e-login-3',
      source: 'fn-auth-controller',
      target: 'fn-validate-credentials',
      label: 'validateCredentials()',
      status: 'verified',
      dataPassed: 'email, password',
    },
    {
      id: 'e-login-4',
      source: 'fn-validate-credentials',
      target: 'fn-user-service',
      label: 'userService.findByEmail()',
      status: 'verified',
      dataPassed: 'email: string',
    },
    {
      id: 'e-login-5',
      source: 'fn-user-service',
      target: 'fn-database-query',
      label: 'queryUserByEmail()',
      status: 'verified',
      dataPassed: 'SQL SELECT users',
    },
    {
      id: 'e-login-6',
      source: 'fn-auth-controller',
      target: 'fn-generate-jwt',
      label: 'generateJwt()',
      status: 'verified',
      dataPassed: 'AuthenticatedUser',
    },
    {
      id: 'e-login-7',
      source: 'fn-generate-jwt',
      target: 'fn-return-response',
      label: 'buildLoginResponse()',
      status: 'verified',
      dataPassed: 'SignedToken',
    },
    {
      id: 'e-login-8',
      source: 'fn-auth-controller',
      target: 'fn-return-response',
      label: '200 OK DTO',
      status: 'verified',
      dataPassed: 'LoginResponseDto',
    },
  ];

  const flow: ExecutionFlow = {
    id: 'flow-user-login',
    title: 'User Login Authentication Flow',
    triggerType: 'api-endpoint',
    entryPoint: 'POST /api/v1/auth/login',
    summary:
      'Traces a login submission from the client handler through Login API, Auth Controller, credential validation, User Service DB query, JWT signing, and HTTP response.',
    rootNodeId: 'fn-login-trigger',
    steps: [
      {
        stepOrder: 1,
        nodeId: 'fn-login-trigger',
        functionName: 'User Login',
        moduleName: 'AuthForm',
        nodeType: 'function',
        filePath: 'src/client/auth-form.tsx',
        lineNumber: 18,
        caller: 'Browser Form Submit',
        callee: 'Login API',
        dataPassed: 'LoginCredentials',
        description: 'Dispatches POST /api/v1/auth/login request.',
        status: 'inferred',
      },
      {
        stepOrder: 2,
        nodeId: 'fn-login-api',
        functionName: 'Login API',
        moduleName: 'AuthRouter',
        nodeType: 'api',
        filePath: 'src/routes/auth.router.ts',
        lineNumber: 14,
        caller: 'User Login',
        callee: 'Auth Controller',
        dataPassed: 'req.body',
        description: 'Parses request payload and invokes authController.login().',
        status: 'verified',
      },
      {
        stepOrder: 3,
        nodeId: 'fn-auth-controller',
        functionName: 'Auth Controller',
        moduleName: 'AuthController',
        nodeType: 'method',
        filePath: 'src/controllers/auth.controller.ts',
        lineNumber: 22,
        caller: 'Login API',
        callee: 'Validate Credentials',
        dataPassed: 'LoginInput',
        description: 'Coordinates credential check and JWT issuance.',
        status: 'verified',
      },
      {
        stepOrder: 4,
        nodeId: 'fn-validate-credentials',
        functionName: 'Validate Credentials',
        moduleName: 'AuthController',
        nodeType: 'method',
        filePath: 'src/controllers/auth.controller.ts',
        lineNumber: 46,
        caller: 'Auth Controller',
        callee: 'User Service',
        dataPassed: 'email, password',
        description: 'Fetches user record and verifies password hash.',
        status: 'verified',
      },
      {
        stepOrder: 5,
        nodeId: 'fn-user-service',
        functionName: 'User Service',
        moduleName: 'UserService',
        nodeType: 'method',
        filePath: 'src/services/user.service.ts',
        lineNumber: 19,
        caller: 'Validate Credentials',
        callee: 'Database Query',
        dataPassed: 'normalizedEmail',
        description: 'Delegates email lookup to user repository.',
        status: 'verified',
      },
      {
        stepOrder: 6,
        nodeId: 'fn-database-query',
        functionName: 'Database Query',
        moduleName: 'UserRepository',
        nodeType: 'database',
        filePath: 'src/db/user.repository.ts',
        lineNumber: 28,
        caller: 'User Service',
        callee: 'PostgreSQL users',
        dataPassed: 'UserRecord | null',
        description: 'Executes parameterized query on users table.',
        status: 'verified',
      },
      {
        stepOrder: 7,
        nodeId: 'fn-generate-jwt',
        functionName: 'Generate JWT',
        moduleName: 'TokenValidator',
        nodeType: 'function',
        filePath: 'src/services/token-validator.service.ts',
        lineNumber: 54,
        caller: 'Auth Controller',
        callee: 'Return Response',
        dataPassed: 'SignedToken',
        description: 'Signs JWT with JTI claim and expiration.',
        status: 'verified',
      },
      {
        stepOrder: 8,
        nodeId: 'fn-return-response',
        functionName: 'Return Response',
        moduleName: 'AuthController',
        nodeType: 'function',
        filePath: 'src/controllers/auth.controller.ts',
        lineNumber: 71,
        caller: 'Generate JWT',
        callee: 'HTTP 200 JSON',
        dataPassed: 'LoginResponseDto',
        description: 'Returns sanitized session token DTO to client.',
        status: 'verified',
      },
    ],
  };

  return { flow, nodes, edges };
}

function buildProxyAuthTrace(): ExecutionEntryGraph {
  const nodes: ExecutionGraphNode[] = [
    toGraphNode('fn-create-app', { x: 260, y: 20 }, 0),
    toGraphNode('fn-proxy-router', { x: 260, y: 145 }, 1),
    toGraphNode('fn-require-auth', { x: 50, y: 280 }, 2),
    toGraphNode('fn-tenant-rate-limit', { x: 270, y: 280 }, 2),
    toGraphNode('fn-resolve-upstream', { x: 490, y: 280 }, 2),
    toGraphNode('fn-verify-jwt', { x: -30, y: 420 }, 3),
    toGraphNode('fn-is-token-revoked', { x: 185, y: 420 }, 3),
    toGraphNode('fn-upstream-forward', { x: 490, y: 420 }, 3),
    toGraphNode('fn-normalize-token', { x: 185, y: 550 }, 4),
  ];

  const edges: ExecutionGraphEdge[] = [
    {
      id: 'e-proxy-1',
      source: 'fn-create-app',
      target: 'fn-proxy-router',
      label: 'app.use("/api")',
      status: 'verified',
      dataPassed: 'Request, Response',
    },
    {
      id: 'e-proxy-2',
      source: 'fn-proxy-router',
      target: 'fn-require-auth',
      label: 'requireAuth()',
      status: 'verified',
      dataPassed: 'Authorization Header',
    },
    {
      id: 'e-proxy-3',
      source: 'fn-require-auth',
      target: 'fn-verify-jwt',
      label: 'verifyJwtClaims()',
      status: 'verified',
      dataPassed: 'token -> JwtClaims',
    },
    {
      id: 'e-proxy-4',
      source: 'fn-require-auth',
      target: 'fn-is-token-revoked',
      label: 'isTokenRevoked()',
      status: 'verified',
      dataPassed: 'claims.jti',
    },
    {
      id: 'e-proxy-5',
      source: 'fn-is-token-revoked',
      target: 'fn-normalize-token',
      label: 'normalizeTokenId()',
      status: 'verified',
      dataPassed: 'jti: string',
    },
    {
      id: 'e-proxy-6',
      source: 'fn-proxy-router',
      target: 'fn-tenant-rate-limit',
      label: 'tenantRateLimit()',
      status: 'verified',
      dataPassed: 'req.auth.tenantId',
    },
    {
      id: 'e-proxy-7',
      source: 'fn-proxy-router',
      target: 'fn-resolve-upstream',
      label: 'resolveUpstreamTarget()',
      status: 'inferred',
      dataPassed: 'req.params.service',
    },
    {
      id: 'e-proxy-8',
      source: 'fn-resolve-upstream',
      target: 'fn-upstream-forward',
      label: 'upstreamHttpForward()',
      status: 'unresolved',
      dataPassed: 'Proxied HTTP stream',
    },
  ];

  const flow: ExecutionFlow = {
    id: 'flow-proxy-auth',
    title: 'Authenticated API Proxy Request',
    triggerType: 'api-endpoint',
    entryPoint: 'ALL /api/v1/:service/*',
    summary:
      'Traces an incoming client request through Express router matching, JWT verification, session revocation check, per-tenant rate limiting, and external forwarding.',
    rootNodeId: 'fn-create-app',
    steps: [
      {
        stepOrder: 1,
        nodeId: 'fn-create-app',
        functionName: 'createApp',
        moduleName: 'Express Server',
        nodeType: 'function',
        filePath: 'src/server.ts',
        lineNumber: 8,
        caller: 'HTTP Listener',
        callee: 'proxyRouter',
        dataPassed: 'Request, Response',
        description: 'Dispatches /api prefixed traffic into proxyRouter.',
        status: 'verified',
      },
      {
        stepOrder: 2,
        nodeId: 'fn-proxy-router',
        functionName: 'proxyRouter',
        moduleName: 'ProxyRouter',
        nodeType: 'api',
        filePath: 'src/routes/proxy.router.ts',
        lineNumber: 12,
        caller: 'createApp',
        callee: 'requireAuth',
        dataPassed: 'req.params.service',
        description: 'Matches /v1/:service/* and executes middleware chain.',
        status: 'verified',
      },
      {
        stepOrder: 3,
        nodeId: 'fn-require-auth',
        functionName: 'requireAuth',
        moduleName: 'AuthMiddleware',
        nodeType: 'function',
        filePath: 'src/middleware/auth.middleware.ts',
        lineNumber: 13,
        caller: 'proxyRouter',
        callee: 'verifyJwtClaims',
        dataPassed: 'req.headers.authorization',
        description: 'Extracts Bearer token string from Authorization header.',
        status: 'verified',
      },
      {
        stepOrder: 4,
        nodeId: 'fn-verify-jwt',
        functionName: 'verifyJwtClaims',
        moduleName: 'TokenValidator',
        nodeType: 'function',
        filePath: 'src/services/token-validator.service.ts',
        lineNumber: 12,
        caller: 'requireAuth',
        callee: 'verifyJwtClaims',
        dataPassed: 'token -> JwtClaims',
        description: 'Validates JWT structure and decodes sub, jti, and tenantId.',
        status: 'verified',
      },
      {
        stepOrder: 5,
        nodeId: 'fn-is-token-revoked',
        functionName: 'SessionService.isTokenRevoked',
        moduleName: 'SessionStore',
        nodeType: 'database',
        filePath: 'src/services/session.service.ts',
        lineNumber: 6,
        caller: 'requireAuth',
        callee: 'normalizeTokenId',
        dataPassed: 'claims.jti -> boolean',
        description: 'Checks whether token JTI exists in the revocation set.',
        status: 'verified',
      },
      {
        stepOrder: 6,
        nodeId: 'fn-tenant-rate-limit',
        functionName: 'tenantRateLimit',
        moduleName: 'RateLimiter',
        nodeType: 'function',
        filePath: 'src/services/rate-limiter.service.ts',
        lineNumber: 11,
        caller: 'proxyRouter',
        callee: 'tenantRateLimit',
        dataPassed: 'req.auth.tenantId',
        description: 'Increments tenant sliding window and sets X-RateLimit-Remaining.',
        status: 'verified',
      },
      {
        stepOrder: 7,
        nodeId: 'fn-resolve-upstream',
        functionName: 'resolveUpstreamTarget',
        moduleName: 'UpstreamRouter',
        nodeType: 'function',
        filePath: 'src/routes/proxy.router.ts',
        lineNumber: 35,
        caller: 'proxyRouter',
        callee: 'upstreamHttpForward',
        dataPassed: 'serviceKey -> baseUrl',
        description: 'Maps service key to target microservice cluster URL.',
        status: 'inferred',
      },
      {
        stepOrder: 8,
        nodeId: 'fn-upstream-forward',
        functionName: 'upstreamHttpForward',
        moduleName: 'External Cluster',
        nodeType: 'external',
        filePath: 'src/routes/proxy.router.ts',
        lineNumber: 24,
        caller: 'resolveUpstreamTarget',
        callee: 'billing-service.internal',
        dataPassed: 'Proxied HTTP payload',
        description:
          'Downstream microservice execution happens outside this repository boundary.',
        status: 'unresolved',
      },
    ],
  };

  return { flow, nodes, edges };
}

function buildTokenRevocationTrace(): ExecutionEntryGraph {
  const nodes: ExecutionGraphNode[] = [
    toGraphNode('fn-revoke-token', { x: 240, y: 60 }, 0),
    toGraphNode('fn-normalize-token', { x: 240, y: 200 }, 1),
  ];

  const edges: ExecutionGraphEdge[] = [
    {
      id: 'e-revoke-1',
      source: 'fn-revoke-token',
      target: 'fn-normalize-token',
      label: 'normalizeTokenId(jti)',
      status: 'verified',
      dataPassed: 'jti: string',
    },
  ];

  const flow: ExecutionFlow = {
    id: 'flow-token-revocation',
    title: 'Session Token Revocation Flow',
    triggerType: 'function',
    entryPoint: 'SessionService.revokeToken(jti)',
    summary:
      'Traces how a logout or security rotation event normalizes a JWT identifier and invalidates active gateway sessions.',
    rootNodeId: 'fn-revoke-token',
    steps: [
      {
        stepOrder: 1,
        nodeId: 'fn-revoke-token',
        functionName: 'SessionService.revokeToken',
        moduleName: 'SessionStore',
        nodeType: 'method',
        filePath: 'src/services/session.service.ts',
        lineNumber: 11,
        caller: 'authRouter (/logout)',
        callee: 'normalizeTokenId',
        dataPassed: 'jti: string',
        description: 'Receives token identifier from logout handler.',
        status: 'inferred',
      },
      {
        stepOrder: 2,
        nodeId: 'fn-normalize-token',
        functionName: 'normalizeTokenId',
        moduleName: 'TokenValidator',
        nodeType: 'function',
        filePath: 'src/services/token-validator.service.ts',
        lineNumber: 8,
        caller: 'SessionService.revokeToken',
        callee: 'String.prototype.toLowerCase',
        dataPassed: 'normalized jti',
        description: 'Trims and lowercases JTI before storing in revocation set.',
        status: 'verified',
      },
    ],
  };

  return { flow, nodes, edges };
}

export const mockExecutionService: ExecutionService = {
  async getExecutionFlows(repositoryId: string): Promise<ExecutionFlow[]> {
    const workspace = await this.getExecutionWorkspace(repositoryId);
    return workspace.traces.map((t) => t.flow);
  },

  async getExecutionWorkspace(
    repositoryId: string
  ): Promise<ExecutionTraceWorkspace> {
    await simulateNetworkDelay(220);
    return {
      repositoryId,
      repositoryName: repositoryId.replace(/^repo-/, ''),
      functions: structuredClone(SAMPLE_FUNCTIONS),
      traces: [
        buildUserLoginTrace(),
        buildProxyAuthTrace(),
        buildTokenRevocationTrace(),
      ],
    };
  },
};
