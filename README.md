# SecBot – AI Security Assistant with Active Directory Authentication

SecBot is an internal AI-powered security chatbot designed for employees and IT staff. Users authenticate with real Active Directory credentials and can ask security-related questions. The AI (Claude) responds according to company security policies, and all conversations are stored in a database.

## Features

- Active Directory (LDAP) authentication
- Clean chat interface with conversation history
- AI responses powered by Claude (Anthropic)
- Conversations saved in PostgreSQL
- Admin dashboard
- Automatic deployment from GitHub
- Runs as a systemd service

## Architecture

- **Windows Server 2025**: Active Directory Domain Controller (`secproject.local`)
- **Ubuntu Server 24.04**: Hosts the FastAPI application, PostgreSQL database, and AI integration

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, CSS, JavaScript (Jinja2 Templates)
- **Authentication**: LDAP (ldap3)
- **AI**: Anthropic Claude API
- **Database**: PostgreSQL + SQLAlchemy
- **Deployment**: GitHub + Cron + Systemd

## Project Structure

secbot/
├── app/
│   ├── main.py          # Main application & routes
│   ├── auth.py          # Active Directory authentication
│   ├── database.py      # Database connection
│   ├── models.py        # Database models
│   └── templates/       # HTML pages
├── .env                 # Environment variables (not committed)
├── requirements.txt
└── deploy.sh            # Auto-deploy script

## Setup Instructions

### 1. Windows Server
- Install Windows Server 2025
- Promote to Domain Controller
- Domain: `secproject.local`
- Create users: `student1`, `student2`, `admin`

### 2. Ubuntu Server
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip postgresql git

3. Application Setupbash

cd /var/www/secbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

4. Environment VariablesCreate a .env file with:

ANTHROPIC_API_KEY=your_claude_key
LDAP_SERVER=Windows_Server_IP
DOMAIN=secproject.local
DB_HOST=127.0.0.1
DB_NAME=secbot
DB_USER=secbotuser
DB_PASSWORD=your_password
SECRET_KEY=your_secret_key

5. Run the Applicationbash

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Automatic DeploymentEvery time code is pushed to the main branch on GitHub, the Ubuntu server automatically pulls the changes (via cron job every 2 minutes).AuthorAnildo Centeio
Senior Project

---

### How to add it to GitHub:

On Ubuntu run:

```bash
cd /var/www/secbot
nano README.md

Paste the content above, save, then:bash

git add README.md
git commit -m "Add README"
git push



