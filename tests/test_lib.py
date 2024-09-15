import os
import sys
from pathlib import Path
import pytest

from zkstats.computation import computation_to_model
from zkstats.core import create_dummy, verifier_define_calculation

current_dir = Path(__file__).parent
sys.path.append(str(current_dir.parent))

from lib import extract_safe_computation, ExtractComputationFailure


def execute_computation(tmp_path: Path, computation_str: str):
    data_shape = {"x": 7, "y": 7}
    module_path = tmp_path / "test_module.py"
    precal_witness_path = tmp_path / "precal_witness.json"
    dummy_data_path = tmp_path / "dummy_data.json"
    sel_dummy_data_path = tmp_path / "sel_dummy_data.json"
    model_path = tmp_path / "model.onnx"

    extracted_computation = extract_safe_computation(computation_str, str(module_path))
    selected_columns, _, verifier_model = computation_to_model(
        extracted_computation,
        str(precal_witness_path),
        data_shape,
        isProver=True
    )
    create_dummy(data_shape, dummy_data_path)
    verifier_define_calculation(dummy_data_path, selected_columns, sel_dummy_data_path, verifier_model, model_path)
    return extracted_computation


def test_extract_safe_computation_valid(tmp_path):
    valid_computation = """
def computation(state: State, args: Args):
    x = args["x"]
    y = args["y"]
    return state.mean(x), state.mean(y)
    """
    extracted_computation = execute_computation(tmp_path, valid_computation)
    assert callable(extracted_computation)

def test_extract_safe_computation_valid_no_type_hint(tmp_path: Path):
    valid_computation = """
def computation(state, args):
    x = args["x"]
    y = args["y"]
    return state.mean(x), state.mean(y)
    """
    extracted_computation = execute_computation(tmp_path, valid_computation)
    assert callable(extracted_computation)

def test_extract_safe_computation_import_statement(tmp_path: Path):
    invalid_computation = """
import os

def computation(state, args):
    return os.getcwd()
    """
    with pytest.raises(ExtractComputationFailure):
        execute_computation(tmp_path, invalid_computation)

def test_extract_safe_computation_exec(tmp_path: Path):
    invalid_computation = """
def computation(state, args):
    exec("print('This should not be allowed')")
    return 0
    """
    # NameError: name 'exec' is not defined
    with pytest.raises(NameError, match="name 'exec' is not defined"):
        execute_computation(tmp_path, invalid_computation)

def test_extract_safe_computation_eval(tmp_path: Path):
    invalid_computation = """
def computation(state, args):
    return eval("__import__('os').system('ls')")
    """
    with pytest.raises(NameError, match="name 'eval' is not defined"):
        execute_computation(tmp_path, invalid_computation)

def test_extract_safe_computation_globals(tmp_path: Path):
    invalid_computation = """
def computation(state, args):
    return globals()['__builtins__']['__import__']('os').system('ls')
    """
    with pytest.raises(NameError, match="name 'globals' is not defined"):
        execute_computation(tmp_path, invalid_computation)
