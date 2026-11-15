import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  Bell,
  BookOpen,
  ChevronRight,
  FolderGit2,
  FolderTree,
  GitCompare,
  Home,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquareCode,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings,
  Share2,
  User,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom';
import { RepoMindLogo } from '@/components/common/RepoMindLogo';
import { ThemeToggle } from '@/components/common/ThemeToggle';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { APP_ROUTES, getRepositoryRoute } from '@/constants/routes';
import { cn } from '@/lib/utils';
import { repositoryService } from '@/services';
import { useAuthStore } from '@/stores/auth.store';

interface NotificationItem {
  id: string;
  title: string;
  detail: string;
  time: string;
  read: boolean;
  href: string;
}

const INITIAL_NOTIFICATIONS: NotificationItem[] = [
  {
    id: 'notif-1',
    title: 'Sample analysis completed',
    detail: 'acme-platform/cloud-gateway finished indexing 142 files.',
    time: '35m ago',
    read: false,
    href: getRepositoryRoute('repo-cloud-gateway'),
  },
  {
    id: 'notif-2',
    title: 'New commits available',
    detail: 'cloud-gateway has 1 pending commit ready for incremental diff.',
    time: '55m ago',
    read: false,
    href: getRepositoryRoute('repo-cloud-gateway', 'updates'),
  },
  {
    id: 'notif-3',
    title: 'Circular dependency flagged',
    detail: '2 sample import cycles detected in cloud-gateway.',
    time: '2h ago',
    read: true,
    href: getRepositoryRoute('repo-cloud-gateway', 'dependencies'),
  },
];

export function AppShell() {
  const { id: routeRepoId } = useParams<{ id?: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [notifications, setNotifications] = useState<NotificationItem[]>(
    INITIAL_NOTIFICATIONS
  );

  const { data: repositories = [] } = useQuery({
    queryKey: ['repositories'],
    queryFn: () => repositoryService.getRepositories(),
  });

  const activeRepo = useMemo(
    () => repositories.find((r) => r.id === routeRepoId),
    [repositories, routeRepoId]
  );

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const markAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const filteredSearchRepos = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return repositories;
    return repositories.filter(
      (repo) =>
        repo.name.toLowerCase().includes(q) ||
        repo.owner.toLowerCase().includes(q) ||
        repo.language.toLowerCase().includes(q)
    );
  }, [repositories, searchQuery]);

  const currentRepoSection = useMemo(() => {
    if (!routeRepoId) return undefined;
    const segment = location.pathname.split('/').pop() ?? '';
    const validSections = [
      'explorer',
      'architecture',
      'execution',
      'dependencies',
      'updates',
      'docs',
      'assistant',
    ] as const;
    return validSections.find((s) => s === segment);
  }, [location.pathname, routeRepoId]);

  const breadcrumbs = useMemo(() => {
    const path = location.pathname;
    const crumbs: { label: string; to?: string }[] = [];

    if (path === APP_ROUTES.DASHBOARD) {
      crumbs.push({ label: 'Dashboard' });
    } else if (path === APP_ROUTES.REPOSITORIES) {
      crumbs.push({ label: 'Repositories' });
    } else if (path === APP_ROUTES.REPOSITORIES_ADD) {
      crumbs.push({ label: 'Repositories', to: APP_ROUTES.REPOSITORIES });
      crumbs.push({ label: 'Add Repository' });
    } else if (path === APP_ROUTES.SETTINGS) {
      crumbs.push({ label: 'Settings' });
    } else if (routeRepoId) {
      crumbs.push({ label: 'Repositories', to: APP_ROUTES.REPOSITORIES });
      const repoLabel = activeRepo ? activeRepo.name : routeRepoId;
      const sectionMap: Record<string, string> = {
        explorer: 'Project Explorer',
        architecture: 'Architecture Graph',
        execution: 'Execution Tracing',
        dependencies: 'Dependency Analysis',
        updates: 'Repository Updates',
        docs: 'Documentation Center',
        assistant: 'AI Assistant',
      };
      const segment = path.split('/').pop() ?? '';
      const isSection = Object.keys(sectionMap).includes(segment);
      crumbs.push({
        label: repoLabel,
        to: isSection ? getRepositoryRoute(routeRepoId) : undefined,
      });
      if (isSection) {
        crumbs.push({ label: sectionMap[segment] });
      } else {
        crumbs.push({ label: 'Overview' });
      }
    }
    return crumbs;
  }, [location.pathname, routeRepoId, activeRepo]);

  const repoNavItems = useMemo(() => {
    if (!routeRepoId) return [];
    return [
      {
        label: 'Overview',
        to: getRepositoryRoute(routeRepoId),
        icon: LayoutDashboard,
        end: true,
      },
      {
        label: 'Explorer',
        to: getRepositoryRoute(routeRepoId, 'explorer'),
        icon: FolderTree,
        end: false,
      },
      {
        label: 'Architecture',
        to: getRepositoryRoute(routeRepoId, 'architecture'),
        icon: Network,
        end: false,
      },
      {
        label: 'Execution Tracing',
        to: getRepositoryRoute(routeRepoId, 'execution'),
        icon: Activity,
        end: false,
      },
      {
        label: 'Dependencies',
        to: getRepositoryRoute(routeRepoId, 'dependencies'),
        icon: Share2,
        end: false,
      },
      {
        label: 'Updates',
        to: getRepositoryRoute(routeRepoId, 'updates'),
        icon: GitCompare,
        end: false,
      },
      {
        label: 'Documentation',
        to: getRepositoryRoute(routeRepoId, 'docs'),
        icon: BookOpen,
        end: false,
      },
      {
        label: 'AI Assistant',
        to: getRepositoryRoute(routeRepoId, 'assistant'),
        icon: MessageSquareCode,
        end: false,
      },
    ];
  }, [routeRepoId]);

  const handleSignOut = async () => {
    await logout();
    navigate(APP_ROUTES.LOGIN);
  };

  const renderSidebarBody = (isCollapsed: boolean) => (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div
        className={cn(
          'flex h-14 items-center border-b border-sidebar-border px-3.5',
          isCollapsed ? 'justify-center' : 'justify-between'
        )}
      >
        <Link
          to={APP_ROUTES.DASHBOARD}
          className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md"
        >
          <RepoMindLogo compact={isCollapsed} />
        </Link>
        {!isCollapsed && (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => setSidebarCollapsed(true)}
            aria-label="Collapse sidebar"
            className="hidden lg:inline-flex text-muted-foreground hover:text-foreground"
          >
            <PanelLeftClose className="size-4" />
          </Button>
        )}
      </div>

      {isCollapsed && (
        <div className="hidden lg:flex justify-center border-b border-sidebar-border py-2">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => setSidebarCollapsed(false)}
            aria-label="Expand sidebar"
            className="text-muted-foreground hover:text-foreground"
          >
            <PanelLeftOpen className="size-4" />
          </Button>
        </div>
      )}

      <ScrollArea className="flex-1 px-2.5 py-3">
        <div className="space-y-5">
          <nav aria-label="Workspace Navigation" className="space-y-1">
            {!isCollapsed && (
              <p className="px-2.5 pb-1 text-xs font-medium text-muted-foreground">
                Workspace
              </p>
            )}
            <NavLink
              to={APP_ROUTES.DASHBOARD}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors whitespace-nowrap',
                  isCollapsed && 'justify-center px-0',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                    : 'text-sidebar-foreground/80 hover:bg-muted hover:text-foreground'
                )
              }
            >
              <LayoutDashboard className="size-4 shrink-0" />
              {!isCollapsed && <span>Dashboard</span>}
            </NavLink>

            <NavLink
              to={APP_ROUTES.REPOSITORIES}
              end
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors whitespace-nowrap',
                  isCollapsed && 'justify-center px-0',
                  isActive || location.pathname === APP_ROUTES.REPOSITORIES_ADD
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                    : 'text-sidebar-foreground/80 hover:bg-muted hover:text-foreground'
                )
              }
            >
              <FolderGit2 className="size-4 shrink-0" />
              {!isCollapsed && <span>Repositories</span>}
            </NavLink>

            <NavLink
              to={APP_ROUTES.SETTINGS}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors whitespace-nowrap',
                  isCollapsed && 'justify-center px-0',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                    : 'text-sidebar-foreground/80 hover:bg-muted hover:text-foreground'
                )
              }
            >
              <Settings className="size-4 shrink-0" />
              {!isCollapsed && <span>Settings</span>}
            </NavLink>
          </nav>

          {routeRepoId && (
            <nav aria-label="Repository Navigation" className="space-y-1 border-t border-sidebar-border pt-4">
              {!isCollapsed && (
                <div className="px-1.5 pb-2 space-y-1.5">
                  <p className="px-1 text-xs font-medium text-muted-foreground">
                    Active Repository
                  </p>
                  {repositories.length > 0 ? (
                    <Select
                      value={routeRepoId}
                      onValueChange={(nextRepoId) => {
                        navigate(getRepositoryRoute(nextRepoId, currentRepoSection));
                      }}
                    >
                      <SelectTrigger
                        aria-label="Switch active repository"
                        className="h-8 w-full bg-background/70 text-xs font-medium"
                      >
                        <SelectValue placeholder="Select repository" />
                      </SelectTrigger>
                      <SelectContent>
                        {repositories.map((repo) => (
                          <SelectItem key={repo.id} value={repo.id} className="text-xs">
                            <span className="truncate font-medium">
                              {repo.owner}/{repo.name}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <p className="px-1 truncate text-xs font-semibold text-foreground">
                      {activeRepo ? `${activeRepo.owner}/${activeRepo.name}` : routeRepoId}
                    </p>
                  )}
                </div>
              )}

              {repoNavItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    title={isCollapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors whitespace-nowrap',
                        isCollapsed && 'justify-center px-0',
                        isActive
                          ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                          : 'text-sidebar-foreground/80 hover:bg-muted hover:text-foreground'
                      )
                    }
                  >
                    <Icon className="size-4 shrink-0" />
                    {!isCollapsed && <span>{item.label}</span>}
                  </NavLink>
                );
              })}
            </nav>
          )}
        </div>
      </ScrollArea>

      <div className="border-t border-sidebar-border p-2.5 space-y-1.5">
        <Link
          to={APP_ROUTES.LANDING}
          title={isCollapsed ? 'Product Landing Page' : undefined}
          className={cn(
            'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors whitespace-nowrap',
            isCollapsed && 'justify-center px-0'
          )}
        >
          <Home className="size-3.5 shrink-0" />
          {!isCollapsed && <span>Product Landing</span>}
        </Link>

        <div
          className={cn(
            'flex items-center gap-2.5 rounded-md px-2 py-1.5',
            isCollapsed && 'justify-center px-0'
          )}
        >
          <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-xs font-semibold text-primary">
            {user?.avatarInitials ?? 'RM'}
          </div>
          {!isCollapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">
                {user?.name ?? 'Developer'}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {user?.email ?? 'workspace@repomind.dev'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          'hidden lg:flex flex-col shrink-0 border-r border-sidebar-border transition-[width] duration-200',
          sidebarCollapsed ? 'w-[68px]' : 'w-64'
        )}
      >
        <div className="sticky top-0 h-screen w-full">
          {renderSidebarBody(sidebarCollapsed)}
        </div>
      </aside>

      {/* Mobile Drawer Sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative z-10 flex w-72 max-w-[85vw] flex-col border-r border-sidebar-border bg-sidebar">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation menu"
              className="absolute right-2.5 top-3 z-20"
            >
              <X className="size-4" />
            </Button>
            {renderSidebarBody(false)}
          </aside>
        </div>
      )}

      {/* Main Column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-4 border-b border-border bg-background/95 px-4 sm:px-6 backdrop-blur-sm">
          <div className="flex min-w-0 items-center gap-2.5">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation menu"
              className="lg:hidden shrink-0"
            >
              <Menu className="size-5" />
            </Button>

            <nav
              aria-label="Breadcrumb"
              className="flex min-w-0 items-center gap-1.5 text-sm"
            >
              {breadcrumbs.map((crumb, idx) => {
                const isLast = idx === breadcrumbs.length - 1;
                return (
                  <span
                    key={`${crumb.label}-${idx}`}
                    className="flex min-w-0 items-center gap-1.5"
                  >
                    {idx > 0 && (
                      <ChevronRight
                        className="size-3.5 shrink-0 text-muted-foreground"
                        aria-hidden="true"
                      />
                    )}
                    {crumb.to && !isLast ? (
                      <Link
                        to={crumb.to}
                        className="truncate text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {crumb.label}
                      </Link>
                    ) : (
                      <span
                        className={cn(
                          'truncate',
                          isLast
                            ? 'font-semibold text-foreground'
                            : 'text-muted-foreground'
                        )}
                      >
                        {crumb.label}
                      </span>
                    )}
                  </span>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setSearchOpen(true)}
              className="hidden sm:inline-flex items-center gap-2 text-muted-foreground h-8 px-2.5"
            >
              <Search className="size-3.5" />
              <span className="text-xs">Search repositories...</span>
              <kbd className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                Ctrl K
              </kbd>
            </Button>

            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => setSearchOpen(true)}
              aria-label="Search repositories"
              className="sm:hidden text-muted-foreground"
            >
              <Search className="size-4" />
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="View notifications"
                  className="relative text-muted-foreground hover:text-foreground"
                >
                  <Bell className="size-4" />
                  {unreadCount > 0 && (
                    <span className="absolute right-1.5 top-1.5 flex size-2 rounded-full bg-primary" />
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80">
                <div className="flex items-center justify-between px-2 py-1.5">
                  <DropdownMenuLabel className="p-0 text-xs font-semibold">
                    Notifications ({unreadCount} unread)
                  </DropdownMenuLabel>
                  {unreadCount > 0 && (
                    <button
                      type="button"
                      onClick={markAllRead}
                      className="text-xs text-primary hover:underline"
                    >
                      Mark all read
                    </button>
                  )}
                </div>
                <DropdownMenuSeparator />
                {notifications.map((item) => (
                  <DropdownMenuItem
                    key={item.id}
                    onClick={() => {
                      setNotifications((prev) =>
                        prev.map((n) =>
                          n.id === item.id ? { ...n, read: true } : n
                        )
                      );
                      navigate(item.href);
                    }}
                    className="flex flex-col items-start gap-0.5 py-2 cursor-pointer"
                  >
                    <div className="flex w-full items-center justify-between gap-2">
                      <span
                        className={cn(
                          'text-xs font-medium',
                          !item.read ? 'text-foreground' : 'text-muted-foreground'
                        )}
                      >
                        {item.title}
                      </span>
                      <span className="text-[11px] text-muted-foreground tabular-nums">
                        {item.time}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground line-clamp-2">
                      {item.detail}
                    </span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            <ThemeToggle />

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="gap-2 pl-1.5 pr-2"
                  aria-label="Open profile menu"
                >
                  <span className="flex size-6 items-center justify-center rounded bg-primary/15 text-xs font-semibold text-primary">
                    {user?.avatarInitials ?? 'RM'}
                  </span>
                  <span className="hidden md:inline text-xs font-medium whitespace-nowrap">
                    {user?.name ?? 'Developer'}
                  </span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col space-y-0.5">
                    <p className="text-sm font-medium">{user?.name}</p>
                    <p className="text-xs text-muted-foreground truncate">
                      {user?.email}
                    </p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate(APP_ROUTES.SETTINGS)}>
                  <User className="mr-2 size-4" />
                  Profile & Settings
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => navigate(APP_ROUTES.REPOSITORIES_ADD)}
                >
                  <Plus className="mr-2 size-4" />
                  Connect Repository
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate(APP_ROUTES.LANDING)}>
                  <Home className="mr-2 size-4" />
                  Product Landing Page
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={handleSignOut}
                  className="text-destructive focus:text-destructive"
                >
                  <LogOut className="mr-2 size-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6">
          <div className="mx-auto w-full max-w-[1400px]">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Global Search Dialog */}
      <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
        <DialogContent className="sm:max-w-lg p-0 overflow-hidden gap-0">
          <DialogHeader className="sr-only">
            <DialogTitle>Search Repositories</DialogTitle>
            <DialogDescription>
              Jump directly to any indexed repository or workspace view.
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center border-b border-border px-3">
            <Search className="size-4 text-muted-foreground shrink-0" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search repositories by name, owner, or language..."
              className="border-0 focus-visible:ring-0 shadow-none h-11"
              autoFocus
            />
          </div>
          <ScrollArea className="max-h-80 p-2">
            {filteredSearchRepos.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No repositories match &ldquo;{searchQuery}&rdquo;.
              </p>
            ) : (
              <div className="space-y-1.5">
                {filteredSearchRepos.map((repo) => (
                  <div
                    key={repo.id}
                    className="rounded-md border border-transparent hover:border-border hover:bg-muted/50 px-3 py-2 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setSearchOpen(false);
                          setSearchQuery('');
                          navigate(getRepositoryRoute(repo.id));
                        }}
                        className="min-w-0 flex-1 text-left"
                      >
                        <p className="font-medium text-sm text-foreground truncate">
                          {repo.owner}/{repo.name}
                        </p>
                        <p className="text-xs text-muted-foreground truncate">
                          {repo.language} · {repo.fileCount} files · Branch {repo.branch}
                        </p>
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setSearchOpen(false);
                          setSearchQuery('');
                          navigate(getRepositoryRoute(repo.id));
                        }}
                        className="text-xs text-primary font-medium shrink-0 hover:underline"
                      >
                        Overview
                      </button>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(
                        [
                          ['Explorer', 'explorer'],
                          ['Architecture', 'architecture'],
                          ['Execution', 'execution'],
                          ['Dependencies', 'dependencies'],
                          ['Updates', 'updates'],
                          ['Docs', 'docs'],
                          ['Assistant', 'assistant'],
                        ] as const
                      ).map(([label, section]) => (
                        <button
                          key={section}
                          type="button"
                          onClick={() => {
                            setSearchOpen(false);
                            setSearchQuery('');
                            navigate(getRepositoryRoute(repo.id, section));
                          }}
                          className="rounded border border-border bg-background px-2 py-0.5 text-[11px] font-medium text-muted-foreground hover:border-primary/40 hover:text-foreground transition-colors"
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
          <div className="flex items-center justify-between border-t border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <span>Jump to any repository module or connect a new codebase</span>
            <button
              type="button"
              onClick={() => {
                setSearchOpen(false);
                setSearchQuery('');
                navigate(APP_ROUTES.REPOSITORIES_ADD);
              }}
              className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
            >
              <Plus className="size-3.5" />
              Connect Repository
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
