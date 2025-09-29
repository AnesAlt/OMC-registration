# database.py - MySQL Database Utilities

import pymysql
from pymysql import OperationalError, InterfaceError
import time
import os
import csv
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import config

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.last_ping = 0
        self.connect()
        self.create_tables()
    
# In database.py, modify connect():
    def connect(self):
        """Connect to MySQL database"""
        try:
            print(f"🔍 Attempting connection with config: {config.DATABASE_CONFIG}")
            conn_kwargs = dict(config.DATABASE_CONFIG)
            conn_kwargs.setdefault('connect_timeout', 10)
            conn_kwargs.setdefault('read_timeout', 10)
            conn_kwargs.setdefault('write_timeout', 10)
            self.connection = pymysql.connect(**conn_kwargs)
            self.last_ping = time.time()
            print("✅ Connected to MySQL database")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def ensure_connection(self):
        """Ensure the MySQL connection is alive; reconnect if needed."""
        try:
            # Only ping periodically to avoid unnecessary calls
            if self.connection is None:
                self.connect()
            else:
                if time.time() - self.last_ping > 300:
                    self.connection.ping(reconnect=True)
                    self.last_ping = time.time()
        except (OperationalError, InterfaceError, AttributeError):
            # Try a full reconnect
            self.connect()
    
    def create_tables(self):
        """Create necessary tables"""
        try:
            with self.connection.cursor() as cursor:
                # Create registrations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS registrations (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        discord_id VARCHAR(20) UNIQUE NOT NULL,
                        last_name VARCHAR(100) NOT NULL,
                        first_name VARCHAR(100) NOT NULL,
                        photo VARCHAR(500) NOT NULL,
                        year_major VARCHAR(150) NOT NULL,
                        student_id VARCHAR(20) NOT NULL,
                        phone VARCHAR(10) NOT NULL,
                        email VARCHAR(100) NOT NULL,
                        team VARCHAR(20) NOT NULL,
                        timestamp DATETIME NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_discord_id (discord_id),
                        INDEX idx_team (team),
                        INDEX idx_timestamp (timestamp)
                    )
                """)
                
                # Create logs table for admin actions
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS admin_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        action VARCHAR(50) NOT NULL,
                        admin_discord_id VARCHAR(20) NOT NULL,
                        admin_name VARCHAR(100) NOT NULL,
                        details TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_action (action),
                        INDEX idx_timestamp (timestamp)
                    )
                """)
            self.connection.commit()
            print("✅ Database tables created/verified")
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            raise
    
    def save_registration(self, registration_data: dict) -> bool:
        """Save registration to database"""
        for attempt in range(2):
            try:
                self.ensure_connection()
                with self.connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO registrations 
                        (discord_id, last_name, first_name, photo, year_major, student_id, 
                         phone, email, team, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        registration_data['discord_id'],
                        registration_data['nom'],
                        registration_data['prenom'],
                        registration_data['photo'],
                        registration_data['annee_specialite'],
                        registration_data['matricule'],
                        registration_data['phone'],
                        registration_data['email'],
                        registration_data['team'],
                        datetime.fromisoformat(registration_data['timestamp'])
                    ))
                self.connection.commit()
                return True
            except (OperationalError, InterfaceError) as e:
                print(f"⚠️ Transient DB error on save_registration (attempt {attempt+1}): {e}")
                try:
                    self.connect()
                except Exception:
                    pass
                if attempt == 1:
                    try:
                        self.connection.rollback()
                    except Exception:
                        pass
                    return False
            except Exception as e:
                print(f"❌ Error saving registration: {e}")
                try:
                    self.connection.rollback()
                except Exception:
                    pass
                return False
    
    def is_user_registered(self, discord_id: str) -> bool:
        """Check if user is registered"""
        for attempt in range(2):
            try:
                self.ensure_connection()
                with self.connection.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM registrations WHERE discord_id = %s", (discord_id,))
                    return cursor.fetchone() is not None
            except (OperationalError, InterfaceError) as e:
                print(f"⚠️ Transient DB error on is_user_registered (attempt {attempt+1}): {e}")
                try:
                    self.connect()
                except Exception:
                    pass
                if attempt == 1:
                    return False
            except Exception as e:
                print(f"❌ Error checking registration: {e}")
                return False
    
    def get_user_registration(self, discord_id: str) -> Optional[dict]:
        """Get user registration data"""
        for attempt in range(2):
            try:
                self.ensure_connection()
                with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute("SELECT * FROM registrations WHERE discord_id = %s", (discord_id,))
                    return cursor.fetchone()
            except (OperationalError, InterfaceError) as e:
                print(f"⚠️ Transient DB error on get_user_registration (attempt {attempt+1}): {e}")
                try:
                    self.connect()
                except Exception:
                    pass
                if attempt == 1:
                    return None
            except Exception as e:
                print(f"❌ Error getting registration: {e}")
                return None
    
    def get_registered_discord_ids(self) -> set:
        """Get all registered Discord IDs"""
        for attempt in range(2):
            try:
                self.ensure_connection()
                with self.connection.cursor() as cursor:
                    cursor.execute("SELECT discord_id FROM registrations")
                    return {row[0] for row in cursor.fetchall()}
            except (OperationalError, InterfaceError) as e:
                print(f"⚠️ Transient DB error on get_registered_discord_ids (attempt {attempt+1}): {e}")
                try:
                    self.connect()
                except Exception:
                    pass
                if attempt == 1:
                    return set()
            except Exception as e:
                print(f"❌ Error getting registered IDs: {e}")
                return set()
    
    def get_registration_stats(self) -> dict:
        """Get registration statistics"""
        for attempt in range(2):
            try:
                self.ensure_connection()
                with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute("SELECT COUNT(*) as total FROM registrations")
                    total = cursor.fetchone()['total']
                    cursor.execute("SELECT team, COUNT(*) as count FROM registrations GROUP BY team")
                    teams = {row['team']: row['count'] for row in cursor.fetchall()}
                    cursor.execute("SELECT * FROM registrations ORDER BY timestamp DESC LIMIT 1")
                    latest = cursor.fetchone()
                    return {
                        'total': total,
                        'teams': teams,
                        'latest': latest
                    }
            except (OperationalError, InterfaceError) as e:
                print(f"⚠️ Transient DB error on get_registration_stats (attempt {attempt+1}): {e}")
                try:
                    self.connect()
                except Exception:
                    pass
                if attempt == 1:
                    return {'total': 0, 'teams': {}, 'latest': None}
            except Exception as e:
                print(f"❌ Error getting stats: {e}")
                return {'total': 0, 'teams': {}, 'latest': None}
    
    def remove_user_registration(self, discord_id: str) -> bool:
        """Remove user registration"""
        for attempt in range(2):
            try:
                self.ensure_connection()
                with self.connection.cursor() as cursor:
                    cursor.execute("DELETE FROM registrations WHERE discord_id = %s", (discord_id,))
                    rowcount = cursor.rowcount
                self.connection.commit()
                return rowcount > 0
            except (OperationalError, InterfaceError) as e:
                print(f"⚠️ Transient DB error on remove_user_registration (attempt {attempt+1}): {e}")
                try:
                    self.connect()
                except Exception:
                    pass
                if attempt == 1:
                    try:
                        self.connection.rollback()
                    except Exception:
                        pass
                    return False
            except Exception as e:
                print(f"❌ Error removing registration: {e}")
                try:
                    self.connection.rollback()
                except Exception:
                    pass
                return False
    
    def modify_user_registration(self, discord_id: str, field: str, new_value: str) -> Tuple[bool, str]:
        """Modify a specific field in user registration"""
        for attempt in range(2):
            try:
                self.ensure_connection()
                # Map field names to database columns
                field_mapping = {
                    'first_name': 'first_name',
                    'last_name': 'last_name',
                    'email': 'email',
                    'phone': 'phone',
                    'team': 'team',
                    'student_id': 'student_id',
                    'year_major': 'year_major',
                    'photo': 'photo'
                }
                
                if field not in field_mapping:
                    return False, f"Invalid field: {field}"
                
                db_field = field_mapping[field]
                
                with self.connection.cursor() as cursor:
                    cursor.execute(f"UPDATE registrations SET {db_field} = %s WHERE discord_id = %s", 
                                 (new_value, discord_id))
                    rowcount = cursor.rowcount
                
                self.connection.commit()
                
                if rowcount > 0:
                    return True, "Registration updated successfully"
                else:
                    return False, "User not found in registration database"
            except (OperationalError, InterfaceError) as e:
                print(f"⚠️ Transient DB error on modify_user_registration (attempt {attempt+1}): {e}")
                try:
                    self.connect()
                except Exception:
                    pass
                if attempt == 1:
                    try:
                        self.connection.rollback()
                    except Exception:
                        pass
                    return False, f"Error updating registration: {str(e)}"
            except Exception as e:
                print(f"❌ Error modifying registration: {e}")
                try:
                    self.connection.rollback()
                except Exception:
                    pass
                return False, f"Error updating registration: {str(e)}"
    
    def export_to_csv(self, filepath: str) -> bool:
        """Export all registrations to CSV"""
        for attempt in range(2):
            try:
                self.ensure_connection()
                with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute("""
                        SELECT last_name, first_name, photo, year_major, student_id, 
                               phone, email, discord_id, team, timestamp 
                        FROM registrations 
                        ORDER BY timestamp DESC
                    """)
                    registrations = cursor.fetchall()
                    if not registrations:
                        return False
                    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ['last_name', 'first_name', 'photo', 'year_major', 'student_id', 
                                    'phone', 'email', 'discord_id', 'team', 'timestamp']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        for row in registrations:
                            if row['timestamp']:
                                row['timestamp'] = row['timestamp'].isoformat()
                            writer.writerow(row)
                    return True
            except (OperationalError, InterfaceError) as e:
                print(f"⚠️ Transient DB error on export_to_csv (attempt {attempt+1}): {e}")
                try:
                    self.connect()
                except Exception:
                    pass
                if attempt == 1:
                    return False
            except Exception as e:
                print(f"❌ Error exporting to CSV: {e}")
                return False
    
    def log_admin_action(self, action: str, admin_user, details: str = ""):
        """Log admin actions to database"""
        for attempt in range(2):
            try:
                self.ensure_connection()
                with self.connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO admin_logs (action, admin_discord_id, admin_name, details)
                        VALUES (%s, %s, %s, %s)
                    """, (action, str(admin_user.id), str(admin_user), details))
                self.connection.commit()
                return
            except (OperationalError, InterfaceError) as e:
                print(f"⚠️ Transient DB error on log_admin_action (attempt {attempt+1}): {e}")
                try:
                    self.connect()
                except Exception:
                    pass
                if attempt == 1:
                    try:
                        self.connection.rollback()
                    except Exception:
                        pass
                    return
            except Exception as e:
                print(f"❌ Error logging action: {e}")
                try:
                    self.connection.rollback()
                except Exception:
                    pass
                return
    
    def get_all_registrations(self) -> List[dict]:
        """Get all registration data"""
        try:
            self.ensure_connection()
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT * FROM registrations ORDER BY timestamp DESC")
                return cursor.fetchall()
        except Exception as e:
            print(f"❌ Error getting all registrations: {e}")
            return []

# Global database instance
db = None

def get_db():
    """Get database instance"""
    global db
    if db is None:
        db = DatabaseManager()
    return db