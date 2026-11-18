import { Info } from 'lucide-react';

interface SampleDataBannerProps {
  message?: string;
  forceShow?: boolean;
}

export function SampleDataBanner({
  message,
  forceShow = false,
}: SampleDataBannerProps) {
  // In production builds, suppress prototype preview banners
  if (!forceShow || !message) {
    return null;
  }

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
