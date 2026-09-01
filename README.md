# 🚀 Farm to Home Backend

> Production backend powering **Farm to Home**, including Shopify integrations, Recharge subscriptions, Terramay Seeds loyalty program, email services, and PostgreSQL database.

---

# 📚 Table of Contents

- Project Overview
- Architecture
- Tech Stack
- Features
- Folder Structure
- Local Development
- Docker
- Environment Variables
- Database
- Shopify Integration
- Recharge Integration
- Terramay Seeds
- Deployment (Northflank)
- API Documentation
- Git Workflow
- Troubleshooting
- Security
- Roadmap
- Contributors

---

# 📖 Project Overview

This backend powers the Farm to Home platform.

Main responsibilities:

- Shopify Proxy APIs
- Recharge Subscription APIs
- Terramay Seeds Loyalty Program
- Email Notifications
- PostgreSQL Data Storage
- Customer Reward System
- Subscription Extras

---

# 🏗 System Architecture

```text
                    Shopify Store
                           │
                           │
                    App Proxy Requests
                           │
                           ▼
                FastAPI Backend (Northflank)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
 Recharge API         Neon PostgreSQL      SMTP Server
        │                  │                  │
 Subscription       Customers / Seeds     Notifications
 Management          Transactions
```

---

# ⚙️ Tech Stack

| Technology | Purpose |
|------------|----------|
| Python 3.12 | Backend |
| FastAPI | REST API |
| SQLAlchemy | ORM |
| PostgreSQL (Neon) | Database |
| Docker | Containerization |
| Northflank | Hosting |
| Shopify | Store Integration |
| Recharge | Subscription Management |
| SMTP | Emails |

---

# ✨ Features

## Shopify

- App Proxy
- Customer APIs
- Product APIs
- Order Processing

---

## Recharge

- Add Extras
- Remove Extras
- Fetch Subscription Extras

---

## Terramay Seeds

- Earn Seeds
- Redeem Rewards
- Balance
- Transaction History

---

## Email

- Contact Form
- Order Notifications
- Admin Notifications

---

# 📁 Project Structure

```
farm-to-home/
│
├── database/
│
├── models/
│
├── repositories/
│
├── routes/
│
├── schemas/
│
├── services/
│
├── scripts/
│
├── utils/
│
├── static/
│
├── templates/
│
├── Dockerfile
├── requirements.txt
├── main.py
└── README.md
```

---

# 💻 Local Development

Clone

```bash
git clone git@github.com:digital2526/farm-to-home.git

cd farm-to-home
```

Create Virtual Environment

```bash
python3 -m venv venv

source venv/bin/activate
```

Install packages

```bash
pip install -r requirements.txt
```

---

# ▶️ Run Project

```bash
uvicorn main:app --reload
```

Application

```
http://localhost:8000
```

Swagger

```
http://localhost:8000/docs
```

---

# 🐳 Docker

Build

```bash
docker build -t farm-to-home .
```

Run

```bash
docker run -p 8000:8000 farm-to-home
```

---

# 🔐 Environment Variables

Create a `.env` file.

Example

```env
RECHARGE_API_TOKEN=
SHOPIFY_STORE=
DATABASE_URL=
ALLOWED_ORIGINS=
SMTP_HOST=
SMTP_PORT=
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
ADMIN_EMAIL=
```

⚠ Never commit `.env`.

---

# 🗄 Database

Provider

```
Neon PostgreSQL
```

Connection

```
DATABASE_URL
```

Database includes:

- Customers
- Rewards
- Seed Transactions
- Redemption History

---

# 🌱 Terramay Seeds Flow

```
Customer Places Order
          │
          ▼
 Shopify Webhook
          │
          ▼
 FastAPI Receives Order
          │
          ▼
 Calculate Earned Seeds
          │
          ▼
 Store Transaction
          │
          ▼
 Update Customer Balance
```

---

# 🛒 Shopify Integration

Backend integrates with:

- Shopify App Proxy
- Customer Accounts
- Orders
- Products

---

# 🔄 Recharge Integration

Supports

- Add Extras
- Remove Extras
- List Extras

Recharge uses Shopify Checkout.

---

# 🚀 Deployment

Hosted on

```
Northflank
```

Repository

```
digital2526/farm-to-home
```

Deployment Trigger

```
Every push to main
```

---

# 📡 API Documentation

Swagger

```
/docs
```

OpenAPI

```
/openapi.json
```

---

# 🌿 Git Workflow

Create feature branch

```bash
git checkout -b feature/my-feature
```

Commit

```bash
git add .

git commit -m "Add feature"
```

Push

```bash
git push origin feature/my-feature
```

Open Pull Request.

---

# 🐞 Troubleshooting

## Database Connection

Check

```
DATABASE_URL
```

---

## Recharge Errors

Verify

- API Token
- Subscription IDs

---

## Shopify Proxy

Verify

- App Proxy
- HMAC
- Store Domain

---

## Docker

Rebuild

```bash
docker compose build --no-cache
```

---

# 🔒 Security

- Never commit `.env`
- Rotate API keys if exposed
- Store secrets in Northflank
- Use HTTPS endpoints only

---

# 🛣 Roadmap

- [ ] Customer Dashboard
- [ ] Referral Rewards
- [ ] Automated Seed Expiration
- [ ] Analytics Dashboard
- [ ] Admin Portal

---

# 🤝 Contributors

Terramay Development Team

Repository

```
https://github.com/digital2526/farm-to-home
```

---

# 📄 License

Private Repository

© Terramay
