export type AIProviderType = 'ollama' | 'gemini';
export type ProviderStatus = 'connected' | 'unreachable' | 'unconfigured';

export interface UserProfile {
  name: string;
  email: string;
  role: string;
  avatarInitials: string;
}

export interface AIProviderSettings {
  primaryProvider: AIProviderType;
  fallbackProvider: AIProviderType | 'none';
  ollamaEndpoint: string;
  ollamaStatus: ProviderStatus;
  geminiConfigured: boolean;
  geminiStatus: ProviderStatus;
}

export interface ModelConfig {
  generationModel: string;
  embeddingModel: string;
  temperature: number;
  maxContextTokens: number;
}

export interface RepositoryPreferences {
  defaultBranch: string;
  autoAnalyzeOnConnect: boolean;
  includeDevDependencies: boolean;
}

export interface AppSettings {
  profile: UserProfile;
  providers: AIProviderSettings;
  models: ModelConfig;
  preferences: RepositoryPreferences;
}
