import type { ExecutionService } from './intelligence.service';
import type {
  ExecutionExplanationResponse,
  ExecutionFlow,
  ExecutionTraceWorkspace,
} from '@/types';
import { mockExecutionService } from '@/services/mock/execution.mock';

const API_BASE = '/api/v1';

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('repomind_access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiExecutionService implements ExecutionService {
  async getExecutionFlows(repositoryId: string): Promise<ExecutionFlow[]> {
    const workspace = await this.getExecutionWorkspace(repositoryId);
    return workspace.traces.map((t) => t.flow);
  }

  async getExecutionWorkspace(repositoryId: string): Promise<ExecutionTraceWorkspace> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/execution/workspace`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });

      if (!res.ok) {
        // If 404 or unanalyzed, attempt to trigger analysis first
        if (res.status === 404) {
          const analyzeRes = await this.analyzeExecution(repositoryId);
          if (analyzeRes && analyzeRes.traces_generated > 0) {
            const retryRes = await fetch(`${API_BASE}/repositories/${repositoryId}/execution/workspace`, {
              headers: {
                'Content-Type': 'application/json',
                ...getAuthHeader(),
              },
            });
            if (retryRes.ok) {
              return await retryRes.json();
            }
          }
        }
        return mockExecutionService.getExecutionWorkspace(repositoryId);
      }

      const data: ExecutionTraceWorkspace = await res.json();
      if (!data.traces || data.traces.length === 0) {
        // If real repo currently has 0 traces, fallback to mock traces for preview
        const mockData = await mockExecutionService.getExecutionWorkspace(repositoryId);
        return {
          ...data,
          traces: data.traces.length > 0 ? data.traces : mockData.traces,
          functions: data.functions.length > 0 ? data.functions : mockData.functions,
        };
      }
      return data;
    } catch {
      return mockExecutionService.getExecutionWorkspace(repositoryId);
    }
  }

  async analyzeExecution(repositoryId: string): Promise<any> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/execution/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });
      if (!res.ok) {
        return mockExecutionService.analyzeExecution ? mockExecutionService.analyzeExecution(repositoryId) : null;
      }
      return await res.json();
    } catch {
      return mockExecutionService.analyzeExecution ? mockExecutionService.analyzeExecution(repositoryId) : null;
    }
  }

  async explainExecutionFlow(
    repositoryId: string,
    payload: { flowId?: string; symbolId?: string; focusQuestion?: string }
  ): Promise<ExecutionExplanationResponse> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/execution/explain`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        return mockExecutionService.explainExecutionFlow
          ? mockExecutionService.explainExecutionFlow(repositoryId, payload)
          : {
              summary: 'Static analysis trace explanation unavailable.',
              verifiedSteps: [],
              uncertainties: ['Backend explanation service returned non-200 status.'],
              providerUsed: 'fallback',
            };
      }

      return await res.json();
    } catch {
      return mockExecutionService.explainExecutionFlow
        ? mockExecutionService.explainExecutionFlow(repositoryId, payload)
        : {
            summary: 'Network error communicating with AI explanation service.',
            verifiedSteps: [],
            uncertainties: ['Failed to reach backend API.'],
            providerUsed: 'fallback',
          };
    }
  }
}

export const apiExecutionService = new ApiExecutionService();
