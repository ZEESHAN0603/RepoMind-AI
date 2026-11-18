import type { SettingsService } from './intelligence.service';
import type { AppSettings } from '@/types';
import { apiFetch } from './client';

const SETTINGS_STORAGE_KEY = 'repomind-app-settings';

const DEFAULT_SETTINGS: AppSettings = {
  profile: {
    name: 'Developer Workspace',
    email: 'developer@repomind.dev',
    role: 'Lead Architect',
    avatarInitials: 'DW',
  },
  providers: {
    primaryProvider: 'ollama',
    fallbackProvider: 'gemini',
    ollamaEndpoint: 'https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech',
    ollamaStatus: 'connected',
    geminiConfigured: true,
    geminiStatus: 'connected',
  },
  models: {
    generationModel: 'qwen3.5:4b',
    embeddingModel: 'nomic-embed-text',
    temperature: 0.2,
    maxContextTokens: 4096,
  },
  preferences: {
    defaultBranch: 'main',
    autoAnalyzeOnConnect: true,
    includeDevDependencies: true,
  },
};

export class ApiSettingsService implements SettingsService {
  async getSettings(): Promise<AppSettings> {
    let settings = { ...DEFAULT_SETTINGS };

    if (typeof window !== 'undefined') {
      try {
        const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
        if (raw) {
          settings = { ...settings, ...JSON.parse(raw) };
        }
      } catch {
        // Keep defaults
      }
    }

    // Attempt to query live backend AI health
    try {
      const res = await apiFetch('/health/ai-providers');
      if (res.ok) {
        const data = await res.json();
        const ollamaInfo = data.providers?.ollama;
        const geminiInfo = data.providers?.gemini;

        settings.providers.primaryProvider = data.primary_provider || 'ollama';
        settings.providers.fallbackProvider = data.fallback_provider || 'gemini';

        if (ollamaInfo) {
          settings.providers.ollamaStatus = ollamaInfo.is_available ? 'connected' : 'unreachable';
        }
        if (geminiInfo) {
          settings.providers.geminiConfigured = Boolean(geminiInfo.is_available);
          settings.providers.geminiStatus = geminiInfo.is_available ? 'connected' : 'unconfigured';
        }
      }
    } catch {
      // Backend might be offline; return stored settings
    }

    return settings;
  }

  async updateSettings(partial: Partial<AppSettings>): Promise<AppSettings> {
    const current = await this.getSettings();
    const updated: AppSettings = {
      ...current,
      ...partial,
      profile: { ...current.profile, ...partial.profile },
      providers: { ...current.providers, ...partial.providers },
      models: { ...current.models, ...partial.models },
      preferences: { ...current.preferences, ...partial.preferences },
    };

    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(updated));
    }

    return updated;
  }

  async testProviderConnection(
    provider: 'ollama' | 'gemini'
  ): Promise<{ ok: boolean; latencyMs: number; message: string }> {
    try {
      const res = await apiFetch('/health/ai-providers');
      if (!res.ok) {
        return {
          ok: false,
          latencyMs: 0,
          message: `Health check failed with status ${res.status}: ${res.statusText}`,
        };
      }

      const data = await res.json();
      const info = data.providers?.[provider];

      if (!info) {
        return {
          ok: false,
          latencyMs: 0,
          message: `Provider '${provider}' not found in backend configuration.`,
        };
      }

      return {
        ok: info.is_available,
        latencyMs: info.latency_ms || 0,
        message: info.is_available
          ? `Connected to ${provider} (${info.latency_ms}ms latency). Available models: ${info.available_models?.slice(0, 3).join(', ') || 'ready'}`
          : info.error_message || `Could not connect to ${provider} provider.`,
      };
    } catch (err) {
      return {
        ok: false,
        latencyMs: 0,
        message: `Network error connecting to backend health check: ${err instanceof Error ? err.message : String(err)}`,
      };
    }
  }
}

export const apiSettingsService = new ApiSettingsService();
