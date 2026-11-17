import html
import io
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import zipfile

from app.models.repository import Repository
from app.models.repository_document import RepositoryDocument


class DocumentationExportService:
    """Provides export packaging for Markdown, standalone HTML, and complete ZIP documentation archives."""

    @classmethod
    def export_as_markdown(cls, document: RepositoryDocument) -> Tuple[bytes, str]:
        """Returns Markdown bytes and suggested download filename."""
        filename = f"{document.doc_type}.md"
        content_bytes = document.content.encode("utf-8")
        return content_bytes, filename

    @classmethod
    def export_as_html(cls, document: RepositoryDocument, repository: Repository) -> Tuple[bytes, str]:
        """
        Synthesizes a self-contained, offline-compatible HTML document with typography
        and Mermaid.js integration for diagram rendering.
        """
        escaped_title = html.escape(f"{repository.name} — {document.title}")
        js_json_content = json.dumps(document.content)
        filename = f"{document.doc_type}.html"

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --text: #f8fafc;
      --muted: #94a3b8;
      --border: #334155;
      --primary: #3b82f6;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      background: var(--bg);
      color: var(--text);
      max-width: 900px;
      margin: 0 auto;
      padding: 2rem 1.5rem;
    }}
    header {{
      border-bottom: 1px solid var(--border);
      padding-bottom: 1.5rem;
      margin-bottom: 2rem;
    }}
    h1, h2, h3, h4 {{ color: #ffffff; font-weight: 700; }}
    a {{ color: var(--primary); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    pre, code {{
      background: var(--card-bg);
      border-radius: 6px;
      font-family: "JetBrains Mono", Menlo, Monaco, Consolas, monospace;
    }}
    code {{ padding: 0.2rem 0.4rem; font-size: 0.875rem; }}
    pre {{ padding: 1rem; overflow-x: auto; border: 1px solid var(--border); }}
    table {{ width: 100%; border-collapse: collapse; margin: 1.5rem 0; }}
    th, td {{ border: 1px solid var(--border); padding: 0.6rem 0.8rem; text-align: left; }}
    th {{ background: var(--card-bg); font-weight: 600; }}
    blockquote {{ border-left: 4px solid var(--primary); margin: 1.5rem 0; padding-left: 1rem; color: var(--muted); }}
    .mermaid {{ background: var(--card-bg); padding: 1rem; border-radius: 8px; margin: 1.5rem 0; border: 1px solid var(--border); text-align: center; }}
    .meta-badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; background: #1e3a8a; color: #93c5fd; margin-right: 0.5rem; }}
    @media print {{
      body {{ background: #fff; color: #000; max-width: 100%; padding: 0; }}
      pre, code, .mermaid {{ background: #f8fafc; color: #000; border-color: #e2e8f0; }}
    }}
  </style>
</head>
<body>
  <header>
    <div style="margin-bottom: 0.5rem;">
      <span class="meta-badge">{html.escape(document.doc_type.upper())}</span>
      <span class="meta-badge">{html.escape(document.status.upper())}</span>
      <span class="meta-badge">v{document.version_number}</span>
    </div>
    <h1>{escaped_title}</h1>
    <p style="color: var(--muted); margin: 0;">Generated automatically by RepoMind Repository Intelligence</p>
  </header>
  <main id="content"></main>

  <script>
    mermaid.initialize({{ startOnLoad: false, theme: 'dark' }});
    const markdownText = {js_json_content};
    document.getElementById('content').innerHTML = marked.parse(markdownText);

    // Transform mermaid code blocks
    document.querySelectorAll('pre code.language-mermaid').forEach((block) => {{
      const pre = block.parentElement;
      const chart = block.textContent;
      const div = document.createElement('div');
      div.className = 'mermaid';
      div.textContent = chart;
      pre.replaceWith(div);
    }});
    mermaid.run();
  </script>
</body>
</html>"""
        return html_template.encode("utf-8"), filename

    @classmethod
    def export_as_zip_package(
        cls,
        repository: Repository,
        documents: List[RepositoryDocument],
    ) -> Tuple[bytes, str]:
        """
        Packages all documents into an in-memory streaming ZIP archive.
        """
        zip_buffer = io.BytesIO()
        repo_slug = repository.name.lower().replace(" ", "-")
        root_folder = f"{repo_slug}-docs"

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for doc in documents:
                file_name = f"{doc.doc_type}.md"
                zf.writestr(f"{root_folder}/{file_name}", doc.content)

            # Add an index / manifest file
            index_content = [
                f"# Documentation Package: {repository.name}",
                "",
                f"- Repository URL: {repository.repository_url}",
                f"- Generated Documents: {len(documents)}",
                "",
                "## Table of Contents",
                "",
            ]
            for doc in documents:
                index_content.append(f"- [{doc.title}]({doc.doc_type}.md) — {doc.description}")

            zf.writestr(f"{root_folder}/INDEX.md", "\n".join(index_content) + "\n")

        zip_buffer.seek(0)
        archive_name = f"{repo_slug}-documentation.zip"
        return zip_buffer.getvalue(), archive_name
