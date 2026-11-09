import os
import sys
import datetime
import subprocess
from dotenv import load_dotenv

# Add parent directory to path to load .env safely
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load environmental variables
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env"))
load_dotenv(dotenv_path)

DATABASE_URL = os.getenv("DATABASE_URL")

def run_backup():
    print("==================================================")
    print("         KHARAZMI SYSTEM - DATABASE BACKUP")
    print("==================================================")
    
    if not DATABASE_URL:
        print("❌ Error: DATABASE_URL environment variable is not set!")
        return
        
    # Check if we have postgresql connection string
    # E.g. postgresql://username:password@host/database
    if not DATABASE_URL.startswith("postgresql://"):
        print("❌ Error: DATABASE_URL must be a PostgreSQL connection string!")
        return
        
    # Ensure backups directory exists
    backup_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../backups"))
    os.makedirs(backup_dir, exist_ok=True)
    
    # Generate backup filename with timestamp
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y_%m_%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"gaj_db_backup_{timestamp}.sql")
    
    print(f"🔄 Starting database backup using pg_dump...")
    print(f"📂 Destination: {backup_file}")
    
    # Execute pg_dump command
    # E.g., pg_dump postgresql://username:password@host/database > backup.sql  # FIX H13: حذف secret واقعی از کامنت
    try:
        # On Windows, pg_dump may need a shell or explicit path, on Linux standard call works
        # Using stdout redirect safely
        with open(backup_file, "w") as out_f:
            process = subprocess.Popen(
                ["pg_dump", DATABASE_URL],
                stdout=out_f,
                stderr=subprocess.PIPE,
                text=True
            )
            _, stderr = process.communicate()
            
            if process.returncode == 0:
                print(f"✅ Success! Database backup created successfully.")
                print(f"   • File: {os.path.basename(backup_file)}")
                print(f"   • Size: {os.path.getsize(backup_file)} bytes")
            else:
                print(f"❌ Error during pg_dump: {stderr}")
                # Remove empty or corrupt file on error
                if os.path.exists(backup_file):
                    os.remove(backup_file)
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        if os.path.exists(backup_file):
            os.remove(backup_file)
            
    # Clean up backups older than 30 days
    cleanup_old_backups(backup_dir)

def cleanup_old_backups(backup_dir):
    print("\n🧹 Scanning for expired backup files (older than 30 days)...")
    try:
        now = datetime.datetime.now()
        retention_days = 30
        deleted_count = 0
        
        for file_name in os.listdir(backup_dir):
            if file_name.startswith("gaj_db_backup_") and file_name.endswith(".sql"):
                file_path = os.path.join(backup_dir, file_name)
                creation_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                elapsed = now - creation_time
                
                if elapsed.days > retention_days:
                    print(f"   • Removing expired backup file: {file_name} ({elapsed.days} days old)")
                    os.remove(file_path)
                    deleted_count += 1
                    
        if deleted_count > 0:
            print(f"✅ Cleanup complete: Removed {deleted_count} expired backup files.")
        else:
            print("✅ No expired backup files found.")
    except Exception as e:
        print(f"⚠️ Warning during backup cleanup: {e}")

if __name__ == "__main__":
    run_backup()
