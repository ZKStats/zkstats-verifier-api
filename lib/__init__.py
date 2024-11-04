import json
import ast
import importlib.util
import os
import sys
import torch
import base64

from zkstats.core import create_dummy, verifier_define_calculation, setup, verifier_verify
from zkstats.computation import computation_to_model, State, Args, TComputation



class ExtractComputationFailure(Exception):
    pass



def extract_safe_computation(computation_str: str, module_path: str) -> TComputation:

    # Define allowed AST node types
    ALLOWED_NODES = (
        ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Load, ast.Store,
        ast.Name, ast.Subscript, ast.Index, ast.Slice, ast.ExtSlice, ast.Call, ast.Expr, ast.Assign,
        ast.BinOp, ast.UnaryOp, ast.Return, ast.Num, ast.Constant,
        ast.Attribute, ast.Dict, ast.Tuple, ast.List, ast.Compare,
        ast.If, ast.For, ast.While, ast.With, ast.Pass, ast.Str,
        ast.BoolOp, ast.IfExp, ast.Lambda,
    )

    # Define allowed function names and methods
    ALLOWED_FUNCTIONS = {
        'state': None,  # Allow all methods on state
        'args': None,   # Allow access to args
        'torch': None,  # Allow any torch functions
    }

    class SafeNodeVisitor(ast.NodeVisitor):
        def visit(self, node):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                raise ValueError("Import statements are not allowed.")
            if not isinstance(node, ALLOWED_NODES):
                raise ValueError(f"Disallowed node type: {type(node).__name__}")
            self.generic_visit(node)

        def visit_Subscript(self, node):
            # Allow subscripts only on allowed objects
            value_name = self.get_full_name(node.value)
            if value_name.split('.')[0] not in ALLOWED_FUNCTIONS:
                raise ValueError(f"Subscript access is not allowed on '{value_name}'")
            self.generic_visit(node)

        def visit_Call(self, node):
            # Check function calls
            if isinstance(node.func, ast.Name) and node.func.id in ['eval', 'exec']:
                raise ValueError(f"Use of {node.func.id}() is not allowed.")
            if isinstance(node.func, ast.Attribute):
                # Method calls like obj.method()
                obj = self.get_full_name(node.func.value)
                func = node.func.attr
                if obj.split('.')[0] in ALLOWED_FUNCTIONS:
                    pass
                else:
                    raise ValueError(f"Disallowed function call: '{func}' on '{obj}'")
            elif isinstance(node.func, ast.Name):
                # Function calls like func()
                func_name = node.func.id
                if func_name in ALLOWED_FUNCTIONS and ALLOWED_FUNCTIONS[func_name] is None:
                    pass
                else:
                    raise ValueError(f"Disallowed function call: '{func_name}'")
            else:
                raise ValueError(f"Disallowed function call: {ast.dump(node)}")
            self.generic_visit(node)

        def visit_Attribute(self, node):
            # Allow attributes of allowed objects
            obj = self.get_full_name(node.value)
            attr = node.attr
            if obj.split('.')[0] in ALLOWED_FUNCTIONS:
                pass
            else:
                raise ValueError(f"Disallowed attribute access: '{attr}' on '{obj}'")
            self.generic_visit(node)

        def get_full_name(self, node):
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                return f"{self.get_full_name(node.value)}.{node.attr}"
            elif isinstance(node, ast.Subscript):
                return f"{self.get_full_name(node.value)}[{self.get_full_name(node.slice)}]"
            elif isinstance(node, ast.Index):
                return self.get_full_name(node.value)
            elif isinstance(node, ast.Constant):
                return str(node.value)
            elif isinstance(node, ast.Str):  # For Python versions where strings are ast.Str
                return node.s
            else:
                return ""

    try:
        # Parse the computation_str into an AST
        parsed_ast = ast.parse(computation_str)

        # Visit the AST nodes to ensure they are safe
        visitor = SafeNodeVisitor()
        visitor.visit(parsed_ast)

        # Write the computation_str to the module file
        with open(module_path, 'w') as f:
            f.write(computation_str)

        # Import the module from the module file
        module_name = os.path.splitext(os.path.basename(module_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        computation_module = importlib.util.module_from_spec(spec)
        # Ensure that the module has the correct __file__ attribute
        computation_module.__file__ = module_path
        sys.modules[module_name] = computation_module  # Add to sys.modules

        # Use a custom loader to limit built-ins
        class SafeLoader(spec.loader.__class__):
            def exec_module(self, module):
                # Compile the code with the correct filename
                with open(module_path, 'r') as f:
                    code = f.read()
                code_object = compile(code, filename=module_path, mode='exec')

                # Define a restricted set of built-in functions
                safe_builtins = {
                    'abs': abs,
                    'all': all,
                    'any': any,
                    'bool': bool,
                    'callable': callable,
                    'chr': chr,
                    'complex': complex,
                    'dict': dict,
                    'enumerate': enumerate,
                    'float': float,
                    'int': int,
                    'len': len,
                    'list': list,
                    'max': max,
                    'min': min,
                    'pow': pow,
                    'range': range,
                    'set': set,
                    'str': str,
                    'sum': sum,
                    'tuple': tuple,
                    'zip': zip,
                    'sorted': sorted,
                    'reversed': reversed,
                    'slice': slice,
                    # '__import__': __import__,  # Necessary for module imports
                }

                # Define a restricted global namespace
                restricted_globals = {
                    '__builtins__': safe_builtins,
                    '__name__': module.__name__,
                    '__file__': module.__file__,
                    'torch': torch,
                    'State': State,
                    'Args': Args,
                }

                # Execute the code in the restricted namespace
                exec(code_object, restricted_globals, module.__dict__)

        # Replace the loader with our SafeLoader
        spec.loader = SafeLoader(spec.loader.name, spec.loader.path)

        # Execute the module
        spec.loader.exec_module(computation_module)

        # Get the computation function from the module
        computation_func = computation_module.computation

        # Ensure the function has the correct __module__ attribute
        computation_func.__module__ = module_name

        return computation_func

    except Exception as e:
        print(f"Error while extracting computation: {e}")
        print(f"Computation: {computation_str!r}")
        raise ExtractComputationFailure from e


def calculate_vk(
    tmp_dir: str,
    data_shape_json: str,
    computation_str: str,
    settings_json: str,
    precal_witness_json: str,
):
    model_path = os.path.join(tmp_dir, 'model.onnx')
    compiled_model_path = os.path.join(tmp_dir, 'model.compiled')
    vk_path = os.path.join(tmp_dir, 'model.vk')
    pk_path = os.path.join(tmp_dir, 'model.pk')
    dummy_data_path = os.path.join(tmp_dir, 'dummy_data.json')
    sel_dummy_data_path = os.path.join(tmp_dir, 'sel_dummy_data.json')
    precal_witness_path = os.path.join(tmp_dir, 'precal_witness.json')
    settings_path = os.path.join(tmp_dir, 'settings.json')

    data_shape = json.loads(data_shape_json)
    with open(precal_witness_path, 'w') as precal_witness_file:
        precal_witness_file.write(precal_witness_json)
    with open(settings_path, 'w') as settings_file:
        settings_file.write(settings_json)
    module_path = os.path.join(tmp_dir, 'computation_module.py')
    c = extract_safe_computation(computation_str, module_path)
    # Generate the verifier model with the `precal_witness_path` provided by the prover
    selected_columns, _, verifier_model = computation_to_model(c, precal_witness_path, data_shape, isProver=False)
    # Create dummy data with the same shape as the original data
    create_dummy(data_shape, dummy_data_path)
    # Generate the verifier model given the dummy data and the selected columns
    verifier_define_calculation(dummy_data_path, selected_columns, sel_dummy_data_path, verifier_model, model_path)
    # Generate the verification key
    setup(model_path, compiled_model_path, settings_path, vk_path, pk_path)
    return selected_columns, vk_path


def verify_proof(
    tmp_dir: str,
    proof_json: str,
    settings_json: str,
    vk_b64: str,
    selected_columns: list[str],
    data_commitment_json: str,
):
    proof_path = os.path.join(tmp_dir, 'proof.json')
    data_commitment_path = os.path.join(tmp_dir, 'data_commitment.json')
    settings_path = os.path.join(tmp_dir, 'settings.json')
    vk_path = os.path.join(tmp_dir, 'model.vk')
    with open(proof_path, 'w') as proof_file:
        proof_file.write(proof_json)
    with open(settings_path, 'w') as settings_file:
        settings_file.write(settings_json)
    with open(data_commitment_path, 'w') as data_commitment_file:
        data_commitment_file.write(data_commitment_json)
    with open(vk_path, 'wb') as vk_file:
        vk_file.write(base64.b64decode(vk_b64))
    res = verifier_verify(proof_path, settings_path, vk_path, selected_columns, data_commitment_path)
    return res
