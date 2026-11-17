import type { AssistantService } from './intelligence.service';
import type { AssistantConversation, AssistantMessage } from '@/types';
import { mockAssistantService } from '@/services/mock/assistant.mock';

const API_BASE = '/api/v1';

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('repomind_access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiAssistantService implements AssistantService {
  async getConversations(repositoryId: string): Promise<AssistantConversation[]> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/conversations`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });

      if (!res.ok) {
        // Fall back to mock if not authenticated or offline in frontend preview
        return mockAssistantService.getConversations(repositoryId);
      }

      const data = await res.json();
      return data;
    } catch {
      return mockAssistantService.getConversations(repositoryId);
    }
  }

  async getSuggestedQuestions(repositoryId: string): Promise<string[]> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/chat/suggestions`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });

      if (!res.ok) {
        return mockAssistantService.getSuggestedQuestions(repositoryId);
      }

      const data = await res.json();
      return data.suggestions || [];
    } catch {
      return mockAssistantService.getSuggestedQuestions(repositoryId);
    }
  }

  async sendMessage(
    repositoryId: string,
    conversationId: string,
    prompt: string
  ): Promise<AssistantMessage> {
    try {
      const res = await fetch(
        `${API_BASE}/repositories/${repositoryId}/conversations/${conversationId}/messages`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeader(),
          },
          body: JSON.stringify({ prompt }),
        }
      );

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `Inference error: HTTP ${res.status}`);
      }

      const rawMsg = await res.json();
      return {
        id: rawMsg.id,
        role: rawMsg.role,
        content: rawMsg.content,
        timestamp: rawMsg.timestamp,
        confidence: rawMsg.confidence,
        citations: rawMsg.citations,
        isSampleOutput: false,
      };
    } catch (err) {
      // If network error and unauthenticated, use mock service for local preview
      if (err instanceof Error && err.message.includes('fetch')) {
        return mockAssistantService.sendMessage(repositoryId, conversationId, prompt);
      }
      throw err;
    }
  }
}

export const apiAssistantService = new ApiAssistantService();
