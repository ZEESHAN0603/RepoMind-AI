import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  CheckCircle2,
  FileArchive,
  GitBranch,
  Loader2,
  Lock,
  Trash2,
  Upload,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { getRepositoryRoute } from '@/constants/routes';
import { cn } from '@/lib/utils';
import { repositoryService } from '@/services';
import type { Repository } from '@/types';
import { formatBytes, parseGitHubUrl } from '@/utils/formatters';

const ANALYSIS_STAGES = [
  'Validating repository',
  'Extracting files',
  'Detecting languages',
  'Building project structure',
  'Analyzing dependencies',
  'Preparing repository intelligence',
];

export function AddRepositoryPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const initialTab = searchParams.get('tab') === 'zip' ? 'zip' : 'github';
  const [activeTab, setActiveTab] = useState<'github' | 'zip'>(initialTab);

  // GitHub form state
  const [repoUrl, setRepoUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [isPrivate, setIsPrivate] = useState(false);
  const [urlError, setUrlError] = useState<string | null>(null);

  // ZIP upload state
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [zipError, setZipError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  // Simulated analysis state
  const [analyzing, setAnalyzing] = useState(false);
  const [currentStageIndex, setCurrentStageIndex] = useState(-1);
  const [completedRepo, setCompletedRepo] = useState<Repository | null>(null);

  useEffect(() => {
    const paramTab = searchParams.get('tab');
    if (paramTab === 'zip' || paramTab === 'github') {
      setActiveTab(paramTab);
    }
  }, [searchParams]);

  const addMutation = useMutation({
    mutationFn: repositoryService.addRepository,
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      setCompletedRepo(created);
      setAnalyzing(false);
      toast.success(`Repository "${created.name}" connected and queued for indexing.`);
    },
    onError: (err) => {
      setAnalyzing(false);
      toast.error(
        err instanceof Error ? err.message : 'Repository connection failed.'
      );
    },
  });

  const uploadZipMutation = useMutation({
    mutationFn: ({ file, name }: { file: File; name?: string }) => {
      if (repositoryService.uploadRepositoryZip) {
        return repositoryService.uploadRepositoryZip(file, name);
      }
      return repositoryService.addRepository({
        url: `zip://${file.name}`,
        branch: 'main',
        name,
        isPrivate: true,
        sourceType: 'zip',
      });
    },
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      setCompletedRepo(created);
      setAnalyzing(false);
      toast.success(`Repository archive "${created.name}" uploaded and queued for indexing.`);
    },
    onError: (err) => {
      setAnalyzing(false);
      toast.error(
        err instanceof Error ? err.message : 'ZIP archive upload failed.'
      );
    },
  });

  const handleGitHubSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setUrlError(null);
    const parsed = parseGitHubUrl(repoUrl);
    if (!parsed) {
      setUrlError(
        'Enter a valid GitHub repository URL (e.g. https://github.com/owner/repo).'
      );
      return;
    }

    setCompletedRepo(null);
    setAnalyzing(true);
    addMutation.mutate({
      name: parsed.name,
      owner: parsed.owner,
      url: parsed.normalizedUrl,
      branch,
      isPrivate,
      sourceType: 'github',
    });
  };

  const validateAndSelectZip = (file: File) => {
    setZipError(null);
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setZipError('Only .zip repository archives are supported.');
      return;
    }
    setZipFile(file);
    setUploadProgress(100);
  };

  const handleZipSubmit = () => {
    if (!zipFile) {
      setZipError('Please select a .zip archive first.');
      return;
    }

    const cleanName = zipFile.name.replace(/\.zip$/i, '');
    setCompletedRepo(null);
    setAnalyzing(true);
    uploadZipMutation.mutate({ file: zipFile, name: cleanName });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-heading text-2xl font-bold tracking-tight">
          Add Repository
        </h1>
        <p className="text-sm text-muted-foreground">
          Connect a GitHub repository URL or upload a ZIP archive to index your codebase.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Ingestion Source</CardTitle>
              <CardDescription>
                Choose how you want to load a sample repository into RepoMind
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs
                value={activeTab}
                onValueChange={(val) => setActiveTab(val as 'github' | 'zip')}
              >
                <TabsList className="grid w-full grid-cols-2 mb-5">
                  <TabsTrigger value="github">GitHub Repository</TabsTrigger>
                  <TabsTrigger value="zip">ZIP Upload</TabsTrigger>
                </TabsList>

                <TabsContent value="github">
                  <form onSubmit={handleGitHubSubmit} className="space-y-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="github-repo-url">Repository URL</Label>
                      <Input
                        id="github-repo-url"
                        type="url"
                        value={repoUrl}
                        onChange={(e) => {
                          setRepoUrl(e.target.value);
                          if (urlError) setUrlError(null);
                        }}
                        placeholder="https://github.com/acme-platform/payment-api"
                        className="font-mono text-sm"
                        disabled={analyzing}
                      />
                      {urlError && (
                        <p role="alert" className="text-xs text-destructive">
                          {urlError}
                        </p>
                      )}
                    </div>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <Label htmlFor="branch-select">Default Branch</Label>
                        <Select
                          value={branch}
                          onValueChange={setBranch}
                          disabled={analyzing}
                        >
                          <SelectTrigger id="branch-select">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="main">main</SelectItem>
                            <SelectItem value="develop">develop</SelectItem>
                            <SelectItem value="staging">staging</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="flex items-center justify-between rounded-lg border border-border px-3.5 py-2.5">
                        <div className="space-y-0.5">
                          <Label
                            htmlFor="private-toggle"
                            className="flex items-center gap-1.5 text-xs font-medium"
                          >
                            <Lock className="size-3.5 text-muted-foreground" />
                            Private Repository
                          </Label>
                          <p className="text-[11px] text-muted-foreground">
                            Simulates authorized GitHub access
                          </p>
                        </div>
                        <Switch
                          id="private-toggle"
                          checked={isPrivate}
                          onCheckedChange={setIsPrivate}
                          disabled={analyzing}
                        />
                      </div>
                    </div>

                    {isPrivate && (
                      <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                        In Phase 2, private repositories will use least-privilege
                        GitHub OAuth tokens managed server-side.
                      </div>
                    )}

                    <Button
                      type="submit"
                      disabled={analyzing}
                      className="w-full sm:w-auto"
                    >
                      {analyzing ? (
                        <>
                          <Loader2 className="mr-2 size-4 animate-spin" />
                          Simulating Analysis...
                        </>
                      ) : (
                        <>
                          <GitBranch className="mr-2 size-4" />
                          Connect Repository
                        </>
                      )}
                    </Button>
                  </form>
                </TabsContent>

                <TabsContent value="zip" className="space-y-4">
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDragging(true);
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDragging(false);
                      const file = e.dataTransfer.files?.[0];
                      if (file) validateAndSelectZip(file);
                    }}
                    onClick={() => fileInputRef.current?.click()}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        fileInputRef.current?.click();
                      }
                    }}
                    className={cn(
                      'flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center cursor-pointer transition-colors',
                      isDragging
                        ? 'border-primary bg-accent/40'
                        : 'border-border hover:border-primary/60 hover:bg-muted/30'
                    )}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".zip,application/zip"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) validateAndSelectZip(file);
                      }}
                    />
                    <Upload className="mb-3 size-7 text-muted-foreground" />
                    <p className="text-sm font-medium text-foreground">
                      Drop a repository .zip file here, or click to browse
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Accepts standard .zip repository archives up to 50MB
                    </p>
                  </div>

                  {zipError && (
                    <p role="alert" className="text-xs text-destructive">
                      {zipError}
                    </p>
                  )}

                  {zipFile && (
                    <div className="rounded-lg border border-border bg-muted/30 p-3.5 space-y-2.5">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <FileArchive className="size-4 text-primary shrink-0" />
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-foreground">
                              {zipFile.name}
                            </p>
                            <p className="font-mono text-xs text-muted-foreground">
                              {formatBytes(zipFile.size)}
                            </p>
                          </div>
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => {
                            setZipFile(null);
                            setUploadProgress(0);
                            if (fileInputRef.current) {
                              fileInputRef.current.value = '';
                            }
                          }}
                          aria-label="Remove uploaded file"
                          disabled={analyzing}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>

                      <div className="space-y-1">
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>Simulated Archive Staging</span>
                          <span className="font-mono tabular-nums">
                            {uploadProgress}%
                          </span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full bg-primary transition-[width] duration-200"
                            style={{ width: `${uploadProgress}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  <Button
                    type="button"
                    onClick={handleZipSubmit}
                    disabled={analyzing || !zipFile}
                    className="w-full sm:w-auto"
                  >
                    {analyzing ? (
                      <>
                        <Loader2 className="mr-2 size-4 animate-spin" />
                        Simulating Analysis...
                      </>
                    ) : (
                      'Start Simulated Analysis'
                    )}
                  </Button>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>

        {/* Simulated Analysis Progress Panel */}
        <div className="lg:col-span-5">
          <Card className="h-full">
            <CardHeader>
              <CardTitle className="text-base">
                Analysis Pipeline (Simulated)
              </CardTitle>
              <CardDescription>
                Mock indexing stages executed after submitting a repository
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <ol className="space-y-2.5">
                {ANALYSIS_STAGES.map((stage, index) => {
                  const isDone =
                    Boolean(completedRepo) ||
                    (analyzing && index < currentStageIndex);
                  const isActive = analyzing && index === currentStageIndex;

                  return (
                    <li
                      key={stage}
                      className={cn(
                        'flex items-center justify-between rounded-md border px-3 py-2 text-xs transition-colors',
                        isDone
                          ? 'border-emerald-500/30 bg-emerald-500/5 text-foreground'
                          : isActive
                            ? 'border-primary/50 bg-accent/50 text-foreground'
                            : 'border-border text-muted-foreground'
                      )}
                    >
                      <span className="flex items-center gap-2.5">
                        <span className="font-mono text-[11px] tabular-nums">
                          0{index + 1}.
                        </span>
                        <span className="font-medium">{stage}</span>
                      </span>
                      {isDone ? (
                        <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
                      ) : isActive ? (
                        <Loader2 className="size-4 text-primary animate-spin shrink-0" />
                      ) : (
                        <span className="text-[11px] text-muted-foreground">
                          Queued
                        </span>
                      )}
                    </li>
                  );
                })}
              </ol>

              {completedRepo && (
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 space-y-3">
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-foreground">
                      {completedRepo.owner}/{completedRepo.name} ready
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Sample intelligence workspace prepared on branch{' '}
                      <code className="font-mono">{completedRepo.branch}</code>.
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => navigate(getRepositoryRoute(completedRepo.id))}
                    className="w-full"
                  >
                    Open Repository Overview
                    <ArrowRight className="ml-1.5 size-4" />
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
