import type { ArchitectureService } from './intelligence.service';
import type { ArchitectureGraphData } from '@/types';
import { apiFetch } from './client';

export class ApiArchitectureService implements ArchitectureService {
  async getArchitectureGraph(repositoryId: string): Promise<ArchitectureGraphData> {
    const res = await apiFetch(`/repositories/${repositoryId}/architecture/graph`);
    if (!res.ok) {
      throw new Error(`Failed to load architecture graph: ${res.statusText}`);
    }

    const data: ArchitectureGraphData = await res.json();
    return data;
  }
}

export const apiArchitectureService = new ApiArchitectureService();
