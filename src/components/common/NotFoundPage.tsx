import { ArrowLeft, FileQuestion } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { APP_ROUTES } from '@/constants/routes';
import { cn } from '@/lib/utils';

interface NotFoundPageProps {
  embedded?: boolean;
}

export function NotFoundPage({ embedded = false }: NotFoundPageProps) {
  return (
    <main
      className={cn(
        'bg-background text-foreground flex items-center justify-center p-6',
        embedded ? 'min-h-[60vh]' : 'min-h-screen'
      )}
    >
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-8 text-center space-y-4">
        <div className="mx-auto flex size-12 items-center justify-center rounded-lg border border-border bg-muted text-muted-foreground">
          <FileQuestion className="size-6" />
        </div>
        <div className="space-y-1.5">
          <p className="font-mono text-xs text-muted-foreground">404</p>
          <h1 className="font-heading text-xl font-bold">Page not found</h1>
          <p className="text-sm text-muted-foreground">
            The route you requested does not exist or may have been moved.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Button asChild variant="outline" size="sm">
            <Link to={embedded ? APP_ROUTES.REPOSITORIES : APP_ROUTES.LANDING}>
              <ArrowLeft className="mr-1.5 size-4" />
              {embedded ? 'View Repositories' : 'Back to Home'}
            </Link>
          </Button>
          <Button asChild size="sm">
            <Link to={APP_ROUTES.DASHBOARD}>Open Dashboard</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}

