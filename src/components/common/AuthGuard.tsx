import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { APP_ROUTES } from '@/constants/routes';
import { useAuthStore } from '@/stores/auth.store';

export function AuthGuard() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return (
      <Navigate
        to={APP_ROUTES.LOGIN}
        replace
        state={{ from: location.pathname }}
      />
    );
  }

  return <Outlet />;
}
