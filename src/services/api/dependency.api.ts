import type { DependencyService } from './intelligence.service';
import type { DependencyAnalysisData } from '@/types';
import { mockDependencyService } from '@/services/mock/dependency.mock';

const API_BASE = '/api/v1';

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('repomind_access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiDependencyService implements DependencyService {
  async getDependencyAnalysis(repositoryId: string): Promise<DependencyAnalysisData> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/dependencies/graph`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });

      if (!res.ok) {
        // Fall back to sample data for offline preview / demo repositories
        return mockDependencyService.getDependencyAnalysis(repositoryId);
      }

      const data: DependencyAnalysisData = await res.json();
      return data;
    } catch {
      return mockDependencyService.getDependencyAnalysis(repositoryId);
    }
  }

  async refreshDependencyAnalysis(repositoryId: string): Promise<DependencyAnalysisData> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/dependencies/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });

      if (!res.ok) {
        return mockDependencyService.refreshDependencyAnalysis(repositoryId);
      }

      const data: DependencyAnalysisData = await res.json();
      return data;
    } catch {
      return mockDependencyService.refreshDependencyAnalysis(repositoryId);
    }
  }
}

export const apiDependencyService = new ApiDependencyService();
