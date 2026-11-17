import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from app.analysis.registry import ParserRegistry
from app.analysis.schemas import (
    ConfidenceLevel,
    FileParseResult,
    ParsedEndpoint,
    ParsedImportExport,
    ParsedSymbol,
    ParseStatus,
)
from app.core.logging import logger


class SymbolDiffService:
    """
    Extracts and diffs code symbols (functions, methods, classes, endpoints, imports)
    across repository versions with strict line-shift invariance.
    """

    @classmethod
    def normalize_symbol_body(cls, code: str, start_line: int, end_line: int) -> str:
        """Extracts and normalizes symbol source lines, ignoring variable whitespace."""
        lines = code.splitlines()
        # 1-indexed line numbers
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        slice_lines = lines[start_idx:end_idx]
        # Strip trailing/leading space from each line
        normalized = "\n".join(l.strip() for l in slice_lines if l.strip())
        return normalized

    @classmethod
    def hash_body(cls, normalized_body: str) -> str:
        return hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()

    @classmethod
    def diff_file_symbols(
        cls,
        base_code: Optional[str],
        target_code: Optional[str],
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """
        Parses base and target code using language AST parsers and identifies
        added, modified, deleted, and renamed code symbols.
        Guarantees that pure line shifts do NOT mark a function as modified.
        """
        parser = ParserRegistry.get_parser_for_file(file_path)
        if not parser:
            return []

        base_res: Optional[FileParseResult] = None
        target_res: Optional[FileParseResult] = None

        if base_code and base_code.strip():
            try:
                base_res = parser.parse_source(base_code, file_path)
            except Exception as e:
                logger.warning("Failed to parse base source %s: %s", file_path, e)

        if target_code and target_code.strip():
            try:
                target_res = parser.parse_source(target_code, file_path)
            except Exception as e:
                logger.warning("Failed to parse target source %s: %s", file_path, e)

        base_symbols: List[ParsedSymbol] = base_res.symbols if base_res else []
        target_symbols: List[ParsedSymbol] = target_res.symbols if target_res else []

        # Index symbols by (symbol_type, scope, name)
        base_map: Dict[Tuple[str, str, str], ParsedSymbol] = {
            (s.symbol_type.value, s.scope or "", s.name): s for s in base_symbols
        }
        target_map: Dict[Tuple[str, str, str], ParsedSymbol] = {
            (s.symbol_type.value, s.scope or "", s.name): s for s in target_symbols
        }

        diff_results: List[Dict[str, Any]] = []

        base_keys = set(base_map.keys())
        target_keys = set(target_map.keys())

        added_keys = target_keys - base_keys
        deleted_keys = base_keys - target_keys
        common_keys = base_keys & target_keys

        # Check for potential renames: same (symbol_type, scope), deleted key & added key with identical body hash
        renamed_pairs: Dict[Tuple[str, str, str], Tuple[str, str, str]] = {}  # target_key -> base_key
        if base_code and target_code:
            deleted_by_body: Dict[str, Tuple[str, str, str]] = {}
            for k in deleted_keys:
                bs = base_map[k]
                body = cls.normalize_symbol_body(base_code, bs.start_line, bs.end_line)
                if body:
                    deleted_by_body[cls.hash_body(body)] = k

            for ak in list(added_keys):
                ts = target_map[ak]
                body = cls.normalize_symbol_body(target_code, ts.start_line, ts.end_line)
                b_hash = cls.hash_body(body) if body else ""
                if b_hash in deleted_by_body:
                    old_k = deleted_by_body.pop(b_hash)
                    renamed_pairs[ak] = old_k

        # 1. Process Renamed & Added Symbols
        for ak in sorted(added_keys):
            ts = target_map[ak]
            if ak in renamed_pairs:
                old_k = renamed_pairs[ak]
                old_s = base_map[old_k]
                deleted_keys.discard(old_k)
                diff_results.append({
                    "symbol_name": ts.name,
                    "symbol_type": ts.symbol_type.value,
                    "scope": ts.scope,
                    "change_type": "renamed",
                    "old_signature": old_s.signature or f"{old_s.name}(...)",
                    "new_signature": ts.signature or f"{ts.name}(...)",
                    "evidence": {
                        "renamed_from": old_s.name,
                        "old_scope": old_s.scope,
                        "normalized_body_matched": True,
                        "is_breaking": True,
                    },
                })
            else:
                diff_results.append({
                    "symbol_name": ts.name,
                    "symbol_type": ts.symbol_type.value,
                    "scope": ts.scope,
                    "change_type": "added",
                    "old_signature": None,
                    "new_signature": ts.signature or f"{ts.name}(...)",
                    "evidence": {
                        "is_async": ts.is_async,
                        "parameters": [p.to_dict() for p in ts.parameters],
                        "return_type": ts.return_type,
                        "decorators": ts.decorators,
                    },
                })

        # 2. Process Deleted Symbols
        for dk in sorted(deleted_keys):
            bs = base_map[dk]
            diff_results.append({
                "symbol_name": bs.name,
                "symbol_type": bs.symbol_type.value,
                "scope": bs.scope,
                "change_type": "deleted",
                "old_signature": bs.signature or f"{bs.name}(...)",
                "new_signature": None,
                "evidence": {
                    "was_exported": bs.is_exported,
                    "visibility": bs.visibility,
                    "is_breaking": True,
                },
            })

        # 3. Process Modified Symbols (Strict Line-Shift Invariance)
        for ck in sorted(common_keys):
            bs = base_map[ck]
            ts = target_map[ck]

            modifications: List[str] = []
            is_breaking = False

            # Check signature / parameter differences
            if (bs.signature or "").strip() != (ts.signature or "").strip():
                modifications.append("signature_changed")

            # Check parameter lists
            old_params = [p.name for p in bs.parameters]
            new_params = [p.name for p in ts.parameters]
            if old_params != new_params:
                modifications.append(f"parameters_changed: {old_params} -> {new_params}")
                # If new parameters without defaults added, mark breaking
                new_required = [p.name for p in ts.parameters if not p.is_optional and p.default_value is None]
                if len(new_required) > len([p.name for p in bs.parameters if not p.is_optional and p.default_value is None]):
                    is_breaking = True

            # Check return type
            if bs.return_type != ts.return_type:
                modifications.append(f"return_type_changed: {bs.return_type} -> {ts.return_type}")

            # Check decorators
            if bs.decorators != ts.decorators:
                modifications.append(f"decorators_changed: {bs.decorators} -> {ts.decorators}")

            # Check body AST / content change
            body_changed = False
            if base_code and target_code:
                old_body = cls.normalize_symbol_body(base_code, bs.start_line, bs.end_line)
                new_body = cls.normalize_symbol_body(target_code, ts.start_line, ts.end_line)
                if old_body != new_body:
                    body_changed = True
                    modifications.append("body_content_changed")

            # LINE NUMBER SHIFT CHECK:
            # If ONLY the line numbers changed, and no signature, parameters, return type,
            # decorators, or normalized body changed, it is NOT modified!
            if not modifications and not body_changed:
                continue

            diff_results.append({
                "symbol_name": ts.name,
                "symbol_type": ts.symbol_type.value,
                "scope": ts.scope,
                "change_type": "modified",
                "old_signature": bs.signature or f"{bs.name}(...)",
                "new_signature": ts.signature or f"{ts.name}(...)",
                "evidence": {
                    "modifications": modifications,
                    "is_breaking": is_breaking,
                    "old_lines": f"{bs.start_line}-{bs.end_line}",
                    "new_lines": f"{ts.start_line}-{ts.end_line}",
                },
            })

        # 4. Check Endpoints diffs
        base_eps: List[ParsedEndpoint] = base_res.endpoints if base_res else []
        target_eps: List[ParsedEndpoint] = target_res.endpoints if target_res else []

        base_ep_map = {(ep.http_method.upper(), ep.path): ep for ep in base_eps}
        target_ep_map = {(ep.http_method.upper(), ep.path): ep for ep in target_eps}

        for (m, p), tep in target_ep_map.items():
            if (m, p) not in base_ep_map:
                diff_results.append({
                    "symbol_name": f"{m} {p}",
                    "symbol_type": "endpoint",
                    "scope": tep.framework,
                    "change_type": "added",
                    "old_signature": None,
                    "new_signature": f"{m} {p} -> {tep.handler_name}",
                    "evidence": {"handler": tep.handler_name, "framework": tep.framework},
                })
            else:
                bep = base_ep_map[(m, p)]
                if bep.handler_name != tep.handler_name:
                    diff_results.append({
                        "symbol_name": f"{m} {p}",
                        "symbol_type": "endpoint",
                        "scope": tep.framework,
                        "change_type": "modified",
                        "old_signature": f"{m} {p} -> {bep.handler_name}",
                        "new_signature": f"{m} {p} -> {tep.handler_name}",
                        "evidence": {"handler_changed": f"{bep.handler_name} -> {tep.handler_name}"},
                    })

        for (m, p), bep in base_ep_map.items():
            if (m, p) not in target_ep_map:
                diff_results.append({
                    "symbol_name": f"{m} {p}",
                    "symbol_type": "endpoint",
                    "scope": bep.framework,
                    "change_type": "deleted",
                    "old_signature": f"{m} {p} -> {bep.handler_name}",
                    "new_signature": None,
                    "evidence": {"is_breaking": True, "removed_endpoint": f"{m} {p}"},
                })

        return diff_results
