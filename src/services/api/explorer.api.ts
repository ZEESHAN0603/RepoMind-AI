import type { ExplorerService } from './intelligence.service';
import type { CodeSymbol, FileIntelligence, RepositoryFileNode } from '@/types';
import { apiFetch } from './client';

export class ApiExplorerService implements ExplorerService {
  async getFileTree(repositoryId: string): Promise<RepositoryFileNode[]> {
    const res = await apiFetch(`/repositories/${repositoryId}/files`);
    if (!res.ok) {
      throw new Error(`Failed to load file tree: ${res.statusText}`);
    }

    const data = await res.json();
    if (!Array.isArray(data)) return [];
    return data;
  }

  async getFileIntelligence(
    repositoryId: string,
    filePath: string
  ): Promise<FileIntelligence> {
    const extension = filePath.split('.').pop()?.toLowerCase() ?? 'text';
    const languageMap: Record<string, string> = {
      ts: 'typescript',
      tsx: 'typescript',
      js: 'javascript',
      jsx: 'javascript',
      py: 'python',
      go: 'go',
      json: 'json',
      md: 'markdown',
      rs: 'rust',
      java: 'java',
      cpp: 'cpp',
      c: 'c',
    };
    const language = languageMap[extension] ?? 'plaintext';

    // Query symbols for this file path
    const res = await apiFetch(
      `/repositories/${repositoryId}/symbols?search=${encodeURIComponent(filePath)}`
    );

    let symbols: CodeSymbol[] = [];
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) {
        symbols = data.map((sym: any) => ({
          id: sym.id,
          name: sym.name,
          kind: (sym.symbol_type === 'function' ? 'function' : sym.symbol_type === 'class' ? 'class' : 'variable') as any,
          startLine: sym.start_line,
          endLine: sym.end_line,
          signature: sym.signature || `${sym.name}()`,
          summary: sym.docstring || `${sym.visibility || 'public'} ${sym.symbol_type} ${sym.name}`,
          confidence: 'verified' as const,
        }));
      }
    }

    const fileName = filePath.split('/').pop() ?? filePath;
    return {
      path: filePath,
      language,
      confidence: symbols.length > 0 ? 'verified' : 'inferred',
      explanation: symbols.length > 0
        ? `Source file contains ${symbols.length} identified symbol(s) analyzed by the static AST parsing engine.`
        : `Source module indexed at "${filePath}".`,
      relatedFiles: [],
      dependencies: [],
      sourceReferences: symbols.map((s) => ({ label: s.name, line: s.startLine })),
      symbols,
      content: `// Source File: ${filePath}\n// Symbols identified: ${symbols.length}\n\n` +
        symbols.map((s) => `// Line ${s.startLine}-${s.endLine}: ${s.signature}\n`).join(''),
    };
  }
}

export const apiExplorerService = new ApiExplorerService();
