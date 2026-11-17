import pytest
from app.analysis.call_resolver import CallResolver
from app.analysis.entry_point_detector import EntryPointDetector
from app.analysis.schemas import ParsedCall, ParsedEndpoint, ParsedImportExport, ParsedSymbol, SymbolType, ConfidenceLevel


def test_call_resolver_local_and_method_resolution():
    workspace_files = ["app/services/auth_service.py"]
    symbols = [
        ParsedSymbol(
            name="AuthService",
            symbol_type=SymbolType.CLASS,
            start_line=1,
            end_line=20,
        ),
        ParsedSymbol(
            name="login",
            symbol_type=SymbolType.METHOD,
            scope="AuthService",
            start_line=5,
            end_line=12,
        ),
        ParsedSymbol(
            name="verify_password",
            symbol_type=SymbolType.METHOD,
            scope="AuthService",
            start_line=14,
            end_line=18,
        ),
    ]

    calls = [
        ParsedCall(
            callee_name="self.verify_password",
            caller_name="AuthService.login",
            callee_attribute="verify_password",
            call_type="method_call",
            line_number=8,
        ),
        ParsedCall(
            callee_name="json.dumps",
            caller_name="AuthService.login",
            callee_attribute="dumps",
            call_type="external",
            line_number=10,
        ),
        ParsedCall(
            callee_name="dynamic_fn()",
            caller_name="AuthService.login",
            call_type="dynamic",
            line_number=11,
        ),
    ]

    resolver = CallResolver(
        workspace_files=workspace_files,
        symbols_by_file={"app/services/auth_service.py": symbols},
        imports_by_file={"app/services/auth_service.py": []},
    )

    resolved = resolver.resolve_calls_for_file("app/services/auth_service.py", calls)
    assert len(resolved) == 3

    # 1. Local method call
    res_local = resolved[0]
    assert res_local.resolution_status == "resolved_internal"
    assert res_local.confidence == "verified"
    assert res_local.callee_symbol_name == "verify_password"
    assert res_local.callee_file_path == "app/services/auth_service.py"

    # 2. External library call
    res_ext = resolved[1]
    assert res_ext.resolution_status == "external"
    assert res_ext.confidence == "verified"

    # 3. Dynamic call
    res_dyn = resolved[2]
    assert res_dyn.resolution_status == "unresolved"
    assert res_dyn.confidence == "unknown"


def test_call_resolver_cross_file_imports():
    workspace_files = ["app/api/auth.py", "app/services/auth_service.py"]

    service_symbols = [
        ParsedSymbol(
            name="login_user",
            symbol_type=SymbolType.FUNCTION,
            start_line=5,
            end_line=15,
        )
    ]

    api_imports = [
        ParsedImportExport(
            statement_type="import",
            source_module="app.services.auth_service",
            symbol_name="login_user",
            alias=None,
            line_number=2,
        )
    ]

    api_calls = [
        ParsedCall(
            callee_name="login_user",
            caller_name="login_route_handler",
            call_type="function_call",
            line_number=8,
        )
    ]

    resolver = CallResolver(
        workspace_files=workspace_files,
        symbols_by_file={
            "app/api/auth.py": [
                ParsedSymbol(name="login_route_handler", symbol_type=SymbolType.FUNCTION, start_line=6, end_line=10)
            ],
            "app/services/auth_service.py": service_symbols,
        },
        imports_by_file={
            "app/api/auth.py": api_imports,
            "app/services/auth_service.py": [],
        },
    )

    resolved = resolver.resolve_calls_for_file("app/api/auth.py", api_calls)
    assert len(resolved) == 1
    res = resolved[0]

    assert res.resolution_status == "resolved_internal"
    assert res.confidence == "verified"
    assert res.callee_file_path == "app/services/auth_service.py"
    assert res.callee_symbol_name == "login_user"


def test_entry_point_detector_diverse_types():
    files = ["main.py", "src/App.tsx", "app/api/users.py", "worker.py"]

    symbols = [
        ParsedSymbol(name="main", symbol_type=SymbolType.FUNCTION, start_line=10, end_line=15),
        ParsedSymbol(name="get_users", symbol_type=SymbolType.FUNCTION, start_line=20, end_line=25),
        ParsedSymbol(name="process_orders", symbol_type=SymbolType.FUNCTION, start_line=5, end_line=12, decorators=["@celery.task"]),
        ParsedSymbol(name="handleSubmit", symbol_type=SymbolType.FUNCTION, start_line=15, end_line=22),
    ]

    # Assign file paths for test symbols
    symbols[0].file_path = "main.py"
    symbols[1].file_path = "app/api/users.py"
    symbols[2].file_path = "worker.py"
    symbols[3].file_path = "src/App.tsx"

    endpoints = [
        ParsedEndpoint(
            http_method="GET",
            path="/api/v1/users",
            handler_name="get_users",
            framework="FastAPI",
            start_line=20,
            end_line=25,
        )
    ]
    endpoints[0].file_path = "app/api/users.py"

    detected = EntryPointDetector.detect_entry_points(
        files=files,
        symbols=symbols,
        endpoints=endpoints,
    )

    types = {e.entry_type for e in detected}
    assert "api_route" in types
    assert "main_entry" in types
    assert "background_job" in types
    assert "frontend_event" in types

    api_entry = next(e for e in detected if e.entry_type == "api_route")
    assert api_entry.display_name == "GET /api/v1/users"
    assert api_entry.confidence == "verified"

    main_entry = next(e for e in detected if e.entry_type == "main_entry")
    assert "main.py" in main_entry.file_path
