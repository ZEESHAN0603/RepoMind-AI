import type { DependencyService } from './intelligence.service';
import type { DependencyAnalysisData } from '@/types';
import { apiFetch } from './client';

export class ApiDependencyService implements DependencyService {
  async getDependencyAnalysis(repositoryId: string): Promise<DependencyAnalysisData> {
    const res = await apiFetch(`/repositories/${repositoryId}/dependencies/graph`);
    if (!res.ok) {
      throw new Error(`Failed to load dependency graph: ${res.statusText}`);
    }

    const data: DependencyAnalysisData = await res.json();
    return data;
  }

  async refreshDependencyAnalysis(repositoryId: string): Promise<DependencyAnalysisData> {
    const res = await apiFetch(`/repositories/${repositoryId}/dependencies/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!res.ok) {
      throw new Error(`Failed to run dependency analysis: ${res.statusText}`);
    }

    const data: DependencyAnalysisData = await res.json();
    return data;
  }
}

export const apiDependencyService = new ApiDependencyService();
