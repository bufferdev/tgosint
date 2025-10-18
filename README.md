# tgosint

Telegram OSINT tool (public data only) powered by Telethon.

---

## Description

`tgosint` is an open-source tool designed to extract **publicly available** information from Telegram.  
It uses the official **Telethon** library, without any scraping, exploits, or unauthorized access.

The goal is to provide a framework for **ethical**, **documented**, and **reproducible** OSINT research, analysis, and digital investigations.

---

## Features

- Retrieve public information about:
  - **Users**: first name, last name, username, biography, profile photos, status, last seen time  
  - **Groups & Channels**: title, description, creation date, member count, profile photos  
  - **Public messages**: text content, links, hashtags, dates, reactions, media metadata  
- Supports multiple query types:
  - `-u` / `--username` – by username  
  - `-i` / `--id` – by Telegram user or channel ID  
  - `-p` / `--phone` – by phone number (temporary contact import)  
  - `-l` / `--url` – by public message URL  
- JSON export support for automation or integration  
- Optional download of profile pictures  

---

## Installation

```
git clone https://github.com/bufferdev/tgosint.git
cd tgosint


# Create a Python virtual environment
python -m venv .venv
source .venv/bin/activate  # (on Windows: .venv\Scripts\activate)

# Install dependencies
pip install -r requirements.txt
Configuration
Copy the environment example file and edit it:



cp .env.example .env
Then fill in your Telegram API credentials:

ini

TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
TG_PHONE=+33123456789
You can obtain your API ID and hash from the official Telegram portal:
https://my.telegram.org

Usage
Run the main script:



# Query by username
python src/tg_osint.py -u @username

# Query by user ID
python src/tg_osint.py -i 123456789

# Query by phone number
python src/tg_osint.py -p +33123456789

# Query a public message by URL
python src/tg_osint.py -l https://t.me/somechannel/12345
Optional flags
sql

--json              Output in JSON format
--photos            Download profile photos
--limit-photos 5    Limit the number of downloaded photos
--tz Europe/Paris   Display timestamps in a specific timezone
--no-color          Disable colored output
Examples:



python src/tg_osint.py -u @dupond --json > exports/dupond.json
python src/tg_osint.py -l https://t.me/somechannel/12345 --tz Europe/Paris
Local Testing (Quick Start)
If you want to test locally:



git clone https://github.com/<your-username>/tgosint.git
cd tgosint
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env  # edit TG_API_ID / TG_API_HASH
export $(grep -v '^#' .env | xargs)

python src/tg_osint.py -u @dupond
# or
python src/tg_osint.py -l https://t.me/somechannel/12345 --json
Legal and Ethical Notice
This tool is intended only for legitimate OSINT, research, and security purposes.
It does not bypass Telegram’s privacy model and only accesses public data via the official API.

By using this software, you agree to comply with:

Local and international data protection laws

Telegram’s Terms of Service

The author is not responsible for any misuse or illegal activity performed with this tool.

License
Released under the MIT License.
See the LICENSE file for details.




---

Would you like me to make a **shorter version** (for a GitHub summary section), or do you prefer this **
