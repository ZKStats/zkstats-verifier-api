import pytest
from lib import extract_safe_computation, ExtractComputationFailure

def test_extract_safe_computation_valid():
    valid_computation = """
def computation(state: State, args: Args):
    x = args["x"]
    y = args["y"]
    return state.mean(x), state.mean(y)
    """
    module_path = "test_module.py"
    result = extract_safe_computation(valid_computation, module_path)
    assert callable(result)

def test_extract_safe_computation_valid_no_type_hint():
    valid_computation = """
def computation(state, args):
    x = args["x"]
    y = args["y"]
    return state.mean(x), state.mean(y)
    """
    module_path = "test_module.py"
    result = extract_safe_computation(valid_computation, module_path)
    assert callable(result)

def test_extract_safe_computation_import_statement():
    invalid_computation = """
import os

def computation(state, args):
    return os.getcwd()
    """
    module_path = "test_module.py"
    with pytest.raises(ExtractComputationFailure):
        extract_safe_computation(invalid_computation, module_path)

def test_extract_safe_computation_exec():
    invalid_computation = """
def computation(state, args):
    exec("print('This should not be allowed')")
    return 0
    """
    module_path = "test_module.py"
    with pytest.raises(ExtractComputationFailure):
        extract_safe_computation(invalid_computation, module_path)

def test_extract_safe_computation_eval():
    invalid_computation = """
def computation(state, args):
    return eval("__import__('os').system('ls')")
    """
    module_path = "test_module.py"
    with pytest.raises(ExtractComputationFailure):
        extract_safe_computation(invalid_computation, module_path)

def test_extract_safe_computation_globals():
    invalid_computation = """
def computation(state, args):
    return globals()['__builtins__']['__import__']('os').system('ls')
    """
    module_path = "test_module.py"
    with pytest.raises(ExtractComputationFailure):
        extract_safe_computation(invalid_computation, module_path)

def test_extract_safe_computation_allowed_functions():
    valid_computation = """
def computation(state, args):
    import torch
    return torch.tensor([1, 2, 3]).mean()
    """
    module_path = "test_module.py"
    result = extract_safe_computation(valid_computation, module_path)
    assert callable(result)

def test_extract_safe_computation_disallowed_attribute():
    invalid_computation = """
def computation(state, args):
    return args.__class__.__bases__[0].__subclasses__()
    """
    module_path = "test_module.py"
    with pytest.raises(ExtractComputationFailure):
        extract_safe_computation(invalid_computation, module_path)
