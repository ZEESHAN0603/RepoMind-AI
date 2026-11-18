import { Eye, EyeOff, Github, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { RepoMindLogo } from '@/components/common/RepoMindLogo';
import { ThemeToggle } from '@/components/common/ThemeToggle';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { APP_ROUTES } from '@/constants/routes';
import { useAuthStore } from '@/stores/auth.store';
import { isValidEmail } from '@/utils/formatters';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, loginWithGitHub, isLoading, error, clearError } = useAuthStore();

  const [email, setEmail] = useState('alex.rivera@repomind.dev');
  const [password, setPassword] = useState('demo-password-123');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);

  const [forgotOpen, setForgotOpen] = useState(false);
  const [resetEmail, setResetEmail] = useState('');
  const [resetSent, setResetSent] = useState(false);

  const redirectTo =
    (location.state as { from?: string } | null)?.from || APP_ROUTES.DASHBOARD;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    clearError();
    setValidationError(null);

    if (!isValidEmail(email)) {
      setValidationError('Please enter a valid email address.');
      return;
    }
    if (password.trim().length < 4) {
      setValidationError('Password must be at least 4 characters.');
      return;
    }

    try {
      await login({ email, password, rememberMe });
      toast.success('Signed in to RepoMind workspace.');
      navigate(redirectTo, { replace: true });
    } catch {
      // Error is handled in store state
    }
  };

  const handleGitHubSignIn = async () => {
    clearError();
    setValidationError(null);
    try {
      await loginWithGitHub();
      toast.success('Connecting with GitHub...');
      navigate(redirectTo, { replace: true });
    } catch {
      // Error is handled in store state
    }
  };

  const handleForgotSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isValidEmail(resetEmail)) {
      toast.error('Enter a valid email address for password recovery.');
      return;
    }
    setResetSent(true);
    toast.success('Sample password reset link simulated.');
  };

  const activeError = validationError || error;

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <header className="flex h-16 items-center justify-between px-4 sm:px-6 border-b border-border">
        <Link to={APP_ROUTES.LANDING}>
          <RepoMindLogo />
        </Link>
        <ThemeToggle />
      </header>

      <main className="flex flex-1 items-center justify-center p-4 sm:p-6">
        <Card className="w-full max-w-md border-border">
          <CardHeader className="space-y-1">
            <CardTitle className="text-xl font-bold tracking-tight">
              Sign in to RepoMind
            </CardTitle>
            <CardDescription>
              Enter your account credentials to access your repositories.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            {activeError && (
              <div
                role="alert"
                className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive"
              >
                {activeError}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="login-email">Email</Label>
                <Input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor="login-password">Password</Label>
                  <button
                    type="button"
                    onClick={() => {
                      setResetEmail(email);
                      setResetSent(false);
                      setForgotOpen(true);
                    }}
                    className="text-xs text-primary hover:underline"
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative">
                  <Input
                    id="login-password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password (type 'error' to test error state)"
                    className="pr-10"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? (
                      <EyeOff className="size-4" />
                    ) : (
                      <Eye className="size-4" />
                    )}
                  </button>
                </div>
              </div>

              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="size-4 rounded border-input accent-primary"
                />
                <span>Remember me on this browser</span>
              </label>

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading && <Loader2 className="mr-2 size-4 animate-spin" />}
                {isLoading ? 'Signing in...' : 'Sign In'}
              </Button>
            </form>

            <div className="relative flex items-center py-1">
              <div className="flex-grow border-t border-border" />
              <span className="mx-3 shrink-0 text-xs text-muted-foreground">
                Or continue with
              </span>
              <div className="flex-grow border-t border-border" />
            </div>

            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={handleGitHubSignIn}
              disabled={isLoading}
            >
              <Github className="mr-2 size-4" />
              Sign in with GitHub
            </Button>
          </CardContent>

          <CardFooter className="justify-center border-t border-border pt-4 text-xs text-muted-foreground">
            <span>
              New to RepoMind?{' '}
              <Link
                to={APP_ROUTES.REGISTER}
                className="font-medium text-primary hover:underline"
              >
                Create an account
              </Link>
            </span>
          </CardFooter>
        </Card>
      </main>

      <Dialog open={forgotOpen} onOpenChange={setForgotOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Reset password (Simulated)</DialogTitle>
            <DialogDescription>
              Enter your account email to simulate sending a password recovery link.
            </DialogDescription>
          </DialogHeader>
          {resetSent ? (
            <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-700 dark:text-emerald-400">
              Sample reset instructions prepared for <strong>{resetEmail}</strong>.
            </div>
          ) : (
            <form onSubmit={handleForgotSubmit} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="reset-email">Account Email</Label>
                <Input
                  id="reset-email"
                  type="email"
                  value={resetEmail}
                  onChange={(e) => setResetEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                />
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setForgotOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit">Send Reset Link</Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
