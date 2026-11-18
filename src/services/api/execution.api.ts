import type { ExecutionService } from './intelligence.service';
import type {
  ExecutionExplanationResponse,
  ExecutionFlow,
  ExecutionTraceWorkspace,
} from '@/types';
import { apiFetch } from './client';

export class ApiExecutionService implements ExecutionService {
  async getExecutionFlows(repositoryId: string): Promise<ExecutionFlow[]> {
    const workspace = await this.getExecutionWorkspace(repositoryId);
    return (workspace.traces || []).map((t) => t.flow);
  }

  async getExecutionWorkspace(repositoryId: string): Promise<ExecutionTraceWorkspace> {
    const res = await apiFetch(`/repositories/${repositoryId}/execution/workspace`);

    if (!res.ok) {
      if (res.status === 404) {
        // Attempt on-demand analysis if workspace has not been generated yet
        const analyzeRes = await this.analyzeExecution(repositoryId);
        if (analyzeRes && analyzeRes.traces_generated > 0) {
          const retryRes = await apiFetch(`/repositories/${repositoryId}/execution/workspace`);
          if (retryRes.ok) {
            return await retryRes.json();
          }
        }
      }
      throw new Error(`Failed to load execution workspace: ${res.statusText}`);
    }

    const data: ExecutionTraceWorkspace = await res.json();
    return {
      repositoryId: data.repositoryId || repositoryId,
      repositoryName: data.repositoryName || 'Repository',
      traces: data.traces || [],
      functions: data.functions || [],
    };
  }

  async analyzeExecution(repositoryId: string): Promise<any> {
    const res = await apiFetch(`/repositories/${repositoryId}/execution/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!res.ok) {
      throw new Error(`Execution analysis failed: ${res.statusText}`);
    }

    return await res.json();
  }

  async explainExecutionFlow(
    repositoryId: string,
    payload: { flowId?: string; symbolId?: string; focusQuestion?: string }
  ): Promise<ExecutionExplanationResponse> {
    const res = await apiFetch(`/repositories/${repositoryId}/execution/explain`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Failed to generate execution explanation: ${res.statusText}`);
    }

    return await res.json();
  }
}

export const apiExecutionService = new ApiExecutionService();
