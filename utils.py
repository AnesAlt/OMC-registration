# utils.py - Utility functions (MySQL version)

import discord
import re
import os
from datetime import datetime
from typing import List, Set, Optional, Tuple
import config
from database import get_db

def has_admin_permissions(user: discord.Member) -> bool:
    """Check if user has admin permissions (role or user ID)"""
    # Check if user ID is in admin list
    if user.id in config.ADMIN_USER_IDS:
        return True
    
    # Check if user has any admin roles
    user_role_ids = [role.id for role in user.roles]
    return any(role_id in config.ADMIN_ROLE_IDS for role_id in user_role_ids)

def check_registration_eligibility(user: discord.Member) -> Tuple[bool, str]:
    """
    Simplified eligibility check: Everyone must register except excluded roles
    Returns: (is_eligible, reason_if_not_eligible)
    """
    user_role_ids = [role.id for role in user.roles]
    
    # Check if user has any excluded roles (staff, special cases, etc.)
    has_excluded_role = any(role_id in config.EXCLUDED_ROLE_IDS for role_id in user_role_ids)
    if has_excluded_role:
        return False, "You're not concerned with this registration"
    
    # Everyone else must register
    return True, ""

def validate_email(email: str) -> bool:
    """Validate email format"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email.strip()))

def validate_phone(phone: str) -> str:
    """Clean and validate phone number, return cleaned version"""
    # Remove all non-digit characters
    phone_clean = re.sub(r'[^\d]', '', phone)
    return phone_clean

def validate_field_value(field: str, value: str) -> Optional[str]:
    """Validate a field value for registration modification. Returns error message if invalid."""
    value = value.strip()
    
    if field in ["first_name", "last_name"]:
        if not value:
            return f"{field.replace('_', ' ').title()} cannot be empty"
        if len(value) > 100:
            return f"{field.replace('_', ' ').title()} cannot be longer than 100 characters"
    
    elif field == "email":
        if not value:
            return "Email cannot be empty"
        if not validate_email(value):
            return "Invalid email format"
        if len(value) > 100:
            return "Email cannot be longer than 100 characters"
    
    elif field == "phone":
        phone_clean = re.sub(r'[^\d]', '', value)
        if not phone_clean:
            return "Phone number cannot be empty"
        if len(phone_clean) != 10:
            return "Phone number must be exactly 10 digits"
    
    elif field == "team":
        valid_teams = ["IT", "Design", "Marketing", "B2B", "OPS", "HR"]
        if value not in valid_teams:
            return f"Invalid team. Must be one of: {', '.join(valid_teams)}"
    
    elif field == "student_id":
        if not value:
            return "Student ID cannot be empty"
        if not value.isdigit():
            return "Student ID must contain only numbers"
        if len(value) < 5:
            return "Student ID must be at least 5 digits long"
    
    elif field == "year_major":
        if not value:
            return "Year + Major cannot be empty"
        if len(value) > 150:
            return "Year + Major cannot be longer than 150 characters"
    
    elif field == "photo":
        if not value:
            return "Photo URL cannot be empty"
        if len(value) > 500:
            return "Photo URL cannot be longer than 500 characters"
    
    return None

def get_registered_discord_ids() -> Set[str]:
    """Get all registered Discord IDs from database"""
    db = get_db()
    return db.get_registered_discord_ids()

def is_user_registered(discord_id: str) -> bool:
    """Check if a specific Discord ID is already registered"""
    db = get_db()
    return db.is_user_registered(discord_id)

def save_registration_to_db(registration_data: dict) -> bool:
    """Save registration data to database"""
    db = get_db()
    return db.save_registration(registration_data)

def get_registration_stats() -> dict:
    """Get registration statistics from database"""
    db = get_db()
    return db.get_registration_stats()

def get_unregistered_members_with_teams(guild: discord.Guild) -> Tuple[List[discord.Member], List[discord.Member]]:
    """
    Get unregistered members split by whether they have existing team roles
    Returns: (members_with_teams, members_without_teams)
    """
    registered_ids = get_registered_discord_ids()
    
    members_with_teams = []
    members_without_teams = []
    
    for member in guild.members:
        if str(member.id) not in registered_ids:
            is_eligible, _ = check_registration_eligibility(member)
            if is_eligible:
                user_role_ids = [role.id for role in member.roles]
                has_existing_team = any(role_id in config.EXISTING_TEAM_ROLE_IDS for role_id in user_role_ids)
                
                if has_existing_team:
                    members_with_teams.append(member)
                else:
                    members_without_teams.append(member)
    
    return members_with_teams, members_without_teams

def get_unregistered_members(guild: discord.Guild) -> List[discord.Member]:
    """Get list of eligible members who haven't registered (all types)"""
    members_with_teams, members_without_teams = get_unregistered_members_with_teams(guild)
    return members_with_teams + members_without_teams

def create_registration_embed() -> discord.Embed:
    """Create the registration panel embed"""
    embed = discord.Embed(
        title="🔄 Re-Registration",
        description="Did you enjoy your time last year at OMC? Let's have another great year together!",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Complete all fields to finalize your registration")
    return embed

def log_action(action: str, user: discord.User, details: str = ""):
    """Log admin actions to database"""
    db = get_db()
    db.log_admin_action(action, user, details)

def remove_user_from_db(discord_id: str) -> bool:
    """Remove a user from the database"""
    db = get_db()
    return db.remove_user_registration(discord_id)

def get_user_registration(discord_id: str) -> dict:
    """Get a specific user's registration data"""
    db = get_db()
    return db.get_user_registration(discord_id)

def get_all_registrations() -> list:
    """Get all registration data from database"""
    db = get_db()
    return db.get_all_registrations()

def modify_user_registration(discord_id: str, field: str, new_value: str) -> Tuple[bool, str]:
    """
    Modify a specific field in a user's registration.
    Returns: (success: bool, message: str)
    """
    db = get_db()
    return db.modify_user_registration(discord_id, field, new_value)

def export_registrations_to_csv(filepath: str) -> bool:
    """Export all registrations to CSV file"""
    db = get_db()
    return db.export_to_csv(filepath)