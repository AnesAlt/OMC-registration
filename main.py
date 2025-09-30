# main.py - Club Registration Bot (MySQL version with health check)

import discord
from discord.ext import commands, tasks
from discord import app_commands
import config
import utils
from views import RegistrationView, ConfirmationView, DeleteConfirmationView
from database import get_db
import os
import asyncio
import sys
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

print("=" * 50)
print("ENVIRONMENT VARIABLES CHECK")
print(f"BOT_TOKEN: {'SET' if os.getenv('BOT_TOKEN') else 'MISSING'}")
print(f"MYSQL_PUBLIC_URL: {os.getenv('MYSQL_PUBLIC_URL', 'NOT SET')}")
print("=" * 50)

from keep_alive import keep_alive

GUILD_ID = 659857443299393547

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None
)

@tasks.loop(seconds=120)
async def db_keepalive():
    """Periodic task to keep DB connection alive and reconnect if needed"""
    try:
        db = get_db()
        db.ensure_connection()
    except Exception as e:
        print(f"⚠️ DB keepalive ping failed: {e}")

@bot.tree.command(name="ping_bot", description="Basic ping to verify bot is responsive")
async def ping_bot(interaction: discord.Interaction):
    try:
        await interaction.response.send_message("🏓 Pong!", ephemeral=True)
    except Exception as e:
        print(f"Error in ping_bot: {e}")

@bot.tree.command(name="db_ping", description="Check database connectivity")
async def db_ping(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        db = get_db()
        db.ensure_connection()
        await interaction.followup.send("✅ DB connection OK")
    except discord.errors.NotFound:
        print("db_ping: Interaction expired")
    except Exception as e:
        print(f"DB ping failed: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds:')
    for guild in bot.guilds:
        print(f"  → {guild.name} (ID: {guild.id})")
    
    try:
        db = get_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return
    
    bot.add_view(RegistrationView())
    print("Persistent views loaded!")
    
    try:
        if not db_keepalive.is_running():
            db_keepalive.start()
            print("✅ DB keepalive task started")
    except Exception as e:
        print(f"⚠️ Could not start DB keepalive task: {e}")

    try:
        global_synced = await bot.tree.sync()
        print(f"✅ Global sync complete: {len(global_synced)} commands")
    except Exception as e:
        print(f"❌ Global sync error: {e}")

@bot.tree.command(name="setup_registration", description="Setup registration panel (Admin only)")
async def setup_registration(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Setup registration panel"""
    try:
        # DEFER IMMEDIATELY
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_admin_permissions(interaction.user):
            await interaction.followup.send("❌ No permission!")
            return

        if channel is None:
            channel = interaction.channel
        
        embed = utils.create_registration_embed()
        view = RegistrationView()
        
        await channel.send(embed=embed, view=view)
        await interaction.followup.send(f"✅ Panel setup in {channel.mention}!")
        utils.log_action("SETUP_REGISTRATION", interaction.user, f"Channel: {channel.name}")
    except discord.Forbidden:
        await interaction.followup.send(f"❌ No permission in {channel.mention}!")
    except discord.errors.NotFound:
        print("setup_registration: Interaction expired")
    except Exception as e:
        print(f"Error in setup_registration: {e}")

@bot.tree.command(name="registration_stats", description="View registration statistics (Admin only)")
async def registration_stats(interaction: discord.Interaction):
    """Show stats"""
    try:
        # DEFER IMMEDIATELY
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_admin_permissions(interaction.user):
            await interaction.followup.send("❌ No permission!")
            return

        stats = await asyncio.to_thread(utils.get_registration_stats)
        embed = discord.Embed(title="📊 Registration Statistics", color=discord.Color.green())
        embed.add_field(name="Total", value=f"**{stats['total']}** members", inline=False)
        
        if stats['teams']:
            teams_text = "\n".join([f"**{team}:** {count}" for team, count in stats['teams'].items()])
            embed.add_field(name="Teams", value=teams_text, inline=False)
        
        await interaction.followup.send(embed=embed)
    except discord.errors.NotFound:
        print("registration_stats: Interaction expired")
    except Exception as e:
        print(f"Error in registration_stats: {e}")

@bot.tree.command(name="check_registration_status", description="Check registration status by member type (Admin only)")
async def check_registration_status(interaction: discord.Interaction):
    """Show detailed registration status"""
    try:
        # DEFER IMMEDIATELY
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_admin_permissions(interaction.user):
            await interaction.followup.send("❌ No permission!")
            return
        
        try:
            await interaction.guild.chunk()
        except Exception as e:
            print(f"Warning: Could not chunk guild members: {e}")
        
        registered_ids = await asyncio.to_thread(utils.get_registered_discord_ids)
        members_with_teams = []
        members_without_teams = []
        for member in interaction.guild.members:
            if str(member.id) not in registered_ids:
                is_eligible, _ = utils.check_registration_eligibility(member)
                if is_eligible:
                    user_role_ids = [role.id for role in member.roles]
                    has_existing_team = any(role_id in config.EXISTING_TEAM_ROLE_IDS for role_id in user_role_ids)
                    if has_existing_team:
                        members_with_teams.append(member)
                    else:
                        members_without_teams.append(member)
        
        embed = discord.Embed(title="📊 Registration Status by Member Type", color=discord.Color.blue())
        
        embed.add_field(
            name="🔄 Existing Team Members (Unregistered)",
            value=f"**{len(members_with_teams)}** members\n(Will get 'not renewed' role)",
            inline=True
        )
        
        embed.add_field(
            name="❌ New Members (Unregistered)", 
            value=f"**{len(members_without_teams)}** members\n(Will be kicked)",
            inline=True
        )
        
        if not members_with_teams and not members_without_teams:
            embed.add_field(name="Status", value="✅ All eligible members have registered!", inline=False)
        
        await interaction.followup.send(embed=embed)
    except discord.errors.NotFound:
        print("check_registration_status: Interaction expired")
    except Exception as e:
        print(f"Error in check_registration_status: {e}")

@bot.tree.command(name="assign_not_renewed", description="Assign 'not renewed' role to existing team members who didn't register (Admin only)")
async def assign_not_renewed(interaction: discord.Interaction):
    """Assign not renewed role to existing team members"""
    try:
        # DEFER IMMEDIATELY
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_admin_permissions(interaction.user):
            await interaction.followup.send("❌ No permission!")
            return
        
        try:
            await interaction.guild.chunk()
        except Exception as e:
            print(f"Warning: Could not chunk guild members: {e}")
        
        not_renewed_role = interaction.guild.get_role(config.NOT_RENEWED_ROLE_ID)
        if not not_renewed_role:
            await interaction.followup.send("❌ 'Not renewed' role not found! Check NOT_RENEWED_ROLE_ID in config.py")
            return
        
        registered_ids = await asyncio.to_thread(utils.get_registered_discord_ids)
        members_with_teams = []
        for member in interaction.guild.members:
            if str(member.id) not in registered_ids:
                is_eligible, _ = utils.check_registration_eligibility(member)
                if is_eligible:
                    user_role_ids = [role.id for role in member.roles]
                    if any(role_id in config.EXISTING_TEAM_ROLE_IDS for role_id in user_role_ids):
                        members_with_teams.append(member)
        
        if not members_with_teams:
            await interaction.followup.send("✅ All existing team members have registered!")
            return
        
        processed = 0
        already_had = 0
        errors = 0
        
        for member in members_with_teams:
            try:
                if not_renewed_role in member.roles:
                    already_had += 1
                else:
                    await member.add_roles(not_renewed_role, reason="Existing team member who didn't renew")
                    processed += 1
            except Exception as e:
                print(f"Error assigning not renewed role to {member}: {e}")
                errors += 1
        
        utils.log_action("ASSIGN_NOT_RENEWED", interaction.user, f"Assigned: {processed}")
        
        embed = discord.Embed(title="✅ Not Renewed Role Assignment", color=discord.Color.orange())
        embed.add_field(name="Newly Assigned", value=str(processed), inline=True)
        embed.add_field(name="Already Had Role", value=str(already_had), inline=True)
        embed.add_field(name="Errors", value=str(errors), inline=True)
        
        await interaction.followup.send(embed=embed)
    except discord.errors.NotFound:
        print("assign_not_renewed: Interaction expired")
    except Exception as e:
        print(f"Error in assign_not_renewed: {e}")

@bot.tree.command(name="assign_unverified", description="Assign unverified role to new members (Admin only)")
async def assign_unverified(interaction: discord.Interaction):
    """Assign unverified role to new members"""
    try:
        # DEFER IMMEDIATELY
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_admin_permissions(interaction.user):
            await interaction.followup.send("❌ No permission!")
            return
        
        try:
            await interaction.guild.chunk()
        except Exception as e:
            print(f"Warning: Could not chunk guild members: {e}")
        
        unverified_role = interaction.guild.get_role(config.UNVERIFIED_ROLE_ID)
        if not unverified_role:
            await interaction.followup.send("❌ Unverified role not found!")
            return
        
        registered_ids = await asyncio.to_thread(utils.get_registered_discord_ids)
        members_without_teams = []
        for member in interaction.guild.members:
            if str(member.id) not in registered_ids:
                is_eligible, _ = utils.check_registration_eligibility(member)
                if is_eligible:
                    user_role_ids = [role.id for role in member.roles]
                    has_existing_team = any(role_id in config.EXISTING_TEAM_ROLE_IDS for role_id in user_role_ids)
                    if not has_existing_team:
                        members_without_teams.append(member)
        
        if not members_without_teams:
            await interaction.followup.send("✅ All new members have registered!")
            return
        
        processed = 0
        already_had = 0
        errors = 0
        
        for member in members_without_teams:
            try:
                if unverified_role in member.roles:
                    already_had += 1
                else:
                    await member.add_roles(unverified_role, reason="Unregistered new member")
                    processed += 1
            except Exception as e:
                print(f"Error with {member}: {e}")
                errors += 1
        
        utils.log_action("ASSIGN_UNVERIFIED", interaction.user, f"Assigned: {processed}")
        
        embed = discord.Embed(title="✅ Unverified Role Assignment", color=discord.Color.blue())
        embed.add_field(name="Newly Assigned", value=str(processed), inline=True)
        embed.add_field(name="Already Had Role", value=str(already_had), inline=True)
        embed.add_field(name="Errors", value=str(errors), inline=True)
        
        await interaction.followup.send(embed=embed)
    except discord.errors.NotFound:
        print("assign_unverified: Interaction expired")
    except Exception as e:
        print(f"Error in assign_unverified: {e}")

@bot.tree.command(name="kick_new_members", description="Kick unregistered new members (without existing team roles) (Admin only)")
async def kick_new_members(interaction: discord.Interaction):
    """Kick only new members without existing team roles"""
    try:
        # DEFER IMMEDIATELY
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_admin_permissions(interaction.user):
            await interaction.followup.send("❌ No permission!")
            return
        
        bot_member = interaction.guild.get_member(bot.user.id)
        if not bot_member or not bot_member.guild_permissions.kick_members:
            await interaction.followup.send("❌ Bot doesn't have kick permissions!")
            return
        
        try:
            await interaction.guild.chunk()
        except Exception as e:
            print(f"Warning: Could not chunk guild members: {e}")
        
        registered_ids = await asyncio.to_thread(utils.get_registered_discord_ids)
        members_without_teams = []
        for member in interaction.guild.members:
            if str(member.id) not in registered_ids:
                is_eligible, _ = utils.check_registration_eligibility(member)
                if is_eligible:
                    user_role_ids = [role.id for role in member.roles]
                    has_existing_team = any(role_id in config.EXISTING_TEAM_ROLE_IDS for role_id in user_role_ids)
                    if not has_existing_team:
                        members_without_teams.append(member)
        
        kickable_members = []
        skipped_members = []
        
        for member in members_without_teams:
            if member.bot:
                continue
            if member.top_role >= bot_member.top_role:
                skipped_members.append(f"{member.display_name} (higher role)")
                continue
            if member.guild_permissions.administrator:
                skipped_members.append(f"{member.display_name} (admin)")
                continue
            kickable_members.append(member)
        
        if not kickable_members:
            msg = "✅ All new members have registered!"
            if skipped_members:
                msg += f"\n\n**Note:** {len(skipped_members)} members were skipped (bots/admins/higher roles)"
            await interaction.followup.send(msg)
            return
        
        embed = discord.Embed(
            title="⚠️ Kick New Members Confirmation",
            description=f"About to kick **{len(kickable_members)}** unregistered new members.\n\n"
                       f"**Criteria:**\n"
                       f"• Not registered in database\n"
                       f"• No existing team roles\n"
                       f"• Not bots or admins\n\n"
                       f"**⚠️ This action cannot be undone!**",
            color=discord.Color.red()
        )
        
        preview = []
        for i, member in enumerate(kickable_members[:10], 1):
            roles = [r.name for r in member.roles if r.name != "@everyone"]
            role_text = f" ({', '.join(roles[:3])})" if roles else " (no roles)"
            preview.append(f"{i}. {member.mention} - {member.name}{role_text}")
        
        embed.add_field(
            name=f"Preview (showing {min(10, len(kickable_members))} of {len(kickable_members)})",
            value="\n".join(preview) + 
                  (f"\n... and {len(kickable_members) - 10} more" if len(kickable_members) > 10 else ""),
            inline=False
        )
        
        if skipped_members:
            embed.add_field(
                name=f"⚠️ Skipped ({len(skipped_members)})",
                value="\n".join(skipped_members[:5]) + 
                      (f"\n... and {len(skipped_members) - 5} more" if len(skipped_members) > 5 else ""),
                inline=False
            )
        
        view = ConfirmationView(kickable_members)
        await interaction.followup.send(embed=embed, view=view)
    except discord.errors.NotFound:
        print("kick_new_members: Interaction expired")
    except Exception as e:
        print(f"Error in kick_new_members: {e}")

@bot.tree.command(name="search_registration", description="Search registration (Admin only)")
async def search_registration(interaction: discord.Interaction, user: discord.Member):
    """Search user registration"""
    try:
        # DEFER IMMEDIATELY
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_admin_permissions(interaction.user):
            await interaction.followup.send("❌ No permission!")
            return
        
        registration = await asyncio.to_thread(utils.get_user_registration, str(user.id))
        
        if registration:
            embed = discord.Embed(title=f"Registration: {user.display_name}", color=discord.Color.blue())
            embed.add_field(name="Name", value=f"{registration['first_name']} {registration['last_name']}", inline=True)
            embed.add_field(name="Team", value=registration['team'], inline=True)
            embed.add_field(name="Email", value=registration['email'], inline=False)
            embed.add_field(name="Phone", value=registration['phone'], inline=False)
            embed.add_field(name="Student ID", value=registration['student_id'], inline=True)
            embed.add_field(name="Year/Major", value=registration['year_major'], inline=True)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ {user.mention} not registered.")
    except discord.errors.NotFound:
        print("search_registration: Interaction expired")
    except Exception as e:
        print(f"Error in search_registration: {e}")

@bot.tree.command(name="delete_registration", description="Delete registration (Admin only)")
async def delete_registration(interaction: discord.Interaction, user: discord.Member):
    """Delete registration"""
    try:
        # DEFER IMMEDIATELY
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_admin_permissions(interaction.user):
            await interaction.followup.send("❌ No permission!")
            return
        
        registration = await asyncio.to_thread(utils.get_user_registration, str(user.id))
        if not registration:
            await interaction.followup.send(f"❌ {user.mention} not registered.")
            return
        
        view = DeleteConfirmationView(user, registration)
        
        embed = discord.Embed(
            title="⚠️ Delete Confirmation", 
            description=f"Delete {user.mention}'s registration?\n\n"
                       f"**Name:** {registration['first_name']} {registration['last_name']}\n"
                       f"**Team:** {registration['team']}\n\n**Cannot be undone!**",
            color=discord.Color.red()
        )
        
        await interaction.followup.send(embed=embed, view=view)
    except discord.errors.NotFound:
        print("delete_registration: Interaction expired")
    except Exception as e:
        print(f"Error in delete_registration: {e}")

@bot.tree.command(name="export_registrations", description="Export CSV (Admin only)")
async def export_registrations(interaction: discord.Interaction):
    """Export CSV"""
    try:
        # DEFER IMMEDIATELY
        await interaction.response.defer(ephemeral=True)
        
        if not utils.has_admin_permissions(interaction.user):
            await interaction.followup.send("❌ No permission!")
            return
        
        success = await asyncio.to_thread(utils.export_registrations_to_csv, config.TEMP_CSV_FILE)
        
        if success:
            with open(config.TEMP_CSV_FILE, 'rb') as f:
                file = discord.File(f, filename="registrations.csv")
                await interaction.followup.send("📄 Registration database:", file=file)
            
            try:
                os.remove(config.TEMP_CSV_FILE)
            except:
                pass
                
            utils.log_action("EXPORT_CSV", interaction.user, "Exported database")
        else:
            await interaction.followup.send("❌ No registrations found or export failed.")
    except discord.errors.NotFound:
        print("export_registrations: Interaction expired")
    except Exception as e:
        print(f"Error in export_registrations: {e}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Global error handler - just log, commands handle their own responses"""
    import traceback
    print(f"Command error: {error}")
    traceback.print_exc()

if __name__ == "__main__":
    print("Starting Club Registration Bot...")
    keep_alive()
    bot.run(config.BOT_TOKEN)