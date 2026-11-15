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

// Service registry: Phase 2 replaces mock implementations here without modifying UI code.
export const repositoryService: RepositoryService = mockRepositoryService;
export const explorerService: ExplorerService = mockExplorerService;
export const architectureService: ArchitectureService = mockArchitectureService;
export const executionService: ExecutionService = mockExecutionService;
export const dependencyService: DependencyService = mockDependencyService;
export const updatesService: UpdatesService = mockUpdatesService;
export const documentationService: DocumentationService = mockDocumentationService;
export const assistantService: AssistantService = mockAssistantService;
export const settingsService: SettingsService = mockSettingsService;
export const authService: AuthService = mockAuthService;
