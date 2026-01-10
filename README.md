# TensorLake Expense Explorer 🍎🚀

Expense Explorer is a premium, cloud-native financial intelligence suite that transforms messy PDF statements into structured, actionable insights. Powered by **TensorLake Cloud** and **Gemini-3-Flash**.

## ✨ Key Features
- **Apple-Style Dashboard**: A minimalist, high-daylight UI for seamless interaction.
- **Deep Financial Extraction**: Beyond dates and amounts—identifies merchants, subscriptions, payment methods, and enriched tags.
- **Gemini-3-Flash**: High-performance extraction and conversational intelligence.
- **Deduplication**: Intelligent iterative ingestion skips already-processed transactions.
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

### 3. Launch the Dashboard
Use the built-in launch script to start the proxy server and frontend:
```bash
chmod +x launch_dashboard.sh
./launch_dashboard.sh
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

## 📁 Repository Structure
- `index.html` & `style.css`: The Apple-style minimalist dashboard.
- `app.js`: Frontend logic for file handling and API polling.
- `server.py`: Secure Python proxy for API injection and static serving.
- `workflow.py`: TensorLake application definitions (`ingestion` & `query`).
- `schema.py`: SQLAlchemy and Pydantic models for enriched transactions.
- `extractor_logic.py`: Agentic extraction logic powered by Gemini-3-Flash.

Built with ❤️ using TensorLake.
