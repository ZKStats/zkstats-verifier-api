import ast
import tempfile
import os
import json
import base64
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lib import calculate_vk, verify_proof as lib_verify_proof, ExtractComputationFailure


app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=False,  # Default is False
    allow_methods=["GET", "POST"],  # Specify the HTTP methods you want to allow
    allow_headers=["*"],  # Allows all headers
)

# ### POST `/computation_to_vk`

class ComputationToVKRequest(BaseModel):
    # Example: '{"x": 7, "y": 7}'
    data_shape: str
    # Example: 'def computation(state, args): ...'
    computation: str
    # Settings in JSON format
    settings: str
    # Precomputed witness in JSON format
    precal_witness: str


# tmp_dir: str,
# proof_json: str,
# settings_json: str,
# vk_path: str,
# selected_columns: list[str],
# data_commitment_json: str,
class VerifyProofRequest(BaseModel):
    # Example: 'def computation(state, args): ...'
    proof_json: str
    # Settings in JSON format
    settings_json: str
    vk_b64: str
    selected_columns: list[str]
    data_commitment_json: str


@app.post("/computation_to_vk")
async def computation_to_vk(request: ComputationToVKRequest):
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            selected_columns, vk_path = calculate_vk(
                tmp_dir,
                request.data_shape,
                request.computation,
                request.settings,
                request.precal_witness
            )
            # Read the verification key file
            with open(vk_path, 'rb') as vk_file:
                vk_content = vk_file.read()

        # Return the file content and selected columns
        return JSONResponse(content={
            "verification_key": base64.b64encode(vk_content).decode('utf-8'),
            "selected_columns": selected_columns
        })
    except ExtractComputationFailure as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        # Re-raise HTTPException to preserve status code and detail
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/verify_proof")
async def verify_proof(request: VerifyProofRequest):
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            res = lib_verify_proof(
                tmp_dir,
                request.proof_json,
                request.settings_json,
                request.vk_b64,
                request.selected_columns,
                request.data_commitment_json
            )
            res_json = json.dumps({"result": res})
            return JSONResponse(content=res_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
