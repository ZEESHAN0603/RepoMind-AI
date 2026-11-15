import { lazy, Suspense } from 'react';
import {
  createBrowserRouter,
  isRouteErrorResponse,
  Link,
  RouterProvider,
  useRouteError,
} from 'react-router-dom';
import { AuthGuard } from '@/components/common/AuthGuard';
import { ErrorState } from '@/components/common/ErrorState';
import { NotFoundPage } from '@/components/common/NotFoundPage';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { APP_ROUTES } from '@/constants/routes';
import { LoginPage } from '@/features/auth/LoginPage';
import { RegisterPage } from '@/features/auth/RegisterPage';
import { DashboardPage } from '@/features/dashboard/DashboardPage';
import { LandingPage } from '@/features/landing/LandingPage';
import { AddRepositoryPage } from '@/features/repositories/AddRepositoryPage';
import { RepositoriesPage } from '@/features/repositories/RepositoriesPage';
import { RepositoryOverviewPage } from '@/features/repositories/RepositoryOverviewPage';
import { SettingsPage } from '@/features/settings/SettingsPage';

// Lazy-load heavier visualization and editor routes for fast initial load
const ExplorerPage = lazy(() =>
  import('@/features/explorer/ExplorerPage').then((m) => ({
    default: m.ExplorerPage,
  }))
);
const ArchitecturePage = lazy(() =>
  import('@/features/architecture/ArchitecturePage').then((m) => ({
    default: m.ArchitecturePage,
  }))
);
const ExecutionPage = lazy(() =>
  import('@/features/execution/ExecutionPage').then((m) => ({
    default: m.ExecutionPage,
  }))
);
const DependenciesPage = lazy(() =>
  import('@/features/dependencies/DependenciesPage').then((m) => ({
    default: m.DependenciesPage,
  }))
);
const UpdatesPage = lazy(() =>
  import('@/features/updates/UpdatesPage').then((m) => ({
    default: m.UpdatesPage,
  }))
);
const DocumentationPage = lazy(() =>
  import('@/features/documentation/DocumentationPage').then((m) => ({
    default: m.DocumentationPage,
  }))
);
const AssistantPage = lazy(() =>
  import('@/features/assistant/AssistantPage').then((m) => ({
    default: m.AssistantPage,
  }))
);

function RouteLoadingFallback() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-[460px] w-full" />
    </div>
  );
}

function RouteErrorFallback() {
  const error = useRouteError();
  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : 'An unexpected routing error occurred while rendering this view.';

  return (
    <div className="mx-auto max-w-xl py-12 space-y-4">
      <ErrorState
        title="Unable to render view"
        message={message}
        onRetry={() => window.location.reload()}
      />
      <div className="flex justify-center">
        <Button asChild variant="outline" size="sm">
          <Link to={APP_ROUTES.DASHBOARD}>Return to Dashboard</Link>
        </Button>
      </div>
    </div>
  );
}

function withSuspense(node: React.ReactNode) {
  return <Suspense fallback={<RouteLoadingFallback />}>{node}</Suspense>;
}

const router = createBrowserRouter([
  {
    path: APP_ROUTES.LANDING,
    element: <LandingPage />,
    errorElement: <RouteErrorFallback />,
  },
  {
    path: APP_ROUTES.LOGIN,
    element: <LoginPage />,
    errorElement: <RouteErrorFallback />,
  },
  {
    path: APP_ROUTES.REGISTER,
    element: <RegisterPage />,
    errorElement: <RouteErrorFallback />,
  },
  {
    element: <AuthGuard />,
    errorElement: <RouteErrorFallback />,
    children: [
      {
        element: <AppShell />,
        errorElement: <RouteErrorFallback />,
        children: [
          {
            path: APP_ROUTES.DASHBOARD,
            element: <DashboardPage />,
          },
          {
            path: APP_ROUTES.REPOSITORIES,
            element: <RepositoriesPage />,
          },
          {
            path: APP_ROUTES.REPOSITORIES_ADD,
            element: <AddRepositoryPage />,
          },
          {
            path: APP_ROUTES.REPOSITORY_OVERVIEW,
            element: <RepositoryOverviewPage />,
          },
          {
            path: APP_ROUTES.REPOSITORY_EXPLORER,
            element: withSuspense(<ExplorerPage />),
          },
          {
            path: APP_ROUTES.REPOSITORY_ARCHITECTURE,
            element: withSuspense(<ArchitecturePage />),
          },
          {
            path: APP_ROUTES.REPOSITORY_EXECUTION,
            element: withSuspense(<ExecutionPage />),
          },
          {
            path: APP_ROUTES.REPOSITORY_DEPENDENCIES,
            element: withSuspense(<DependenciesPage />),
          },
          {
            path: APP_ROUTES.REPOSITORY_UPDATES,
            element: withSuspense(<UpdatesPage />),
          },
          {
            path: APP_ROUTES.REPOSITORY_DOCS,
            element: withSuspense(<DocumentationPage />),
          },
          {
            path: APP_ROUTES.REPOSITORY_ASSISTANT,
            element: withSuspense(<AssistantPage />),
          },
          {
            path: APP_ROUTES.SETTINGS,
            element: <SettingsPage />,
          },
          {
            path: '*',
            element: <NotFoundPage embedded />,
          },
        ],
      },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}

