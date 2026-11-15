import pytest

from app.analysis.python_parser import PythonAstParser
from app.analysis.registry import ParserRegistry
from app.analysis.schemas import ParseStatus, SymbolType
from app.analysis.treesitter_parser import TreeSitterCodeParser


def test_python_function_and_method_extraction():
    parser = PythonAstParser()
    source = """
class UserService:
    '''Service handling user accounts.'''
    def __init__(self, db: Database):
        self.db = db

    def get_user(self, user_id: int = 1, *args, **kwargs) -> Optional[dict]:
        '''Fetch a user by ID.'''
        return {"id": user_id}

    async def async_fetch(self) -> None:
        pass

    def generator_method(self):
        yield 1
        yield 2

def standalone_func(x: str) -> str:
    def nested_func(y: int) -> int:
        return y * 2
    return x
"""
    res = parser.parse_source(source)
    assert res.status == ParseStatus.SUCCESS
    assert res.language == "Python"
    assert res.parser_name == "python_ast"

    # Symbols: UserService, __init__, get_user, async_fetch, generator_method, standalone_func, nested_func
    names = [s.name for s in res.symbols]
    assert "UserService" in names
    assert "__init__" in names
    assert "get_user" in names
    assert "async_fetch" in names
    assert "generator_method" in names
    assert "standalone_func" in names
    assert "nested_func" in names

    # Method check
    get_user = next(s for s in res.symbols if s.name == "get_user")
    assert get_user.symbol_type == SymbolType.METHOD
    assert get_user.scope == "UserService"
    assert get_user.return_type == "Optional[dict]"
    assert get_user.docstring == "Fetch a user by ID."
    assert any(p.name == "self" for p in get_user.parameters)
    assert any(p.name == "user_id" and p.type_annotation == "int" and p.default_value == "1" for p in get_user.parameters)
    assert any(p.name == "*args" and p.is_variadic for p in get_user.parameters)
    assert any(p.name == "**kwargs" and p.is_kwarg for p in get_user.parameters)

    # Async & generator check
    async_fetch = next(s for s in res.symbols if s.name == "async_fetch")
    assert async_fetch.is_async is True

    gen = next(s for s in res.symbols if s.name == "generator_method")
    assert gen.is_generator is True

    # Nested function check
    nested = next(s for s in res.symbols if s.name == "nested_func")
    assert nested.scope == "standalone_func"


def test_python_imports_and_exports():
    parser = PythonAstParser()
    source = """
import os
import sys as system
from pathlib import Path, PurePath
from .models import User
from ..utils import helper

__all__ = ["User", "my_func"]

def my_func():
    pass

def _private_func():
    pass
"""
    res = parser.parse_source(source)
    assert res.status == ParseStatus.SUCCESS

    # Imports
    modules = [imp.source_module for imp in res.imports_exports if imp.statement_type == "import"]
    assert "os" in modules
    assert "sys" in modules
    assert "pathlib" in modules
    assert ".models" in modules
    assert "..utils" in modules

    # Relative imports
    rel_import = next(i for i in res.imports_exports if i.source_module == ".models")
    assert rel_import.is_relative is True

    # Alias check
    alias_import = next(i for i in res.imports_exports if i.source_module == "sys")
    assert alias_import.alias == "system"

    # Export check based on __all__
    my_func = next(s for s in res.symbols if s.name == "my_func")
    assert my_func.is_exported is True

    priv = next(s for s in res.symbols if s.name == "_private_func")
    assert priv.is_exported is False
    assert priv.visibility == "protected"


def test_python_malformed_syntax():
    parser = PythonAstParser()
    bad_code = "def broken_syntax(:\n    return {"
    res = parser.parse_source(bad_code)
    assert res.status == ParseStatus.FAILED
    assert len(res.errors) >= 1
    assert res.errors[0].error_type == "SyntaxError"
    assert res.errors[0].line is not None


def test_empty_source():
    parser = PythonAstParser()
    res = parser.parse_source("")
    assert res.status == ParseStatus.SUCCESS
    assert len(res.symbols) == 0
    assert len(res.errors) == 0


def test_unicode_identifiers():
    parser = PythonAstParser()
    source = """
class CalculateurDonnées:
    def résumé(self, entrée: str) -> str:
        return entrée
"""
    res = parser.parse_source(source)
    assert res.status == ParseStatus.SUCCESS
    names = [s.name for s in res.symbols]
    assert "CalculateurDonnées" in names
    assert "résumé" in names


def test_typescript_tree_sitter_parsing():
    parser = TreeSitterCodeParser("TypeScript")
    source = """
import { Request, Response } from 'express';

export interface User {
    id: string;
    email: string;
}

export class UserService {
    private apiKey: string;

    constructor(key: string) {
        this.apiKey = key;
    }

    async getUser(id: string): Promise<User> {
        return { id, email: 'test@example.com' };
    }
}

export const createToken = (userId: string): string => {
    return 'token-' + userId;
};
"""
    res = parser.parse_source(source)
    assert res.status in (ParseStatus.SUCCESS, ParseStatus.PARTIAL)
    names = [s.name for s in res.symbols]
    assert "User" in names
    assert "UserService" in names
    assert "getUser" in names
    assert "createToken" in names

    user_iface = next(s for s in res.symbols if s.name == "User")
    assert user_iface.symbol_type == SymbolType.INTERFACE
    assert user_iface.is_exported is True

    user_svc = next(s for s in res.symbols if s.name == "UserService")
    assert user_svc.symbol_type == SymbolType.CLASS
    assert user_svc.is_exported is True

    get_user = next(s for s in res.symbols if s.name == "getUser")
    assert get_user.symbol_type == SymbolType.METHOD
    assert get_user.is_async is True
    assert get_user.scope == "UserService"


def test_java_tree_sitter_parsing():
    parser = TreeSitterCodeParser("Java")
    source = """
package com.repomind.demo;

public class MathUtils {
    public static int multiply(int a, int b) {
        return a * b;
    }
}
"""
    res = parser.parse_source(source)
    assert res.status == ParseStatus.SUCCESS
    names = [s.name for s in res.symbols]
    assert "MathUtils" in names
    assert "multiply" in names


def test_go_tree_sitter_parsing():
    parser = TreeSitterCodeParser("Go")
    source = """
package server

type Config struct {
    Port int
}

func StartServer(cfg Config) error {
    return nil
}
"""
    res = parser.parse_source(source)
    assert res.status == ParseStatus.SUCCESS
    names = [s.name for s in res.symbols]
    assert "StartServer" in names


def test_parser_registry():
    py_parser = ParserRegistry.get_parser("Python")
    assert isinstance(py_parser, PythonAstParser)

    ts_parser = ParserRegistry.get_parser("TypeScript")
    assert isinstance(ts_parser, TreeSitterCodeParser)

    ext_parser = ParserRegistry.get_parser(file_path="src/index.js")
    assert isinstance(ext_parser, TreeSitterCodeParser)

    unsupported = ParserRegistry.get_parser("Brainfuck")
    res = unsupported.parse_source("++++++++[>++++<-]>++.")
    assert res.status == ParseStatus.UNSUPPORTED

