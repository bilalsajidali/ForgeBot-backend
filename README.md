# BotForge 🤖

AI Chatbot SaaS — Build and embed custom AI bots for any business.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Vite + React |
| Backend | FastAPI |
| Database | MongoDB (Motor async) |
| AI | Groq API (Llama 3.3 70b) |
| Auth | JWT |
| Payments | Dodo Payments |
| Deploy | AWS |

---

## Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Setup environment
copy .env.example .env
# Fill in your values in .env

# Run dev server
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:5173

---

## Environment Variables

```
SECRET_KEY         → Any random string (use: openssl rand -hex 32)
MONGO_URI          → MongoDB Atlas connection string
GROQ_API_KEY       → Get free at: console.groq.com
DODO_API_KEY       → Get at: dodopayments.com
FRONTEND_URL       → http://localhost:5173 (dev) or your domain (prod)
```

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | /auth/signup | Register new user |
| POST | /auth/login | Login, get JWT |
| GET | /auth/me | Get current user |

### Agents (Protected — Bearer token required)
| Method | Endpoint | Description |
|---|---|---|
| POST | /agents/create | Create new bot |
| GET | /agents/list | List all bots |
| GET | /agents/:id | Get single bot |
| PUT | /agents/:id | Update bot |
| DELETE | /agents/:id | Delete bot |
| POST | /agents/:id/regenerate-key | New API key |

### Chat
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | /chat/test/:id | Bearer JWT | Test bot internally |
| POST | /chat/widget | X-Api-Key header | External embed endpoint |

---

## Widget Embed (for client websites)

```html
<!-- Add before closing </body> tag -->
<script>
  window.BotForgeConfig = {
    apiKey: "bf_live_your_key_here"
  };
</script>
<script src="https://cdn.botforge.app/widget.js"></script>
```

---

## Plans

| Plan | Bots | Daily Messages | Price |
|---|---|---|---|
| Free | 1 | 50 | $0 |
| Starter | 3 | 1,000 | $12/mo |
| Pro | Unlimited | 10,000 | $29/mo |
| Enterprise | Unlimited | Unlimited | $99/mo |
