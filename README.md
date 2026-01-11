# TensorLake Expense Explorer 🍎🚀

Expense Explorer is a premium, cloud-native financial intelligence suite that transforms messy PDF statements into structured, actionable insights. Powered by **TensorLake Cloud** and **Gemini-3-Flash**.

## ✨ Key Features
- **Apple-Style Dashboard**: A minimalist, high-daylight UI for seamless interaction.
- **Deep Financial Extraction**: Beyond dates and amounts—identifies merchants, subscriptions, payment methods, and enriched tags.
- **Gemini-3-Flash**: High-performance extraction and conversational intelligence.
- **Deduplication**: Intelligent iterative ingestion skips already-processed transactions.
- **SQL Reliability**: Integrated `tenacity` retry logic for resilient database operations.
- **Cloud-Native Proxy**: A secure server-side proxy handles authentication and bypasses browser security constraints.

## 🏗️ Architecture
- **AI Models**: Gemini-3-Flash (via TensorLake Applications).
- **Backend API**: TensorLake V2 REST API + Application Framework.
- **Database**: Neon Postgres (Serverless) for robust financial records.
- **Web UI**: Vanilla HTML/JS with a refined Apple-inspired aesthetic.

## 🛠️ Quick Start

### 1. Requirements
Ensure you have the following in your `.env` file:
```env
TENSORLAKE_API_KEY=YOUR_KEY
GEMINI_API_KEY=YOUR_KEY
DATABASE_URL=YOUR_NEON_POSTGRES_URL
```

### 2. Configuration & Deployment
Push secrets to TensorLake and deploy your cloud applications:
```bash
tensorlake secrets set DATABASE_URL=...
tensorlake secrets set GEMINI_API_KEY=...
tensorlake deploy workflow.py
```

### 3. Ingest Statements
#### Dashboard (Individual)
Launch the dashboard and drag/drop your files.

#### CLI (Batch)
Use the batch tool for bulk processing:
```bash
python verify_flow.py
```
*Note: Ensure your PDF statements are in `~/Downloads/Credit_Card_Statements`.*

### 4. Launch the Dashboard
Use the built-in launch script:
```bash
chmod +x launch_dashboard.sh
./launch_dashboard.sh
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

Built with ❤️ using TensorLake.
