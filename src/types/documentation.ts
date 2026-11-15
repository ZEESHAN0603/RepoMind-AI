import type { GroundingConfidence } from './repository';

export type DocSectionType =
  | 'readme'
  | 'architecture'
  | 'module'
  | 'api'
  | 'database'
  | 'onboarding';

export interface DocumentationDocument {
  id: string;
  repositoryId: string;
  type: DocSectionType;
  title: string;
  description: string;
  content: string;
  lastUpdated: string;
  confidence: GroundingConfidence;
}
