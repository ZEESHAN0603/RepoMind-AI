import { cn } from '@/lib/utils';

interface RepoMindLogoProps {
  compact?: boolean;
  className?: string;
}

export function RepoMindLogo({ compact = false, className }: RepoMindLogoProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2.5 font-semibold tracking-tight text-foreground whitespace-nowrap shrink-0',
        className
      )}
    >
      <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <svg
          viewBox="0 0 24 24"
          className="size-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="6" cy="6" r="2.5" />
          <circle cx="18" cy="6" r="2.5" />
          <circle cx="12" cy="18" r="2.5" />
          <path d="M8 7.5 11 15.5" />
          <path d="M16 7.5 13 15.5" />
          <path d="M8.5 6h7" />
        </svg>
      </span>
      {!compact && (
        <span className="font-heading text-base font-bold tracking-tight">
          RepoMind
        </span>
      )}
    </span>
  );
}
