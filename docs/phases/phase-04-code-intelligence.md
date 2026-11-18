# Phase 4: Code Intelligence & Static Analysis

## Status: Completed

### Scope & Invariants
- **Multi-Language Detection**: Robust language detection from file extensions, standard project conventions, and shebang lines.
- **AST Parsing Engine**: Full Python AST parsing using Python's native `ast` module; extensible parser interfaces for JavaScript/TypeScript and configuration files.
- **Symbol Extraction**: Extraction of classes, functions, methods, parameters, return types, decorators, docstrings, and exact start/end line bounds.
- **Import & Export Resolution**: Resolves relative and absolute imports to source files across the repository workspace.
- **Cross-File Referencing**: Tracks symbol usage, references, and definitions across repository files.
- **Persistence**: Extracted symbols (`CodeSymbol`) and references (`SymbolReference`) are persisted with repository scoping to support downstream RAG, architecture graphs, execution flow, and dependency analysis.

---

### Core Components & Pipeline

#### 1. Language Detection & File Scanning (`LanguageService`)
- Maps file extensions to programming languages: Python (`.py`), JavaScript (`.js`, `.jsx`), TypeScript (`.ts`, `.tsx`), HTML/CSS, JSON, YAML, Markdown, etc.
- Classifies files as code, documentation, configuration, or assets.

#### 2. AST Visitor & Symbol Extractor (`CodeIntelligenceService`)
- Parses Python source files using `ast.parse` into syntax trees.
- Traverses AST nodes via customized visitors:
  - `FunctionDef` / `AsyncFunctionDef`: extracts name, arguments, docstrings, return type annotations, start and end line numbers.
  - `ClassDef`: extracts class name, base classes, methods, docstrings, and line bounds.
  - `Import` / `ImportFrom`: extracts imported module names, aliases, and imported symbols.
- Robust error tolerance: syntax errors in individual files do not halt repository processing; error details are logged and non-syntax-error files continue processing.

#### 3. Symbol Persistence & Queries (`SymbolRepository`)
- Bulk insertion of extracted symbols with repository and file relational foreign keys.
- Search symbols by name, kind, file path, or query prefix.
- Feeds symbol bounds into Phase 5 chunking for syntax-boundary RAG retrieval.
