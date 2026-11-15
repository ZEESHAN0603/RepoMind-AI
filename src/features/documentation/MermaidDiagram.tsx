import mermaid from 'mermaid';
import { useEffect, useId, useState } from 'react';
import { useThemeStore } from '@/stores/theme.store';

interface MermaidDiagramProps {
  chart: string;
}

export function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const theme = useThemeStore((state) => state.theme);
  const rawId = useId();
  const safeId = `mermaid-${rawId.replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const [svg, setSvg] = useState<string>('');
  const [renderError, setRenderError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function render() {
      try {
        mermaid.initialize({
          startOnLoad: false,
          theme: theme === 'dark' ? 'dark' : 'default',
          securityLevel: 'strict',
        });
        const { svg: renderedSvg } = await mermaid.render(safeId, chart);
        if (!cancelled) {
          setSvg(renderedSvg);
          setRenderError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setRenderError(
            err instanceof Error ? err.message : 'Unable to render Mermaid diagram.'
          );
        }
      }
    }

    render();
    return () => {
      cancelled = true;
    };
  }, [chart, theme, safeId]);

  if (renderError) {
    return (
      <div className="my-3 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
        Mermaid preview error: {renderError}
      </div>
    );
  }

  return (
    <div
      className="my-4 overflow-x-auto rounded-lg border border-border bg-background p-4"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
