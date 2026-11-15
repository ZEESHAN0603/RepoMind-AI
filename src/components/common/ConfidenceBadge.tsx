import { CheckCircle2, HelpCircle, Sparkles } from 'lucide-react';
import type { GroundingConfidence } from '@/types';
import { cn } from '@/lib/utils';

type ExtendedConfidence = GroundingConfidence | 'unresolved';

interface ConfidenceBadgeProps {
  confidence: ExtendedConfidence;
  className?: string;
}

const CONFIG: Record<
  ExtendedConfidence,
  { label: string; classes: string; icon: typeof CheckCircle2 }
> = {
  verified: {
    label: 'Verified',
    classes:
      'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/25',
    icon: CheckCircle2,
  },
  inferred: {
    label: 'Inferred',
    classes:
      'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/25',
    icon: Sparkles,
  },
  unknown: {
    label: 'Unknown',
    classes: 'bg-muted text-muted-foreground border-border',
    icon: HelpCircle,
  },
  unresolved: {
    label: 'Unresolved',
    classes:
      'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/25',
    icon: HelpCircle,
  },
};

export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  const item = CONFIG[confidence];
  const Icon = item.icon;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap shrink-0',
        item.classes,
        className
      )}
    >
      <Icon className="size-3" aria-hidden="true" />
      <span>{item.label}</span>
    </span>
  );
}
