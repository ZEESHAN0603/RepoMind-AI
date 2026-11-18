import type { DocumentationService } from './intelligence.service';
import type { DocSectionType, DocumentationDocument, DocumentDiffData } from '@/types';
import { apiFetch } from './client';

export class ApiDocumentationService implements DocumentationService {
  async getDocuments(repositoryId: string): Promise<DocumentationDocument[]> {
    const res = await apiFetch(`/repositories/${repositoryId}/documentation`);
    if (!res.ok) {
      if (res.status === 404) return [];
      throw new Error(`Failed to load documentation list: ${res.statusText}`);
    }

    const data = await res.json();
    if (!data.items || !Array.isArray(data.items) || data.items.length === 0) {
      return [];
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
          content: `# ${item.title}\n\nContent is being generated.`,
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
  }

  async getDocument(repositoryId: string, docType: string): Promise<DocumentationDocument> {
    const res = await apiFetch(`/repositories/${repositoryId}/documentation/${docType}`);
    if (!res.ok) {
      throw new Error(`Failed to load document '${docType}': ${res.statusText}`);
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
  }

  async saveDocument(
    repositoryId: string,
    type: DocSectionType | string,
    content: string,
    changeSummary: string = 'Manual edit in Documentation Workspace'
  ): Promise<DocumentationDocument> {
    const res = await apiFetch(`/repositories/${repositoryId}/documentation/${type}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ content, change_summary: changeSummary }),
    });

    if (!res.ok) {
      throw new Error(`Failed to save document: ${res.statusText}`);
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
  }

  async regenerateDocument(
    repositoryId: string,
    type: DocSectionType | string
  ): Promise<DocumentationDocument> {
    const res = await apiFetch(`/repositories/${repositoryId}/documentation/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        doc_types: [type],
        force_refresh: true,
      }),
    });

    if (!res.ok) {
      throw new Error(`Failed to regenerate document: ${res.statusText}`);
    }

    return await this.getDocument(repositoryId, type);
  }

  async generateAllDocuments(
    repositoryId: string,
    docTypes?: string[]
  ): Promise<DocumentationDocument[]> {
    const res = await apiFetch(`/repositories/${repositoryId}/documentation/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        doc_types: docTypes,
        force_refresh: true,
      }),
    });

    if (!res.ok) {
      throw new Error(`Failed to generate documentation package: ${res.statusText}`);
    }

    return this.getDocuments(repositoryId);
  }

  async approveDocument(
    repositoryId: string,
    type: string
  ): Promise<{ documentId: string; status: string; approvedAt: string }> {
    const res = await apiFetch(`/repositories/${repositoryId}/documentation/${type}/approve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!res.ok) {
      throw new Error(`Failed to approve document: ${res.statusText}`);
    }

    return res.json();
  }

  async getDocumentDiff(
    repositoryId: string,
    type: string,
    v1: number,
    v2: number
  ): Promise<DocumentDiffData> {
    const res = await apiFetch(
      `/repositories/${repositoryId}/documentation/${type}/diff?v1=${v1}&v2=${v2}`
    );

    if (!res.ok) {
      throw new Error(`Failed to load version diff: ${res.statusText}`);
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
    const res = await apiFetch(`/repositories/${repositoryId}/documentation/export-package`);
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
    const res = await apiFetch(
      `/repositories/${repositoryId}/documentation/${type}/export?format=${format}`
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

export const apiDocumentationService = new ApiDocumentationService();
