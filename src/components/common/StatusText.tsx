import { AlertCircle, CheckCircle2, Clock, Loader2 } from 'lucide-react';
import type { AnalysisStatus } from '@/types';
import { cn } from '@/lib/utils';

interface StatusTextProps {
  status: AnalysisStatus;
  className?: string;
}

const STATUS_MAP: Record<
  AnalysisStatus,
  { label: string; textClass: string; icon: typeof CheckCircle2; spin?: boolean }
> = {
  completed: {
    label: 'Completed',
    textClass: 'text-emerald-600 dark:text-emerald-400',
    icon: CheckCircle2,
  },
  analyzing: {
    label: 'Analyzing',
    textClass: 'text-primary',
    icon: Loader2,
    spin: true,
  },
  pending: {
    label: 'Pending',
    textClass: 'text-amber-600 dark:text-amber-400',
    icon: Clock,
  },
  failed: {
    label: 'Failed',
    textClass: 'text-destructive',
    icon: AlertCircle,
  },
};

export function StatusText({ status, className }: StatusTextProps) {
  const cfg = STATUS_MAP[status];
  const Icon = cfg.icon;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-xs font-medium whitespace-nowrap shrink-0',
        cfg.textClass,
        className
      )}
    >
      <Icon
        className={cn('size-3.5', cfg.spin && 'animate-spin')}
        aria-hidden="true"
      />
      <span>{cfg.label}</span>
    </span>
  );
}
