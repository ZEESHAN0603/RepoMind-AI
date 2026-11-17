import type { ArchitectureService } from './intelligence.service';
import type { ArchitectureGraphData } from '@/types';
import { mockArchitectureService } from '@/services/mock/architecture.mock';

const API_BASE = '/api/v1';

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('repomind_access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiArchitectureService implements ArchitectureService {
  async getArchitectureGraph(repositoryId: string): Promise<ArchitectureGraphData> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/architecture/graph`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });

      if (!res.ok) {
        // Fall back to sample mock graph for preview / offline demo repositories
        return mockArchitectureService.getArchitectureGraph(repositoryId);
      }

      const data: ArchitectureGraphData = await res.json();
      return data;
    } catch {
      return mockArchitectureService.getArchitectureGraph(repositoryId);
    }
  }
}

export const apiArchitectureService = new ApiArchitectureService();
