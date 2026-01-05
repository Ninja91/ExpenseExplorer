# TensorLake Expense Explorer

## Overview
A serverless Expense Explorer powered by TensorLake. 
Ingest PDF credit card statements, extract transactions with Gemma 3, and query your spending naturally.

## Deployment

1. **Deploy to TensorLake Cloud**:
   ```bash
   python workflow.py deploy
   ```
   *If successful, this registers your `expense_ingestion` graph.*

## Usage

1. **Ingest a Statement**:
   Upload a PDF to be processed by the deployed ecosystem.
   ```bash
   python workflow.py ingest /path/to/statement.pdf
   ```

2. **Query Expenses**:
   Ask questions about your extracted transactions.
   ```bash
   python query_agent.py "How much did I spend on groceries?"
   ```

## Note on Credentials
Ensure your proper `TENSORLAKE_API_KEY` is set in local `.env` or your cloud environment.

## Troubleshooting
If you encounter `404` errors during deployment:
1.  **Check Namespace**: The default code uses the `default` namespace. Ensure this exists in your TensorLake Console or set a different `namespace` in `TensorlakeClient`.
2.  **API Key Permissions**: Ensure your API key has `Admin` or `Write` permissions to register graphs.
3.  **Deployment Bundle**: Use `python workflow.py deploy` from the project root. The script handles bundling automatically.
