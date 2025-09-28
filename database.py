# database.py - MySQL Database Utilities

import pymysql
import os
import csv
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import config

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Connect to MySQL database"""
        try:
            self.connection = pymysql.connect(**config.DATABASE_CONFIG)
            print("✅ Connected to MySQL database")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
    
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
                
            print("✅ Database tables created/verified")
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            raise
    
    def save_registration(self, registration_data: dict) -> bool:
        """Save registration to database"""
        try:
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
            return True
        except Exception as e:
            print(f"❌ Error saving registration: {e}")
            return False
    
    def is_user_registered(self, discord_id: str) -> bool:
        """Check if user is registered"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM registrations WHERE discord_id = %s", (discord_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"❌ Error checking registration: {e}")
            return False
    
    def get_user_registration(self, discord_id: str) -> Optional[dict]:
        """Get user registration data"""
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT * FROM registrations WHERE discord_id = %s", (discord_id,))
                return cursor.fetchone()
        except Exception as e:
            print(f"❌ Error getting registration: {e}")
            return None
    
    def get_registered_discord_ids(self) -> set:
        """Get all registered Discord IDs"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT discord_id FROM registrations")
                return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            print(f"❌ Error getting registered IDs: {e}")
            return set()
    
    def get_registration_stats(self) -> dict:
        """Get registration statistics"""
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # Get total count
                cursor.execute("SELECT COUNT(*) as total FROM registrations")
                total = cursor.fetchone()['total']
                
                # Get team counts
                cursor.execute("SELECT team, COUNT(*) as count FROM registrations GROUP BY team")
                teams = {row['team']: row['count'] for row in cursor.fetchall()}
                
                # Get latest registration
                cursor.execute("SELECT * FROM registrations ORDER BY timestamp DESC LIMIT 1")
                latest = cursor.fetchone()
                
                return {
                    'total': total,
                    'teams': teams,
                    'latest': latest
                }
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {'total': 0, 'teams': {}, 'latest': None}
    
    def remove_user_registration(self, discord_id: str) -> bool:
        """Remove user registration"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("DELETE FROM registrations WHERE discord_id = %s", (discord_id,))
                return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Error removing registration: {e}")
            return False
    
    def modify_user_registration(self, discord_id: str, field: str, new_value: str) -> Tuple[bool, str]:
        """Modify a specific field in user registration"""
        try:
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
                
                if cursor.rowcount > 0:
                    return True, "Registration updated successfully"
                else:
                    return False, "User not found in registration database"
                    
        except Exception as e:
            print(f"❌ Error modifying registration: {e}")
            return False, f"Error updating registration: {str(e)}"
    
    def export_to_csv(self, filepath: str) -> bool:
        """Export all registrations to CSV"""
        try:
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
                
                # Write to CSV
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['last_name', 'first_name', 'photo', 'year_major', 'student_id', 
                                'phone', 'email', 'discord_id', 'team', 'timestamp']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for row in registrations:
                        # Convert datetime to string for CSV
                        if row['timestamp']:
                            row['timestamp'] = row['timestamp'].isoformat()
                        writer.writerow(row)
                
                return True
        except Exception as e:
            print(f"❌ Error exporting to CSV: {e}")
            return False
    
    def log_admin_action(self, action: str, admin_user, details: str = ""):
        """Log admin actions to database"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO admin_logs (action, admin_discord_id, admin_name, details)
                    VALUES (%s, %s, %s, %s)
                """, (action, str(admin_user.id), str(admin_user), details))
        except Exception as e:
            print(f"❌ Error logging action: {e}")
    
    def get_all_registrations(self) -> List[dict]:
        """Get all registration data"""
        try:
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