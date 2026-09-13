import os

from dotenv import load_dotenv

load_dotenv()


PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "telecomnexus")
PGUSER = os.getenv("PGUSER", "fde_user")
PGPASSWORD = os.getenv("PGPASSWORD", "")


APP_TITLE = "TelecomNexus Customer Management"
APP_VERSION = "1.0.0"