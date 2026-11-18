import type { AssistantService } from './intelligence.service';
import type { AssistantConversation, AssistantMessage } from '@/types';
import { apiFetch } from './client';

export class ApiAssistantService implements AssistantService {
  async getConversations(repositoryId: string): Promise<AssistantConversation[]> {
    const res = await apiFetch(`/repositories/${repositoryId}/conversations`);
    if (!res.ok) {
      if (res.status === 404) return [];
      throw new Error(`Failed to load conversations: ${res.statusText}`);
    }

    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  async getSuggestedQuestions(repositoryId: string): Promise<string[]> {
    const res = await apiFetch(`/repositories/${repositoryId}/chat/suggestions`);
    if (!res.ok) {
      return [
        'How is this repository structured?',
        'What are the primary entry points and modules?',
        'Explain the core dependencies in this codebase.',
      ];
    }

    const data = await res.json();
    return data.suggestions || [];
  }

  async sendMessage(
    repositoryId: string,
    conversationId: string,
    prompt: string
  ): Promise<AssistantMessage> {
    const res = await apiFetch(
      `/repositories/${repositoryId}/conversations/${conversationId}/messages`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt }),
      }
    );

    if (!res.ok) {
      const errJson = await res.json().catch(() => null);
      throw new Error(errJson?.detail || errJson?.error?.message || `Inference error: HTTP ${res.status}`);
    }

    const rawMsg = await res.json();
    return {
      id: rawMsg.id,
      role: rawMsg.role,
      content: rawMsg.content,
      timestamp: rawMsg.timestamp || new Date().toISOString(),
      confidence: rawMsg.confidence || 'verified',
      citations: rawMsg.citations || [],
      isSampleOutput: false,
    };
  }
}

export const apiAssistantService = new ApiAssistantService();
