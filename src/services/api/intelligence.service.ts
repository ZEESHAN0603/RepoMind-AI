import type {
  AppSettings,
  ArchitectureGraphData,
  AssistantConversation,
  AssistantMessage,
  AuthUser,
  DependencyAnalysisData,
  DocSectionType,
  DocumentationDocument,
  ExecutionExplanationResponse,
  ExecutionFlow,
  ExecutionTraceWorkspace,
  FileIntelligence,
  LoginCredentials,
  RegisterPayload,
  RepositoryFileNode,
  RepositoryUpdatesData,
} from '@/types';

export interface ExplorerService {
  getFileTree(repositoryId: string): Promise<RepositoryFileNode[]>;
  getFileIntelligence(
    repositoryId: string,
    filePath: string
  ): Promise<FileIntelligence>;
}

export interface ArchitectureService {
  getArchitectureGraph(repositoryId: string): Promise<ArchitectureGraphData>;
}

export interface ExecutionService {
  getExecutionFlows(repositoryId: string): Promise<ExecutionFlow[]>;
  getExecutionWorkspace(repositoryId: string): Promise<ExecutionTraceWorkspace>;
  explainExecutionFlow?(
    repositoryId: string,
    payload: { flowId?: string; symbolId?: string; focusQuestion?: string }
  ): Promise<ExecutionExplanationResponse>;
  analyzeExecution?(repositoryId: string): Promise<any>;
}

export interface DependencyService {
  getDependencyAnalysis(repositoryId: string): Promise<DependencyAnalysisData>;
  refreshDependencyAnalysis(repositoryId: string): Promise<DependencyAnalysisData>;
}

export interface UpdatesService {
  getRepositoryUpdates(repositoryId: string): Promise<RepositoryUpdatesData>;
  triggerIncrementalReindex(repositoryId: string): Promise<RepositoryUpdatesData>;
  getUpdateRunDetail?(repositoryId: string, runId: string): Promise<any>;
  generateExplanation?(repositoryId: string, runId: string, focus?: string): Promise<string>;
  compareVersions?(repositoryId: string, baseSha?: string, targetSha?: string): Promise<any>;
}

export interface DocumentationService {
  getDocuments(repositoryId: string): Promise<DocumentationDocument[]>;
  saveDocument(
    repositoryId: string,
    type: DocSectionType,
    content: string
  ): Promise<DocumentationDocument>;
  regenerateDocument(
    repositoryId: string,
    type: DocSectionType
  ): Promise<DocumentationDocument>;
}

export interface AssistantService {
  getConversations(repositoryId: string): Promise<AssistantConversation[]>;
  getSuggestedQuestions(repositoryId: string): Promise<string[]>;
  sendMessage(
    repositoryId: string,
    conversationId: string,
    prompt: string
  ): Promise<AssistantMessage>;
}

export interface SettingsService {
  getSettings(): Promise<AppSettings>;
  updateSettings(partial: Partial<AppSettings>): Promise<AppSettings>;
  testProviderConnection(
    provider: 'ollama' | 'gemini'
  ): Promise<{ ok: boolean; latencyMs: number; message: string }>;
}

export interface AuthService {
  login(credentials: LoginCredentials): Promise<AuthUser>;
  loginWithGitHub(): Promise<AuthUser>;
  register(payload: RegisterPayload): Promise<AuthUser>;
  logout(): Promise<void>;
}
