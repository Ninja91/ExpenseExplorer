# TensorLake Expense Explorer

A cloud-native expense management suite powered by TensorLake and Neon Postgres. 

## 🏗️ Architecture
- **Inference**: Gemma-3 via TensorLake Applications.
- **Parsing**: TensorLake Document AI.
- **Persistence**: Serverless Neon Postgres (managed via SQLAlchemy).
- **Format**: Multi-application architecture (`ingest_app` + `query_app`).

## 🛠️ Setup

1.  **Environment**: Create a virtual environment and install dependencies.
    ```bash
    python3.12 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Configuration**: Create a `.env` file with the following:
    ```env
    TENSORLAKE_API_KEY=your_key
    GEMINI_API_KEY=your_key
    DATABASE_URL=postgresql://user:pass@host/dbname
    ```

3.  **Secrets**: Push sensitive keys to TensorLake Cloud.
    ```bash
    tensorlake secrets set DATABASE_URL=...
    tensorlake secrets set GEMINI_API_KEY=...
    tensorlake secrets set TENSORLAKE_API_KEY=...
    ```

4.  **Deployment**: Deploy both apps to the cloud.
    ```bash
    tensorlake deploy workflow.py
    ```

## 🚀 Usage

### 1. Ingest Statements
Process PDF credit card statements and save transactions to the cloud database.
```bash
python verify_flow.py
```
*Note: Ensure your PDF statements are in `Downloads/Credit_Card_Statements`.*

### 2. Conversational Query
Ask natural language questions about your spending.
```bash
python query_agent.py "What were my top travel expenses in December?"
```

## 🏗️ Technical Details
- **Base64 Encoding**: Used for reliable binary PDF transfer via JSON APIs.
- **Schema Management**: Managed via `schema.py` and SQLAlchemy models.
- **Conversational Gemma**: Queries are handled by a multi-agentic Gemma-3 runner.
