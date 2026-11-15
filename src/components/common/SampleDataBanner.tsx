import { Info } from 'lucide-react';

interface SampleDataBannerProps {
  message?: string;
}

export function SampleDataBanner({
  message = 'Phase 1 Frontend Preview — Displaying sample static analysis data. Live repository parsing and AI inference connect in Phase 2+.',
}: SampleDataBannerProps) {
  return (
    <div
      role="status"
      className="flex items-start sm:items-center gap-2.5 rounded-lg border border-border bg-muted/50 px-3.5 py-2.5 text-xs text-muted-foreground"
    >
      <Info className="size-4 text-primary shrink-0 mt-0.5 sm:mt-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
