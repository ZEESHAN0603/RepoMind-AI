from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import logger
from app.models.repository import Repository
from app.models.repository_update_run import RepositoryUpdateRun
from app.models.repository_version import RepositoryVersion
from app.models.version_file_change import VersionFileChange
from app.models.version_impact_record import VersionImpactRecord
from app.models.version_symbol_change import VersionSymbolChange
from app.repositories.file_repository import FileRepository
from app.repositories.repository_repository import RepositoryRepository
from app.repositories.update_repository import UpdateRepository
from app.services.ai_change_summary_service import AIChangeSummaryService
from app.services.github_service import GitHubService
from app.services.impact_analysis_service import ImpactAnalysisService
from app.services.symbol_diff_service import SymbolDiffService
from app.services.update_detection_service import UpdateDetectionService
from app.services.workspace_service import WorkspaceService


class UpdateService:
    """
    Central business service orchestrating repository update intelligence,
    version comparison, AST symbol diffing, blast-radius calculation, and AI summaries.
    """

    def __init__(
        self,
        workspace_service: Optional[WorkspaceService] = None,
        ai_summary_service: Optional[AIChangeSummaryService] = None,
        impact_analysis_service: Optional[ImpactAnalysisService] = None,
    ) -> None:
        self.workspace_service = workspace_service or WorkspaceService()
        self.ai_summary_service = ai_summary_service or AIChangeSummaryService()
        self.impact_service = impact_analysis_service or ImpactAnalysisService()

    async def get_history(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Returns update history timeline, latest remote commit status, and versions."""
        repo_repo = RepositoryRepository(session)
        update_repo = UpdateRepository(session)

        repo = await repo_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundException("Repository not found")

        runs = await update_repo.list_update_runs_by_repo(repository_id, limit=30)
        versions = await update_repo.list_versions_by_repo(repository_id, limit=30)

        # Check for remote updates if GitHub
        latest_remote_sha = None
        has_pending = False
        if repo.source_type.startswith("github") and repo.repository_url:
            try:
                owner, repo_name = GitHubService.parse_github_url(repo.repository_url)
                target_branch = repo.default_branch or "main"
                latest_remote_sha = await GitHubService.get_latest_commit_sha(owner, repo_name, target_branch)
                if latest_remote_sha and repo.current_commit_sha and latest_remote_sha != repo.current_commit_sha:
                    has_pending = True
            except Exception as e:
                logger.warning("Could not check remote GitHub SHA: %s", e)

        return {
            "repository_id": repository_id,
            "current_commit_sha": repo.current_commit_sha,
            "latest_remote_sha": latest_remote_sha or repo.current_commit_sha,
            "has_pending_updates": has_pending,
            "total_runs": len(runs),
            "update_runs": runs,
            "versions": versions,
        }

    async def run_update_analysis(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
        base_version_id: Optional[str] = None,
        target_version_id: Optional[str] = None,
        base_commit_sha: Optional[str] = None,
        target_commit_sha: Optional[str] = None,
        include_ai_summary: bool = True,
    ) -> RepositoryUpdateRun:
        """
        Executes a complete update analysis between two versions or commits:
        - Detects changed files and categories
        - Computes unified diff patches
        - Diff AST symbols and endpoints (line-shift invariant)
        - Calculates blast radius impact matrix
        - Generates grounded AI explanation
        - Persists all entities in Supabase database
        """
        repo_repo = RepositoryRepository(session)
        update_repo = UpdateRepository(session)
        file_repo = FileRepository(session)

        repo = await repo_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundException("Repository not found")

        # 1. Resolve Target Version
        target_version: Optional[RepositoryVersion] = None
        if target_version_id:
            target_version = await update_repo.get_version_by_id(target_version_id)
        elif target_commit_sha:
            target_version = await update_repo.get_version_by_commit(repository_id, target_commit_sha)
            if not target_version:
                target_version = RepositoryVersion(
                    repository_id=repository_id,
                    version_tag=f"commit:{target_commit_sha[:7]}",
                    commit_sha=target_commit_sha,
                    source_type="github_commit" if repo.source_type.startswith("github") else "snapshot",
                )
                target_version = await update_repo.create_version(target_version)
        else:
            # Default to latest known or workspace snapshot
            target_tag = f"commit:{repo.current_commit_sha[:7]}" if repo.current_commit_sha else f"snapshot:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
            target_version = RepositoryVersion(
                repository_id=repository_id,
                version_tag=target_tag,
                commit_sha=repo.current_commit_sha,
                source_type="github_commit" if repo.source_type.startswith("github") else "snapshot",
            )
            target_version = await update_repo.create_version(target_version)

        # 2. Resolve Base Version
        base_version: Optional[RepositoryVersion] = None
        if base_version_id:
            base_version = await update_repo.get_version_by_id(base_version_id)
        elif base_commit_sha:
            base_version = await update_repo.get_version_by_commit(repository_id, base_commit_sha)

        # 3. Detect File Changes
        # If GitHub compare is possible:
        file_diff_records: List[Dict[str, Any]] = []
        is_github_compare = False

        if repo.source_type.startswith("github") and base_commit_sha and target_commit_sha:
            try:
                owner, repo_name = GitHubService.parse_github_url(repo.repository_url)
                compare_data = await GitHubService.compare_commits(owner, repo_name, base_commit_sha, target_commit_sha)
                if compare_data.get("files"):
                    is_github_compare = True
                    for f in compare_data["files"]:
                        cat = UpdateDetectionService.categorize_file(f["filename"])
                        st = f["status"]
                        change_type = "modified"
                        if st == "added":
                            change_type = "added"
                        elif st == "removed":
                            change_type = "deleted"
                        elif st == "renamed":
                            change_type = "renamed"

                        file_diff_records.append({
                            "path": f["filename"],
                            "old_path": f.get("previous_filename"),
                            "change_type": change_type,
                            "file_category": cat,
                            "additions": f.get("additions", 0),
                            "deletions": f.get("deletions", 0),
                            "old_size_bytes": 0,
                            "new_size_bytes": 0,
                            "old_content_hash": None,
                            "new_content_hash": None,
                            "diff_patch": f.get("patch"),
                            "summary": f"{change_type.capitalize()} {f['filename']} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})",
                        })
            except Exception as e:
                logger.warning("GitHub compare API failed, falling back to local workspace inspection: %s", e)

        # Fallback to local workspace files comparison
        if not is_github_compare:
            workspace_path = self.workspace_service.get_repository_workspace_path(user_id, repository_id)
            current_files: Dict[str, str] = {}
            if workspace_path.exists():
                for p in workspace_path.rglob("*"):
                    if p.is_file() and not any(part.startswith(".git") for part in p.parts):
                        rel = p.relative_to(workspace_path).as_posix()
                        try:
                            # Read text files up to 1 MB for diff
                            if p.stat().st_size <= 1024 * 1024:
                                current_files[rel] = p.read_text(encoding="utf-8", errors="ignore")
                            else:
                                current_files[rel] = ""
                        except Exception:
                            current_files[rel] = ""

            # Resolve baseline files from snapshot or database
            base_file_map: Dict[str, str] = {}

            # 1. Attempt to load base files from workspace snapshot
            base_snap_tag = base_version.version_tag if base_version else "baseline"
            snap_path = self.workspace_service.get_snapshot_path(user_id, repository_id, base_snap_tag)
            if not snap_path.exists() and base_snap_tag != "baseline":
                snap_path = self.workspace_service.get_snapshot_path(user_id, repository_id, "baseline")

            if snap_path.exists():
                for p in snap_path.rglob("*"):
                    if p.is_file() and not any(part.startswith(".git") for part in p.parts):
                        rel = p.relative_to(snap_path).as_posix()
                        try:
                            if p.stat().st_size <= 1024 * 1024:
                                base_file_map[rel] = p.read_text(encoding="utf-8", errors="ignore")
                            else:
                                base_file_map[rel] = ""
                        except Exception:
                            base_file_map[rel] = ""

            # 2. Fallback to database files if snapshot not present
            if not base_file_map:
                if base_version:
                    prior_runs = await update_repo.list_update_runs_by_repo(repository_id)
                    for pr in prior_runs:
                        if pr.target_version_id == base_version.id:
                            for pfc in pr.file_changes:
                                if pfc.change_type != "deleted":
                                    base_file_map[pfc.path] = ""

                if not base_file_map:
                    db_files = await file_repo.list_files_by_repo(repository_id)
                    for db_f in db_files:
                        if db_f.file_type == "file":
                            base_file_map[db_f.path] = ""

            file_diff_records = UpdateDetectionService.detect_file_changes(
                base_files=base_file_map,
                target_files=current_files,
            )

        # 4. AST Symbol Diffing for Modified Source Files
        symbol_diff_records: List[Dict[str, Any]] = []
        workspace_path = self.workspace_service.get_repository_workspace_path(user_id, repository_id)

        for fc in file_diff_records:
            if fc["file_category"] == "source":
                target_code = ""
                base_code = base_file_map.get(fc.get("old_path") or fc["path"], "")
                # Attempt to read current target code from disk
                target_file_disk = workspace_path / fc["path"]
                if target_file_disk.is_file():
                    try:
                        target_code = target_file_disk.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        target_code = ""

                # If patch diff is available and it's a modification, reconstruct approximate base
                # or run SymbolDiffService
                try:
                    sym_diffs = SymbolDiffService.diff_file_symbols(
                        base_code=base_code if fc["change_type"] != "added" else "",
                        target_code=target_code if fc["change_type"] != "deleted" else "",
                        file_path=fc["path"],
                    )
                    for sd in sym_diffs:
                        sd["file_path"] = fc["path"]
                        symbol_diff_records.append(sd)
                except Exception as ex:
                    logger.warning("Symbol diff extraction failed for %s: %s", fc["path"], ex)

        # 5. Blast-Radius Impact Analysis
        impact_result = await self.impact_service.compute_impact(
            session=session,
            repository_id=repository_id,
            changed_files=file_diff_records,
            changed_symbols=symbol_diff_records,
        )

        impact_records = impact_result["impact_records"]
        impact_metrics = impact_result["metrics"]

        # Aggregate line stats
        total_adds = sum(f.get("additions", 0) for f in file_diff_records)
        total_dels = sum(f.get("deletions", 0) for f in file_diff_records)

        # 6. AI Change Summary
        ai_summary_md = None
        ai_status = "pending"
        if include_ai_summary and (file_diff_records or symbol_diff_records):
            ai_status = "generating"
            base_ref_tag = base_version.version_tag if base_version else (base_commit_sha or "base")
            target_ref_tag = target_version.version_tag
            try:
                ai_res = await self.ai_summary_service.generate_change_summary(
                    repository_name=repo.name,
                    base_ref=base_ref_tag,
                    target_ref=target_ref_tag,
                    file_changes=file_diff_records,
                    symbol_changes=symbol_diff_records,
                    impact_metrics=impact_metrics,
                )
                ai_summary_md = ai_res.get("ai_summary_markdown")
                ai_status = "completed"
            except Exception as e:
                logger.warning("AI summary generation error: %s", e)
                ai_status = "failed"

        # 7. Persist Update Run and Associations
        run = RepositoryUpdateRun(
            repository_id=repository_id,
            base_version_id=base_version.id if base_version else None,
            target_version_id=target_version.id,
            base_commit_sha=base_commit_sha or (base_version.commit_sha if base_version else None),
            target_commit_sha=target_commit_sha or target_version.commit_sha,
            status="completed",
            total_files_changed=len(file_diff_records),
            total_symbols_changed=len(symbol_diff_records),
            total_additions=total_adds,
            total_deletions=total_dels,
            impact_summary_json=json.dumps(impact_metrics),
            ai_summary_markdown=ai_summary_md,
            ai_summary_status=ai_status,
            analyzed_at=datetime.now(timezone.utc),
        )
        saved_run = await update_repo.create_update_run(run)

        # Save File Changes
        file_entities: List[VersionFileChange] = []
        path_to_file_change: Dict[str, VersionFileChange] = {}

        for fd in file_diff_records:
            vfc = VersionFileChange(
                update_run_id=saved_run.id,
                path=fd["path"],
                old_path=fd.get("old_path"),
                change_type=fd["change_type"],
                file_category=fd["file_category"],
                additions=fd.get("additions", 0),
                deletions=fd.get("deletions", 0),
                old_size_bytes=fd.get("old_size_bytes", 0),
                new_size_bytes=fd.get("new_size_bytes", 0),
                old_content_hash=fd.get("old_content_hash"),
                new_content_hash=fd.get("new_content_hash"),
                diff_patch=fd.get("diff_patch"),
                summary=fd.get("summary"),
            )
            file_entities.append(vfc)
            path_to_file_change[fd["path"]] = vfc

        if file_entities:
            await update_repo.save_file_changes_batch(file_entities)

        # Save Symbol Changes
        symbol_entities: List[VersionSymbolChange] = []
        for sd in symbol_diff_records:
            fc_obj = path_to_file_change.get(sd.get("file_path", ""))
            vsc = VersionSymbolChange(
                update_run_id=saved_run.id,
                file_change_id=fc_obj.id if fc_obj else None,
                symbol_name=sd["symbol_name"],
                symbol_type=sd["symbol_type"],
                scope=sd.get("scope"),
                change_type=sd["change_type"],
                old_signature=sd.get("old_signature"),
                new_signature=sd.get("new_signature"),
                evidence_json=json.dumps(sd.get("evidence", {})),
            )
            symbol_entities.append(vsc)

        if symbol_entities:
            await update_repo.save_symbol_changes_batch(symbol_entities)

        # Save Impact Records
        impact_entities: List[VersionImpactRecord] = []
        for ir in impact_records:
            vir = VersionImpactRecord(
                update_run_id=saved_run.id,
                affected_type=ir["affected_type"],
                affected_identifier=ir["affected_identifier"],
                affected_path=ir["affected_path"],
                impact_level=ir["impact_level"],
                evidence_reason=ir["evidence_reason"],
                depth=ir.get("depth", 1),
            )
            impact_entities.append(vir)

        if impact_entities:
            await update_repo.save_impact_records_batch(impact_entities)

        # Mark affected approved documentation sections as stale (outdated)
        impacted_doc_types: Set[str] = set()
        if file_diff_records:
            impacted_doc_types.add("update_changelog")
        for fd in file_diff_records:
            cat = fd.get("file_category")
            if cat == "manifest":
                impacted_doc_types.update(["dependencies", "readme"])
            elif cat == "source":
                impacted_doc_types.update(["api", "code_reference", "execution_flow", "architecture"])
            elif cat == "config":
                impacted_doc_types.update(["readme", "architecture"])
            elif cat == "documentation":
                impacted_doc_types.add("readme")

        if impacted_doc_types:
            from app.repositories.documentation_repository import DocumentationRepository
            doc_repo = DocumentationRepository(session)
            await doc_repo.mark_documents_as_stale(repository_id, list(impacted_doc_types))

        await session.commit()

        # Create updated version snapshot on disk
        try:
            self.workspace_service.create_snapshot(user_id, repository_id, target_version.version_tag)
        except Exception as snap_err:
            logger.warning("Could not snapshot target version %s: %s", target_version.version_tag, snap_err)

        # Re-fetch populated run
        full_run = await update_repo.get_update_run_by_id(saved_run.id)
        return full_run or saved_run

    async def get_update_run_detail(
        self,
        session: AsyncSession,
        repository_id: str,
        update_run_id: str,
    ) -> Dict[str, Any]:
        """Retrieves complete details of an update run."""
        update_repo = UpdateRepository(session)
        run = await update_repo.get_update_run_by_id(update_run_id)
        if not run or run.repository_id != repository_id:
            raise NotFoundException("Update analysis run not found")

        file_changes = await update_repo.list_file_changes_by_run(update_run_id)
        symbol_changes = await update_repo.list_symbol_changes_by_run(update_run_id)
        impact_records = await update_repo.list_impact_records_by_run(update_run_id)

        try:
            impact_metrics = json.loads(run.impact_summary_json)
        except Exception:
            impact_metrics = {}

        return {
            "run": run,
            "stats": {
                "files_changed": run.total_files_changed,
                "additions": run.total_additions,
                "deletions": run.total_deletions,
                "symbols_changed": run.total_symbols_changed,
                "endpoints_affected": len([s for s in symbol_changes if s.symbol_type == "endpoint"]),
            },
            "impact_metrics": impact_metrics,
            "impact_summary": impact_metrics,
            "file_changes": file_changes,
            "symbol_changes": symbol_changes,
            "impact_records": impact_records,
        }

    async def get_impact_graph(
        self,
        session: AsyncSession,
        repository_id: str,
        update_run_id: str,
    ) -> Dict[str, Any]:
        """Returns interactive nodes and edges for blast radius graph visualization."""
        detail = await self.get_update_run_detail(session, repository_id, update_run_id)
        return ImpactAnalysisService.build_impact_graph(
            update_run_id=update_run_id,
            file_changes=detail["file_changes"],
            impact_records=detail["impact_records"],
        )
