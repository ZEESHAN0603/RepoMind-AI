import pytest
from app.analysis.python_parser import PythonAstParser
from app.analysis.treesitter_parser import TreeSitterCodeParser
from app.analysis.schemas import ParseStatus, ConfidenceLevel


def test_python_direct_function_call():
    code = """
def greet(name: str):
    print("Hello " + name)
    log_event("greet_called")
"""
    parser = PythonAstParser()
    res = parser.parse_source(code, file_path="main.py")

    assert res.status == ParseStatus.SUCCESS
    assert len(res.symbols) == 1
    assert res.symbols[0].name == "greet"

    # Calls extracted
    assert len(res.calls) == 2
    callee_names = [c.callee_name for c in res.calls]
    assert "print" in callee_names
    assert "log_event" in callee_names

    for c in res.calls:
        assert c.caller_name == "greet"
        assert c.confidence == ConfidenceLevel.VERIFIED


def test_python_nested_and_chained_calls():
    code = """
def compute():
    result = math.sqrt(math.pow(2, 8))
    return str(result).strip()
"""
    parser = PythonAstParser()
    res = parser.parse_source(code, file_path="math_utils.py")

    assert res.status == ParseStatus.SUCCESS
    assert len(res.calls) >= 3

    callee_names = [c.callee_name for c in res.calls]
    assert any("sqrt" in name for name in callee_names)
    assert any("pow" in name for name in callee_names)
    assert any("strip" in name for name in callee_names)


def test_python_class_methods_and_self_calls():
    code = """
class AuthService:
    def __init__(self, repo):
        self.repo = repo

    def login(self, username, password):
        user = self.repo.get_by_username(username)
        if not self.verify_password(password, user.hash):
            raise ValueError("Invalid")
        return self.generate_token(user)

    def verify_password(self, plain, hashed):
        return hash_pwd(plain) == hashed

    def generate_token(self, user):
        return jwt.encode({"sub": user.id}, "secret")
"""
    parser = PythonAstParser()
    res = parser.parse_source(code, file_path="auth_service.py")

    assert res.status == ParseStatus.SUCCESS
    symbols = {s.name: s for s in res.symbols}
    assert "AuthService" in symbols
    assert "login" in symbols

    # Check calls in login
    login_calls = [c for c in res.calls if c.caller_name == "AuthService.login"]
    assert len(login_calls) >= 3

    login_callees = [c.callee_name for c in login_calls]
    assert any("get_by_username" in c for c in login_callees)
    assert any("verify_password" in c for c in login_callees)
    assert any("generate_token" in c for c in login_callees)

    # Check caller attribution in verify_password
    verify_calls = [c for c in res.calls if c.caller_name == "AuthService.verify_password"]
    assert len(verify_calls) == 1
    assert verify_calls[0].callee_name == "hash_pwd"


def test_python_nested_functions_caller_attribution():
    code = """
def outer_task():
    setup()
    def inner_step():
        step_one()
        step_two()
    inner_step()
    cleanup()
"""
    parser = PythonAstParser()
    res = parser.parse_source(code, file_path="pipeline.py")

    assert res.status == ParseStatus.SUCCESS
    outer_calls = [c for c in res.calls if c.caller_name == "outer_task"]
    inner_calls = [c for c in res.calls if c.caller_name == "outer_task.inner_step"]

    outer_callees = [c.callee_name for c in outer_calls]
    inner_callees = [c.callee_name for c in inner_calls]

    assert "setup" in outer_callees
    assert "inner_step" in outer_callees
    assert "cleanup" in outer_callees

    assert "step_one" in inner_callees
    assert "step_two" in inner_callees


def test_python_top_level_module_calls():
    code = """
import logging

setup_logging()
app = create_app()
app.include_router(auth_router)
"""
    parser = PythonAstParser()
    res = parser.parse_source(code, file_path="app.py")

    assert res.status == ParseStatus.SUCCESS
    module_calls = [c for c in res.calls if c.caller_name is None]
    assert len(module_calls) >= 2
    callees = [c.callee_name for c in module_calls]
    assert any("setup_logging" in c for c in callees)
    assert any("create_app" in c for c in callees)


def test_treesitter_typescript_function_and_method_calls():
    code = """
import { apiClient } from './api';

export async function submitOrder(orderId: string, items: any[]) {
    validateOrder(orderId);
    const res = await apiClient.post('/orders', { id: orderId, items });
    notifyUser("Order placed");
    return res.data;
}
"""
    parser = TreeSitterCodeParser("TypeScript")
    res = parser.parse_source(code, file_path="orderService.ts")

    assert res.status == ParseStatus.SUCCESS
    assert len(res.symbols) >= 1

    calls = [c for c in res.calls if c.caller_name == "submitOrder"]
    assert len(calls) >= 3

    callee_names = [c.callee_name for c in calls]
    assert any("validateOrder" in c for c in callee_names)
    assert any("apiClient.post" in c for c in callee_names)
    assert any("notifyUser" in c for c in callee_names)


def test_treesitter_arrow_functions_and_classes():
    code = """
class UserService {
    private client: any;

    constructor(client: any) {
        this.client = client;
    }

    findUser = async (userId: string) => {
        this.logAudit(userId);
        return await this.client.get('/users/' + userId);
    };

    private logAudit(id: string) {
        console.log("Auditing: " + id);
    }
}
"""
    parser = TreeSitterCodeParser("TypeScript")
    res = parser.parse_source(code, file_path="userService.ts")

    assert res.status == ParseStatus.SUCCESS

    # Find calls in findUser arrow function
    find_user_calls = [c for c in res.calls if "findUser" in (c.caller_name or "")]
    assert len(find_user_calls) >= 2

    callees = [c.callee_name for c in find_user_calls]
    assert any("logAudit" in c for c in callees)
    assert any("client.get" in c for c in callees)
