import { create } from 'zustand';
import type { AppSettings } from '@/types';

const DEFAULT_SETTINGS: AppSettings = {
  profile: {
    name: 'Alex Rivera',
    email: 'alex.rivera@repomind.dev',
    role: 'Staff Software Architect',
    avatarInitials: 'AR',
  },
  providers: {
    primaryProvider: 'ollama',
    fallbackProvider: 'gemini',
    ollamaEndpoint: 'http://localhost:11434',
    ollamaStatus: 'connected',
    geminiConfigured: true,
    geminiStatus: 'connected',
  },
  models: {
    generationModel: 'qwen2.5-coder:7b',
    embeddingModel: 'nomic-embed-text',
    temperature: 0.2,
    maxContextTokens: 8192,
  },
  preferences: {
    defaultBranch: 'main',
    autoAnalyzeOnConnect: true,
    includeDevDependencies: false,
  },
};

interface SettingsState {
  settings: AppSettings;
  updateProfile: (profile: Partial<AppSettings['profile']>) => void;
  updateProviders: (providers: Partial<AppSettings['providers']>) => void;
  updateModels: (models: Partial<AppSettings['models']>) => void;
  updatePreferences: (
    preferences: Partial<AppSettings['preferences']>
  ) => void;
  resetSettings: () => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: DEFAULT_SETTINGS,
  updateProfile: (profile) =>
    set((state) => ({
      settings: {
        ...state.settings,
        profile: { ...state.settings.profile, ...profile },
      },
    })),
  updateProviders: (providers) =>
    set((state) => ({
      settings: {
        ...state.settings,
        providers: { ...state.settings.providers, ...providers },
      },
    })),
  updateModels: (models) =>
    set((state) => ({
      settings: {
        ...state.settings,
        models: { ...state.settings.models, ...models },
      },
    })),
  updatePreferences: (preferences) =>
    set((state) => ({
      settings: {
        ...state.settings,
        preferences: { ...state.settings.preferences, ...preferences },
      },
    })),
  resetSettings: () => set({ settings: DEFAULT_SETTINGS }),
}));
