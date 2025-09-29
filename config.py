# config.py - Bot Configuration with Railway & MySQL

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# MySQL Database Configuration (Railway provides these as environment variables)
DATABASE_CONFIG = {
    'host': os.getenv('MYSQLHOST', 'localhost'),
    'port': int(os.getenv('MYSQLPORT', 3306)),
    'user': os.getenv('MYSQLUSER', 'root'),
    'password': os.getenv('MYSQLPASSWORD', ''),
    'database': os.getenv('MYSQLDATABASE', 'railway'),
    'charset': 'utf8mb4',
    'autocommit': True
}

# Role IDs
ADMIN_ROLE_IDS = [
    659861001272819816, # Staff
]

ADMIN_USER_IDS = []

# Roles that are EXCLUDED from registration (staff, alumni, bots, special cases, etc.)
# Everyone with these roles is exempt from registration
EXCLUDED_ROLE_IDS = [
    919642895152205824,  # Alumni
]

# EXISTING TEAM ROLE IDS - Members who already have these roles from previous year
# These members MUST register (unless they have excluded roles above)
EXISTING_TEAM_ROLE_IDS = [
    779765997565509652,  # IT
    779765752131223572,  # Design
    779765838844395590,  # Marketing 
    1034569599280218232,  # B2B
    1164976491768057856,  # OPS
    938021296330141716,  # HR
]

# Role for existing team members who don't register
NOT_RENEWED_ROLE_ID = 1421977919777144946

# Role for non-team members who should register
UNVERIFIED_ROLE_ID = 1421978051075379210

# File paths (for temporary CSV exports)
TEMP_CSV_FILE = "/tmp/registrations.csv"
LOG_FILE = "bot.log"

TEAM_OPTIONS = [
    {"label": "IT Team", "value": "IT", "emoji": "💻"},
    {"label": "Design Team", "value": "Design", "emoji": "🎨"},
    {"label": "Marketing Team", "value": "Marketing", "emoji": "📢"},
    {"label": "B2B Team", "value": "B2B", "emoji": "🤝"},
    {"label": "OPS Team", "value": "OPS", "emoji": "⚙️"},
    {"label": "HR Team", "value": "HR", "emoji": "👥"},
]

# Bot settings
REGISTRATION_TIMEOUT = 300  # 5 minutes timeout for registration views