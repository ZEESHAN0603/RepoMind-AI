import type { DocumentationService } from './intelligence.service';
import type { DocSectionType, DocumentationDocument, DocumentDiffData } from '@/types';
import { mockDocumentationService } from '@/services/mock/documentation.mock';

const API_BASE = '/api/v1';

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('repomind_access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiDocumentationService implements DocumentationService {
  async getDocuments(repositoryId: string): Promise<DocumentationDocument[]> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/documentation`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });

      if (!res.ok) {
        return mockDocumentationService.getDocuments(repositoryId);
      }

      const data = await res.json();
      if (!data.items || data.items.length === 0) {
        return mockDocumentationService.getDocuments(repositoryId);
      }

      // Fetch full content for documents
      const fullDocs: DocumentationDocument[] = [];
      for (const item of data.items) {
        try {
          const detail = await this.getDocument(repositoryId, item.doc_type);
          fullDocs.push(detail);
        } catch {
          fullDocs.push({
            id: item.id,
            repositoryId: item.repository_id,
            type: item.doc_type,
            title: item.title,
            description: item.description,
            content: `# ${item.title}\n\nContent is being generated or loaded.`,
            status: item.status || 'draft',
            confidence: (item.confidence as any) || 'verified',
            versionNumber: item.version_number || 1,
            lastUpdated: item.last_generated_at,
            approvedAt: item.approved_at,
            approvedBy: item.approved_by,
          });
        }
      }

      return fullDocs;
    } catch {
      return mockDocumentationService.getDocuments(repositoryId);
    }
  }

  async getDocument(repositoryId: string, docType: string): Promise<DocumentationDocument> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/documentation/${docType}`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      });

      if (!res.ok) {
        const fallbackList = await mockDocumentationService.getDocuments(repositoryId);
        return fallbackList.find((d) => d.type === docType) || fallbackList[0];
      }

      const d = await res.json();
      return {
        id: d.id,
        repositoryId: d.repository_id,
        type: d.doc_type,
        title: d.title,
        description: d.description,
        content: d.content,
        status: d.status,
        confidence: d.confidence,
        versionNumber: d.version_number,
        lastUpdated: d.last_generated_at,
        approvedAt: d.approved_at,
        approvedBy: d.approved_by,
        sourceEvidence: d.source_evidence,
        versions: (d.versions || []).map((v: any) => ({
          id: v.id,
          documentId: v.document_id,
          repositoryId: v.repository_id,
          versionNumber: v.version_number,
          content: v.content,
          changeSummary: v.change_summary,
          createdBy: v.created_by,
          createdAt: v.created_at,
        })),
      };
    } catch {
      const fallbackList = await mockDocumentationService.getDocuments(repositoryId);
      return fallbackList.find((d) => d.type === docType) || fallbackList[0];
    }
  }

  async saveDocument(
    repositoryId: string,
    type: DocSectionType | string,
    content: string,
    changeSummary: string = 'Manual edit in Documentation Workspace'
  ): Promise<DocumentationDocument> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/documentation/${type}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: jsonBody({ content, change_summary: changeSummary }),
      });

      if (!res.ok) {
        return mockDocumentationService.saveDocument(repositoryId, type as DocSectionType, content);
      }

      const d = await res.json();
      return {
        id: d.id,
        repositoryId: d.repository_id,
        type: d.doc_type,
        title: d.title,
        description: d.description,
        content: d.content,
        status: d.status,
        confidence: d.confidence,
        versionNumber: d.version_number,
        lastUpdated: d.last_generated_at,
        approvedAt: d.approved_at,
        approvedBy: d.approved_by,
        sourceEvidence: d.source_evidence,
        versions: d.versions || [],
      };
    } catch {
      return mockDocumentationService.saveDocument(repositoryId, type as DocSectionType, content);
    }
  }

  async regenerateDocument(
    repositoryId: string,
    type: DocSectionType | string
  ): Promise<DocumentationDocument> {
    try {
      const res = await fetch(`${API_BASE}/repositories/${repositoryId}/documentation/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: jsonBody({
          doc_types: [type],
          force_refresh: true,
        }),
      });

      if (!res.ok) {
        return mockDocumentationService.regenerateDocument(repositoryId, type as DocSectionType);
      }

      return await this.getDocument(repositoryId, type);
    } catch {
      return mockDocumentationService.regenerateDocument(repositoryId, type as DocSectionType);
    }
  }

  async generateAllDocuments(
    repositoryId: string,
    docTypes?: string[]
  ): Promise<DocumentationDocument[]> {
    const res = await fetch(`${API_BASE}/repositories/${repositoryId}/documentation/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: jsonBody({
        doc_types: docTypes,
        force_refresh: true,
      }),
    });

    if (!res.ok) {
      return this.getDocuments(repositoryId);
    }

    return this.getDocuments(repositoryId);
  }

  async approveDocument(
    repositoryId: string,
    type: string
  ): Promise<{ documentId: string; status: string; approvedAt: string }> {
    const res = await fetch(`${API_BASE}/repositories/${repositoryId}/documentation/${type}/approve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
    });

    if (!res.ok) {
      throw new Error('Failed to approve document');
    }

    return res.json();
  }

  async getDocumentDiff(
    repositoryId: string,
    type: string,
    v1: number,
    v2: number
  ): Promise<DocumentDiffData> {
    const res = await fetch(
      `${API_BASE}/repositories/${repositoryId}/documentation/${type}/diff?v1=${v1}&v2=${v2}`,
      {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      }
    );

    if (!res.ok) {
      throw new Error('Failed to load version diff');
    }

    const data = await res.json();
    return {
      docType: data.doc_type,
      baseVersion: data.base_version,
      targetVersion: data.target_version,
      diffPatch: data.diff_patch,
      baseContent: data.base_content,
      targetContent: data.target_content,
    };
  }

  async downloadPackage(repositoryId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/repositories/${repositoryId}/documentation/export-package`, {
      headers: getAuthHeader(),
    });

    if (!res.ok) throw new Error('Package export failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${repositoryId}-docs.zip`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async downloadDocument(repositoryId: string, type: string, format: 'markdown' | 'html'): Promise<void> {
    const res = await fetch(
      `${API_BASE}/repositories/${repositoryId}/documentation/${type}/export?format=${format}`,
      {
        headers: getAuthHeader(),
      }
    );

    if (!res.ok) throw new Error(`Export ${format} failed`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${repositoryId}-${type}.${format === 'markdown' ? 'md' : 'html'}`;
    link.click();
    URL.revokeObjectURL(url);
  }
}

function jsonBody(data: any): string {
  return JSON.stringify(data);
}

export const apiDocumentationService = new ApiDocumentationService();
