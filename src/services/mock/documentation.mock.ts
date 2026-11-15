import type { DocumentationService } from '@/services/api/intelligence.service';
import type { DocSectionType, DocumentationDocument } from '@/types';
import { simulateNetworkDelay } from './delay';

function buildDefaultDocs(repositoryId: string): DocumentationDocument[] {
  const now = new Date().toISOString();
  return [
    {
      id: `${repositoryId}-readme`,
      repositoryId,
      type: 'readme',
      title: 'README Overview',
      description: 'Project purpose, quickstart commands, and environment overview.',
      lastUpdated: now,
      confidence: 'verified',
      content: `# Cloud Gateway (Sample Documentation)

> **Note:** This Markdown document is sample Phase 1 preview content generated for demonstration.

An edge API gateway built with Express and TypeScript that verifies JWT bearer tokens, enforces per-tenant rate limits, and forwards requests to upstream clusters.

## Key Capabilities

- **Token Verification**: Validates incoming JWT claims in \`src/middleware/auth.middleware.ts\`.
- **Session Revocation**: Checks revoked token identifiers via \`SessionService\`.
- **Tenant Quotas**: Applies sliding-window limits in \`src/services/rate-limiter.service.ts\`.

## Quickstart

\`\`\`bash
npm install
npm run dev
\`\`\`
`,
    },
    {
      id: `${repositoryId}-architecture`,
      repositoryId,
      type: 'architecture',
      title: 'Architecture Documentation',
      description: 'Layered system boundaries, request flow diagram, and component roles.',
      lastUpdated: now,
      confidence: 'verified',
      content: `# System Architecture

The gateway enforces authentication and tenant rate limiting before routing requests upstream.

\`\`\`mermaid
flowchart LR
  Client[Web Client] --> Gateway[Express Server]
  Gateway --> Router[Proxy Router]
  Router --> Auth[AuthMiddleware]
  Auth --> Token[TokenValidator]
  Auth --> Session[SessionStore]
  Router --> Rate[Tenant Rate Limiter]
\`\`\`

## Layer Responsibilities

1. **Ingress Layer (\`src/server.ts\`)**: Configures JSON parsing and mounts \`/api\`.
2. **Security Middleware (\`src/middleware/auth.middleware.ts\`)**: Attaches \`req.auth\` tenant context.
3. **Policy Services (\`src/services/\`)**: Enforces rate limits and revocation checks.
`,
    },
    {
      id: `${repositoryId}-module`,
      repositoryId,
      type: 'module',
      title: 'Module Documentation',
      description: 'Detailed breakdown of core internal modules and exported symbols.',
      lastUpdated: now,
      confidence: 'inferred',
      content: `# Core Module Reference

## \`src/middleware/auth.middleware.ts\`

- **\`requireAuth(req, res, next)\`**: Async Express middleware enforcing Bearer JWT authorization.
- **\`extractBearerToken(headerValue)\`**: Safe header parser returning \`null\` on malformed schemes.

## \`src/services/rate-limiter.service.ts\`

- **\`tenantRateLimit(req, res, next)\`**: Tracks per-tenant requests against \`WINDOW_LIMIT = 120\` and writes \`X-RateLimit-Remaining\`.
`,
    },
    {
      id: `${repositoryId}-api`,
      repositoryId,
      type: 'api',
      title: 'API Documentation',
      description: 'HTTP endpoints, auth headers, and status codes.',
      lastUpdated: now,
      confidence: 'verified',
      content: `# API Endpoints

## \`ALL /api/v1/:service/*\`

Forwards authenticated tenant traffic to registered upstream clusters.

### Headers

| Header | Required | Description |
|---|---|---|
| \`Authorization\` | Yes | \`Bearer <jwt>\` issued by auth provider |

### Responses

- **\`200 OK\`**: Upstream payload forwarded with \`X-RateLimit-Remaining\` header.
- **\`401 Unauthorized\`**: Missing token or revoked session.
- **\`429 Too Many Requests\`**: Tenant quota exceeded.
`,
    },
    {
      id: `${repositoryId}-database`,
      repositoryId,
      type: 'database',
      title: 'Database Documentation',
      description: 'Session revocation schema and tenant quota storage design.',
      lastUpdated: now,
      confidence: 'inferred',
      content: `# Data & State Storage

\`\`\`mermaid
erDiagram
  TENANTS ||--o{ SESSIONS : owns
  SESSIONS {
    string jti PK
    string user_id
    string tenant_id
    boolean revoked
    timestamp expires_at
  }
\`\`\`

> **Confidence Note**: Persistence table relationships are **inferred** from \`SessionService\` method signatures in Phase 1 sample data.
`,
    },
    {
      id: `${repositoryId}-onboarding`,
      repositoryId,
      type: 'onboarding',
      title: 'Developer Onboarding',
      description: 'Checklist for new engineers joining the repository.',
      lastUpdated: now,
      confidence: 'inferred',
      content: `# Developer Onboarding Guide

1. **Inspect Entry Point**: Start with \`src/server.ts\` to see middleware registration order.
2. **Review Auth Flow**: Read \`src/middleware/auth.middleware.ts\` and \`src/services/token-validator.service.ts\`.
3. **Watch Out for Known Cycles**: \`SessionService\` and \`TokenValidator\` share a circular import tracked in Dependency Analysis.
`,
    },
  ];
}

const docsStore: Record<string, DocumentationDocument[]> = {};

export const mockDocumentationService: DocumentationService = {
  async getDocuments(repositoryId: string) {
    await simulateNetworkDelay(220);
    if (!docsStore[repositoryId]) {
      docsStore[repositoryId] = buildDefaultDocs(repositoryId);
    }
    return docsStore[repositoryId].map((d) => ({ ...d }));
  },

  async saveDocument(repositoryId: string, type: DocSectionType, content: string) {
    await simulateNetworkDelay(200);
    const list = docsStore[repositoryId] ?? buildDefaultDocs(repositoryId);
    let updatedDoc: DocumentationDocument | undefined;
    docsStore[repositoryId] = list.map((doc) => {
      if (doc.type === type) {
        updatedDoc = {
          ...doc,
          content,
          lastUpdated: new Date().toISOString(),
        };
        return updatedDoc;
      }
      return doc;
    });
    if (!updatedDoc) {
      throw new Error(`Document type "${type}" not found.`);
    }
    return { ...updatedDoc };
  },

  async regenerateDocument(repositoryId: string, type: DocSectionType) {
    await simulateNetworkDelay(550);
    const defaults = buildDefaultDocs(repositoryId);
    const fresh = defaults.find((d) => d.type === type);
    if (!fresh) {
      throw new Error(`Document type "${type}" not found.`);
    }
    const list = docsStore[repositoryId] ?? defaults;
    const regenerated: DocumentationDocument = {
      ...fresh,
      lastUpdated: new Date().toISOString(),
    };
    docsStore[repositoryId] = list.map((doc) =>
      doc.type === type ? regenerated : doc
    );
    return { ...regenerated };
  },
};
