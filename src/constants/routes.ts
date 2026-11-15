export const APP_ROUTES = {
  LANDING: '/',
  LOGIN: '/login',
  REGISTER: '/register',
  DASHBOARD: '/dashboard',
  REPOSITORIES: '/repositories',
  REPOSITORIES_ADD: '/repositories/add',
  REPOSITORY_OVERVIEW: '/repositories/:id',
  REPOSITORY_EXPLORER: '/repositories/:id/explorer',
  REPOSITORY_ARCHITECTURE: '/repositories/:id/architecture',
  REPOSITORY_EXECUTION: '/repositories/:id/execution',
  REPOSITORY_DEPENDENCIES: '/repositories/:id/dependencies',
  REPOSITORY_UPDATES: '/repositories/:id/updates',
  REPOSITORY_DOCS: '/repositories/:id/docs',
  REPOSITORY_ASSISTANT: '/repositories/:id/assistant',
  SETTINGS: '/settings',
} as const;

export function getRepositoryRoute(
  id: string,
  section?:
    | 'explorer'
    | 'architecture'
    | 'execution'
    | 'dependencies'
    | 'updates'
    | 'docs'
    | 'assistant'
): string {
  const base = `/repositories/${encodeURIComponent(id)}`;
  return section ? `${base}/${section}` : base;
}
