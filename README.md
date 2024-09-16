# ZKStats Verifier API

A simple API for ZKStats verification key generation and proof verification. This API is a simple wrapper around the [ZKStats](https://github.com/privacy-scaling-explorations/zk-stats) library to make it easier to use in browser environments.

Caveat: malicious clients can input arbitrary computation and compromise the server. Make sure to run the server in a separate environment, and do not expose the endpoints to the public internet.

## Prerequisites

- Python 3.12 or higher
- Poetry (Python package manager)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/ZKStats/zkstats-verifier-api.git
   cd zkstats-verifier-api
   ```

2. Install Python dependencies:
   ```
   poetry install
   ```

3. Install TypeScript client dependencies:
   ```
   cd ts-client
   npm install
   ```


## Running the Server

To start the FastAPI server:
```
poetry run uvicorn main:app --reload
```

The server will be available at `http://localhost:8000`.

## API Endpoints

### POST `/computation_to_vk`

Generate verification key from computation.

#### Request Body

- `data_shape` (string): JSON string representing the shape of the input data.
- `computation` (string): The computation function as a string.
- `settings` (string): JSON string containing the settings.
- `precal_witness` (string): JSON string containing the precomputed witness.

#### Response

- `verification_key` (string): Base64 encoded verification key.
- `selected_columns` (array): List of selected column names.

### POST `/verify_proof`

Verify a proof.

#### Request Body

- `proof_json` (string): JSON string containing the proof.
- `settings_json` (string): JSON string containing the settings.
- `vk_b64` (string): Base64 encoded verification key.
- `selected_columns` (array): List of selected column names.
- `data_commitment_json` (string): JSON string containing the data commitment.

#### Response

- `result` (array): The result of the verification.

For detailed API documentation, visit `http://localhost:8000/docs` when the server is running.

## Running the TypeScript Client
An example TypeScript client is provided in the [ts-client](./ts-client/src/client.ts) directory.
1. Ensure you have Node.js and npm installed.
2. Ensure the server is running.
3. Run the following command to start the client.

```
cd ts-client
npm start
```
This command will initiate the client, which will then send requests to the server. While efforts have been made to ensure compatibility with both Node.js and browser environments, some further modifications may be necessary for making it work in browser.

## Running Tests

To run the Python tests:
```
poetry run pytest
```
