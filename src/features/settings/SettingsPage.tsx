import { useMutation } from '@tanstack/react-query';
import {
  CheckCircle2,
  Cpu,
  KeyRound,
  Loader2,
  Moon,
  RotateCcw,
  Save,
  Shield,
  Sun,
  User,
} from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { SampleDataBanner } from '@/components/common/SampleDataBanner';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';
import { settingsService } from '@/services';
import { useSettingsStore } from '@/stores/settings.store';
import { useThemeStore } from '@/stores/theme.store';
import type { AIProviderType } from '@/types';
import { isValidEmail } from '@/utils/formatters';

export function SettingsPage() {
  const { theme, setTheme } = useThemeStore();
  const {
    settings,
    updateProfile,
    updateProviders,
    updateModels,
    updatePreferences,
    resetSettings,
  } = useSettingsStore();

  const [name, setName] = useState(settings.profile.name);
  const [email, setEmail] = useState(settings.profile.email);
  const [role, setRole] = useState(settings.profile.role);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [resetOpen, setResetOpen] = useState(false);

  const [providerTestMsg, setProviderTestMsg] = useState<string | null>(null);
  const [mockTokenActive, setMockTokenActive] = useState(true);

  const testMutation = useMutation({
    mutationFn: (provider: 'ollama' | 'gemini') =>
      settingsService.testProviderConnection(provider),
    onSuccess: (result) => {
      setProviderTestMsg(`${result.message} (${result.latencyMs}ms)`);
      toast.success('Simulated provider check succeeded.');
    },
    onError: () => toast.error('Simulated provider check failed.'),
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      settingsService.updateSettings({
        profile: {
          ...settings.profile,
          name: name.trim(),
          email: email.trim(),
          role: role.trim(),
        },
      }),
    onSuccess: () => {
      toast.success('Workspace settings saved (Phase 1 mock state).');
    },
  });

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    setProfileError(null);
    if (name.trim().length < 2) {
      setProfileError('Name must be at least 2 characters.');
      return;
    }
    if (!isValidEmail(email)) {
      setProfileError('Enter a valid email address.');
      return;
    }
    updateProfile({
      name: name.trim(),
      email: email.trim(),
      role: role.trim(),
    });
    saveMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">
            Settings
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage profile, theme appearance, AI provider routing, and repository
            preferences.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setResetOpen(true)}
          className="w-fit whitespace-nowrap shrink-0"
        >
          <RotateCcw className="mr-1.5 size-3.5" />
          Reset Defaults
        </Button>
      </div>

      <SampleDataBanner message="Phase 1 Mock Settings — Provider and token controls preview future backend configuration. Never enter or store real API secrets in frontend local storage." />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-6">
          {/* Profile */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <User className="size-4 text-primary" />
                Developer Profile
              </CardTitle>
              <CardDescription>
                Display identity for your local workspace session
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSaveProfile} className="space-y-4">
                <div className="flex items-center gap-3.5 pb-1">
                  <div className="flex size-12 items-center justify-center rounded-lg bg-primary/15 text-base font-bold text-primary">
                    {settings.profile.avatarInitials}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    <p className="font-medium text-foreground">{name}</p>
                    <p>{role}</p>
                  </div>
                </div>

                {profileError && (
                  <p role="alert" className="text-xs text-destructive">
                    {profileError}
                  </p>
                )}

                <div className="space-y-1.5">
                  <Label htmlFor="settings-name">Full Name</Label>
                  <Input
                    id="settings-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="settings-email">Email</Label>
                  <Input
                    id="settings-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="settings-role">Role</Label>
                  <Input
                    id="settings-role"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  />
                </div>

                <Button
                  type="submit"
                  size="sm"
                  disabled={saveMutation.isPending}
                >
                  {saveMutation.isPending ? (
                    <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                  ) : (
                    <Save className="mr-1.5 size-3.5" />
                  )}
                  Save Profile
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Appearance */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Appearance</CardTitle>
              <CardDescription>
                Theme preference is persisted automatically in local storage
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setTheme('dark')}
                className={cn(
                  'flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors',
                  theme === 'dark'
                    ? 'border-primary bg-accent/40'
                    : 'border-border hover:bg-muted/40'
                )}
              >
                <div className="flex w-full items-center justify-between">
                  <Moon className="size-4 text-primary" />
                  {theme === 'dark' && (
                    <CheckCircle2 className="size-4 text-primary" />
                  )}
                </div>
                <div>
                  <p className="text-sm font-semibold">Dark Theme</p>
                  <p className="text-xs text-muted-foreground">
                    Charcoal surfaces with indigo highlights
                  </p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setTheme('light')}
                className={cn(
                  'flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors',
                  theme === 'light'
                    ? 'border-primary bg-accent/40'
                    : 'border-border hover:bg-muted/40'
                )}
              >
                <div className="flex w-full items-center justify-between">
                  <Sun className="size-4 text-primary" />
                  {theme === 'light' && (
                    <CheckCircle2 className="size-4 text-primary" />
                  )}
                </div>
                <div>
                  <p className="text-sm font-semibold">Light Theme</p>
                  <p className="text-xs text-muted-foreground">
                    Crisp off-white canvas with high contrast
                  </p>
                </div>
              </button>
            </CardContent>
          </Card>

          {/* Repository Preferences */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Repository Preferences</CardTitle>
              <CardDescription>
                Default ingestion and static analysis options
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="pref-branch">Default Branch</Label>
                <Select
                  value={settings.preferences.defaultBranch}
                  onValueChange={(val) =>
                    updatePreferences({ defaultBranch: val })
                  }
                >
                  <SelectTrigger id="pref-branch">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="main">main</SelectItem>
                    <SelectItem value="master">master</SelectItem>
                    <SelectItem value="develop">develop</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between rounded-lg border border-border px-3.5 py-2.5">
                <div>
                  <p className="text-xs font-medium text-foreground">
                    Auto-analyze on repository connect
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Begin indexing immediately after GitHub URL or ZIP submission
                  </p>
                </div>
                <Switch
                  checked={settings.preferences.autoAnalyzeOnConnect}
                  onCheckedChange={(val) =>
                    updatePreferences({ autoAnalyzeOnConnect: val })
                  }
                />
              </div>

              <div className="flex items-center justify-between rounded-lg border border-border px-3.5 py-2.5">
                <div>
                  <p className="text-xs font-medium text-foreground">
                    Include external devDependencies
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Surface build tooling packages inside dependency summaries
                  </p>
                </div>
                <Switch
                  checked={settings.preferences.includeDevDependencies}
                  onCheckedChange={(val) =>
                    updatePreferences({ includeDevDependencies: val })
                  }
                />
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-6">
          {/* AI Providers */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Cpu className="size-4 text-primary" />
                AI Providers (Planned Routing)
              </CardTitle>
              <CardDescription>
                Configure primary local Ollama and fallback Gemini provider behavior
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="primary-provider">Primary Provider</Label>
                  <Select
                    value={settings.providers.primaryProvider}
                    onValueChange={(val) =>
                      updateProviders({ primaryProvider: val as AIProviderType })
                    }
                  >
                    <SelectTrigger id="primary-provider">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ollama">Ollama (Local)</SelectItem>
                      <SelectItem value="gemini">Gemini API</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="fallback-provider">Fallback Provider</Label>
                  <Select
                    value={settings.providers.fallbackProvider}
                    onValueChange={(val) =>
                      updateProviders({
                        fallbackProvider: val as AIProviderType | 'none',
                      })
                    }
                  >
                    <SelectTrigger id="fallback-provider">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gemini">Gemini API</SelectItem>
                      <SelectItem value="ollama">Ollama (Local)</SelectItem>
                      <SelectItem value="none">Disabled</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="rounded-lg border border-border bg-background p-3.5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold">
                    Ollama Local Endpoint
                  </span>
                  <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                    Mock Connected
                  </span>
                </div>
                <Input
                  value={settings.providers.ollamaEndpoint}
                  onChange={(e) =>
                    updateProviders({ ollamaEndpoint: e.target.value })
                  }
                  className="font-mono text-xs"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  onClick={() => testMutation.mutate('ollama')}
                  disabled={testMutation.isPending}
                >
                  Test Ollama Check (Simulated)
                </Button>
              </div>

              <div className="rounded-lg border border-border bg-background p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold">
                    Gemini API Fallback
                  </span>
                  <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                    Server-Side Key Planned
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  API credentials are managed strictly on the backend environment in
                  Phase 4 (`GEMINI_API_KEY`) and are never stored in browser storage.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  onClick={() => testMutation.mutate('gemini')}
                  disabled={testMutation.isPending}
                >
                  Test Gemini Adapter (Simulated)
                </Button>
              </div>

              {providerTestMsg && (
                <p className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-400">
                  {providerTestMsg}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Model Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Model Configuration</CardTitle>
              <CardDescription>
                Separate generation and embedding models for RAG indexing
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="gen-model">Generation Model</Label>
                  <Select
                    value={settings.models.generationModel}
                    onValueChange={(val) =>
                      updateModels({ generationModel: val })
                    }
                  >
                    <SelectTrigger id="gen-model">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="qwen2.5-coder:7b">
                        qwen2.5-coder:7b
                      </SelectItem>
                      <SelectItem value="deepseek-coder-v2:16b">
                        deepseek-coder-v2:16b
                      </SelectItem>
                      <SelectItem value="gemini-2.5-flash">
                        gemini-2.5-flash
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="embed-model">Embedding Model</Label>
                  <Select
                    value={settings.models.embeddingModel}
                    onValueChange={(val) =>
                      updateModels({ embeddingModel: val })
                    }
                  >
                    <SelectTrigger id="embed-model">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="nomic-embed-text">
                        nomic-embed-text
                      </SelectItem>
                      <SelectItem value="mxbai-embed-large">
                        mxbai-embed-large
                      </SelectItem>
                      <SelectItem value="text-embedding-004">
                        text-embedding-004
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <Label htmlFor="temp-range">Sampling Temperature</Label>
                  <span className="font-mono font-medium tabular-nums">
                    {settings.models.temperature.toFixed(1)}
                  </span>
                </div>
                <input
                  id="temp-range"
                  type="range"
                  min={0}
                  max={1}
                  step={0.1}
                  value={settings.models.temperature}
                  onChange={(e) =>
                    updateModels({ temperature: Number(e.target.value) })
                  }
                  className="w-full accent-primary"
                />
                <p className="text-[11px] text-muted-foreground">
                  Lower values (0.1–0.3) keep code explanations deterministic.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Privacy & Access */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Shield className="size-4 text-primary" />
                Privacy & Access Controls
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs text-muted-foreground">
              <div className="flex items-center justify-between rounded-lg border border-border px-3.5 py-2.5">
                <div className="flex items-center gap-2.5">
                  <KeyRound className="size-4 text-muted-foreground shrink-0" />
                  <div>
                    <p className="font-medium text-foreground">
                      GitHub Access Token (Mock Preview)
                    </p>
                    <p className="text-[11px]">
                      {mockTokenActive
                        ? 'Simulated read-only repo scope active'
                        : 'Simulated token revoked'}
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant={mockTokenActive ? 'outline' : 'default'}
                  size="xs"
                  onClick={() => {
                    setMockTokenActive((prev) => !prev);
                    toast.info(
                      mockTokenActive
                        ? 'Mock GitHub token revoked.'
                        : 'Mock GitHub token reconnected.'
                    );
                  }}
                >
                  {mockTokenActive ? 'Revoke' : 'Reconnect'}
                </Button>
              </div>

              <p className="leading-relaxed">
                Phase 1 runs entirely in the browser with sample mock datasets. When
                the backend is introduced in Phase 2+, repository ingestion will
                validate ZIP boundaries, isolate tenants, and redact secrets before
                indexing.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={resetOpen}
        onOpenChange={setResetOpen}
        title="Reset workspace settings?"
        description="This restores AI provider, model, and repository preferences to their Phase 1 defaults."
        confirmLabel="Reset Settings"
        onConfirm={() => {
          resetSettings();
          setResetOpen(false);
          toast.success('Settings restored to defaults.');
        }}
      />
    </div>
  );
}
