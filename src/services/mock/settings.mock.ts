import type { SettingsService } from '@/services/api/intelligence.service';
import { useSettingsStore } from '@/stores/settings.store';
import type { AppSettings } from '@/types';
import { simulateNetworkDelay } from './delay';

export const mockSettingsService: SettingsService = {
  async getSettings(): Promise<AppSettings> {
    await simulateNetworkDelay(150);
    return structuredClone(useSettingsStore.getState().settings);
  },

  async updateSettings(partial: Partial<AppSettings>): Promise<AppSettings> {
    await simulateNetworkDelay(220);
    const store = useSettingsStore.getState();
    if (partial.profile) store.updateProfile(partial.profile);
    if (partial.providers) store.updateProviders(partial.providers);
    if (partial.models) store.updateModels(partial.models);
    if (partial.preferences) store.updatePreferences(partial.preferences);
    return structuredClone(useSettingsStore.getState().settings);
  },

  async testProviderConnection(provider: 'ollama' | 'gemini') {
    await simulateNetworkDelay(450);
    if (provider === 'ollama') {
      return {
        ok: true,
        latencyMs: 38,
        message: 'Sample check: Local Ollama endpoint responded (Phase 1 mock check).',
      };
    }
    return {
      ok: true,
      latencyMs: 112,
      message: 'Sample check: Gemini fallback adapter is ready (Phase 1 mock check).',
    };
  },
};
