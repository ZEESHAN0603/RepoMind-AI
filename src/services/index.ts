import type {
  ArchitectureService,
  AssistantService,
  AuthService,
  DependencyService,
  DocumentationService,
  ExecutionService,
  ExplorerService,
  SettingsService,
  UpdatesService,
} from './api/intelligence.service';
import type { RepositoryService } from './api/repository.service';
import { apiRepositoryService } from './api/repository.api';
import { apiAssistantService } from './api/assistant.api';
import { apiArchitectureService } from './api/architecture.api';
import { apiExecutionService } from './api/execution.api';
import { apiDependencyService } from './api/dependency.api';
import { mockArchitectureService } from './mock/architecture.mock';
import { mockAssistantService } from './mock/assistant.mock';
import { mockAuthService } from './mock/auth.mock';
import { mockDependencyService } from './mock/dependency.mock';
import { mockDocumentationService } from './mock/documentation.mock';
import { mockExecutionService } from './mock/execution.mock';
import { mockExplorerService } from './mock/explorer.mock';
import { mockRepositoryService } from './mock/repository.mock';
import { mockSettingsService } from './mock/settings.mock';
import { mockUpdatesService } from './mock/updates.mock';

// Service registry: Real API repository service backed by Phase 3 backend endpoints
export const repositoryService: RepositoryService = apiRepositoryService;
export const explorerService: ExplorerService = mockExplorerService;
export const architectureService: ArchitectureService = apiArchitectureService;
export const executionService: ExecutionService = apiExecutionService;
export const dependencyService: DependencyService = apiDependencyService;
export const updatesService: UpdatesService = mockUpdatesService;
export const documentationService: DocumentationService = mockDocumentationService;
export const assistantService: AssistantService = apiAssistantService;
export const settingsService: SettingsService = mockSettingsService;
export const authService: AuthService = mockAuthService;
