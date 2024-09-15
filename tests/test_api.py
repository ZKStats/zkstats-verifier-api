import json
import os
import base64
import subprocess
import time

import requests
import pytest

from zkstats.core import verifier_verify

current_dir = os.path.dirname(os.path.abspath(__file__))

def request_computation_to_vk(
    url: str,
    data_shape: dict[str, int],
    computation: str,
    settings_path: str,
    precal_witness_path: str,
    path_to_save_vk: str,
):
    with open(settings_path, "r") as settings_file:
        settings = settings_file.read()

    with open(precal_witness_path, "r") as precal_witness_file:
        precal_witness = precal_witness_file.read()

    # Sample data for the request
    data = {
        "data_shape": json.dumps(data_shape),
        "computation": computation,
        "settings": settings,
        "precal_witness": precal_witness,
    }

    # Send POST request
    response = requests.post(url, json=data)

    # Check if the request was successful
    if response.status_code == 200:
        print("Request successful!")
        response_data = response.json()

        # Extract and decode the verification key
        vk_base64 = response_data["verification_key"]
        vk_bytes = base64.b64decode(vk_base64)

        # Save the verification key to a file
        with open(path_to_save_vk, "wb") as vk_file:
            vk_file.write(vk_bytes)
        print(f"Verification key saved to: {path_to_save_vk}")

        # Extract the selected columns
        selected_columns: list[str] = response_data["selected_columns"]
        print("Selected columns:", selected_columns)

        return selected_columns
    else:
        raise Exception(f"Request failed with status code: {response.status_code=}, {response.text=}")

def request_verify_proof(
    url: str,
    proof_path: str,
    settings_path: str,
    vk_file_path: str,
    selected_columns: list[str],
    data_commitment_path: str
):
    with open(settings_path, "r") as settings_file:
        settings_json = settings_file.read()

    with open(proof_path, "r") as proof_file:
        proof_json = proof_file.read()

    with open(data_commitment_path, "r") as data_commitment_file:
        data_commitment_json = data_commitment_file.read()

    with open(vk_file_path, "rb") as vk_file:
        vk_bytes = vk_file.read()

    # Sample data for the request
    data = {
        "proof_json": proof_json,
        "settings_json": settings_json,
        "vk_b64": base64.b64encode(vk_bytes).decode('utf-8'),
        "selected_columns": selected_columns,
        "data_commitment_json": data_commitment_json
    }

    # Send POST request
    response = requests.post(url, json=data)

    # Check if the request was successful
    if response.status_code == 200:
        print("Request successful!")
        response_data = response.json()
        res = json.loads(response_data)["result"]
        return res
    else:
        raise Exception(f"Request failed with status code: {response.status_code=}, {response.text=}")


@pytest.fixture(scope="module")
def server():
    # Start the server
    server = subprocess.Popen(["uvicorn", "main:app", "--reload"])
    time.sleep(2)  # Give the server some time to start

    yield server

    # Shut down the server
    server.terminate()
    server.wait()


def test_integration(server):
    url = "http://localhost:8000"
    endpoint_computation_to_vk = f"{url}/computation_to_vk"
    endpoint_verify_proof = f"{url}/verify_proof"

    # Test: computation_to_vk
    data_shape = {"x": 7, "y": 7}
    computation = """def computation(state: State, args: Args):
        x = args["x"]
        y = args["y"]
        return state.mean(x), state.mean(y)
    """
    settings_path = os.path.join(current_dir, "assets", "settings.json")
    precal_witness_path = os.path.join(current_dir, "assets", "precal_witness.json")
    vk_file_path = os.path.join(current_dir, "assets", "model.vk")

    selected_columns = request_computation_to_vk(
        endpoint_computation_to_vk,
        data_shape,
        computation,
        settings_path,
        precal_witness_path,
        vk_file_path
    )

    # Assert that the verification key file was created
    assert os.path.exists(vk_file_path)
    # Assert that selected_columns is not empty
    assert selected_columns

    # Test: verify_proof

    proof_path = os.path.join(current_dir, "assets", "model.pf")
    data_commitment_path = os.path.join(current_dir, "assets", "data_commitment.json")
    res = request_verify_proof(
        endpoint_verify_proof,
        proof_path,
        settings_path,
        vk_file_path,
        selected_columns,
        data_commitment_path
    )
    assert res == [51.5390625, 4.0859375]
