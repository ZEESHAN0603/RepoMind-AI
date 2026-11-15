import type { GroundingConfidence } from './repository';

export interface CodeCitation {
  filePath: string;
  startLine: number;
  endLine: number;
  snippet?: string;
}

export interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  confidence?: GroundingConfidence;
  citations?: CodeCitation[];
  codeBlock?: {
    language: string;
    code: string;
    filePath: string;
  };
  isSampleOutput?: boolean;
}

export interface AssistantConversation {
  id: string;
  repositoryId: string;
  title: string;
  updatedAt: string;
  messages: AssistantMessage[];
}
