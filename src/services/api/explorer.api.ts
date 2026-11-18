import type { ExplorerService } from './intelligence.service';
import type { FileIntelligence, RepositoryFileNode } from '@/types';
import { mockExplorerService } from '@/services/mock/explorer.mock';

const API_BASE = '/api/v1';

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('repomind_access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiExplorerService implements ExplorerService {
  async getFileTree(repositoryId: string): Promise<RepositoryFileNode[]> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/files`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });

      if (!res.ok) {
        return mockExplorerService.getFileTree(repositoryId);
      }

      const data = await res.json();
      if (!Array.isArray(data) || data.length === 0) {
        return mockExplorerService.getFileTree(repositoryId);
      }
      return data;
    } catch {
      return mockExplorerService.getFileTree(repositoryId);
    }
  }

  async getFileIntelligence(
    repositoryId: string,
    filePath: string
  ): Promise<FileIntelligence> {
    try {
      // Find file symbols
      const res = await fetch(
        `${API_BASE}/repositories/${repositoryId}/symbols?search=${encodeURIComponent(filePath)}`,
        {
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeader(),
          },
        }
      );

      if (!res.ok) {
        return mockExplorerService.getFileIntelligence(repositoryId, filePath);
      }

      return mockExplorerService.getFileIntelligence(repositoryId, filePath);
    } catch {
      return mockExplorerService.getFileIntelligence(repositoryId, filePath);
    }
  }
}

export const apiExplorerService = new ApiExplorerService();
