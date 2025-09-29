# main.py - Club Registration Bot (MySQL version with health check)

import discord
from discord.ext import commands
from discord import app_commands
import config
import utils
from views import RegistrationView, ConfirmationView, DeleteConfirmationView
import os

# Import and start health check server
from keep_alive import keep_alive

# Your server ID
GUILD_ID = 659857443299393547

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None
)

# Admin-only manual sync command (prefix)
@bot.command(name='sync')
@commands.is_owner()
async def sync_commands(ctx: commands.Context):
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ Synced {len(synced)} global commands.")
    except Exception as e:
        await ctx.send(f"❌ Sync error: {e}")

# Admin utility: force sync commands to this guild now
@bot.command(name='sync_here')
@commands.has_permissions(administrator=True)
async def sync_here(ctx: commands.Context):
    try:
        if ctx.guild is None:
            await ctx.send("❌ Use this in a server channel.")
            return
        bot.tree.copy_global_to(guild=discord.Object(id=ctx.guild.id))
        synced = await bot.tree.sync(guild=discord.Object(id=ctx.guild.id))
        await ctx.send(f"✅ Synced {len(synced)} commands to this guild.")
    except Exception as e:
        await ctx.send(f"❌ Sync error: {e}")

@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    
    # Initialize database connection (do not block command sync if this fails)
    try:
        from database import get_db
        db = get_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed (continuing without DB): {e}")
    
    # Add persistent view
    try:
        bot.add_view(RegistrationView())
        print("Persistent views loaded!")
    except Exception as e:
        print(f"❌ Failed to load persistent views: {e}")
    
    # Sync commands globally and also per-guild for immediate availability
    try:
        global_synced = await bot.tree.sync()
        print(f"✅ Successfully synced {len(global_synced)} global commands!")
        for g in bot.guilds:
            try:
                bot.tree.copy_global_to(guild=discord.Object(id=g.id))
                guild_synced = await bot.tree.sync(guild=discord.Object(id=g.id))
                print(f"✅ Synced {len(guild_synced)} commands to guild {g.name} ({g.id})")
            except Exception as ge:
                print(f"❌ Guild sync error for {g.name} ({g.id}): {ge}")
    except Exception as e:
        print(f"❌ Sync error: {e}")


# Basic Commands
@bot.tree.command(name="setup_registration", description="Setup registration panel (Admin only)")
async def setup_registration(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Setup registration panel"""
    if not utils.has_admin_permissions(interaction.user):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    if channel is None:
        channel = interaction.channel
    
    embed = utils.create_registration_embed()
    view = RegistrationView()
    
    try:
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Panel setup in {channel.mention}!", ephemeral=True)
        utils.log_action("SETUP_REGISTRATION", interaction.user, f"Channel: {channel.name}")
    except discord.Forbidden:
        await interaction.response.send_message(f"❌ No permission in {channel.mention}!", ephemeral=True)

@bot.tree.command(name="registration_stats", description="View registration statistics (Admin only)")
async def registration_stats(interaction: discord.Interaction):
    """Show stats"""
    if not utils.has_admin_permissions(interaction.user):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    stats = utils.get_registration_stats()
    embed = discord.Embed(title="📊 Registration Statistics", color=discord.Color.green())
    embed.add_field(name="Total", value=f"**{stats['total']}** members", inline=False)
    
    if stats['teams']:
        teams_text = "\n".join([f"**{team}:** {count}" for team, count in stats['teams'].items()])
        embed.add_field(name="Teams", value=teams_text, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Registration Management Commands
@bot.tree.command(name="check_registration_status", description="Check registration status by member type (Admin only)")
async def check_registration_status(interaction: discord.Interaction):
    """Show detailed registration status"""
    if not utils.has_admin_permissions(interaction.user):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Fetch all members
    try:
        await interaction.guild.chunk()
    except Exception as e:
        print(f"Warning: Could not chunk guild members: {e}")
    
    members_with_teams, members_without_teams = utils.get_unregistered_members_with_teams(interaction.guild)
    
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

@bot.tree.command(name="assign_not_renewed", description="Assign 'not renewed' role to existing team members who didn't register (Admin only)")
async def assign_not_renewed(interaction: discord.Interaction):
    """Assign not renewed role to existing team members"""
    if not utils.has_admin_permissions(interaction.user):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Fetch all members
    try:
        await interaction.guild.chunk()
    except Exception as e:
        print(f"Warning: Could not chunk guild members: {e}")
    
    # Get not renewed role
    not_renewed_role = interaction.guild.get_role(config.NOT_RENEWED_ROLE_ID)
    if not not_renewed_role:
        await interaction.followup.send("❌ 'Not renewed' role not found! Check NOT_RENEWED_ROLE_ID in config.py")
        return
    
    # Get unregistered members with existing teams
    members_with_teams, _ = utils.get_unregistered_members_with_teams(interaction.guild)
    
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

@bot.tree.command(name="assign_unverified", description="Assign unverified role to new members (Admin only)")
async def assign_unverified(interaction: discord.Interaction):
    """Assign unverified role to new members"""
    if not utils.has_admin_permissions(interaction.user):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Fetch all members
    try:
        await interaction.guild.chunk()
    except Exception as e:
        print(f"Warning: Could not chunk guild members: {e}")
    
    unverified_role = interaction.guild.get_role(config.UNVERIFIED_ROLE_ID)
    if not unverified_role:
        await interaction.followup.send("❌ Unverified role not found!")
        return
    
    # Get only new members (no existing team roles)
    _, members_without_teams = utils.get_unregistered_members_with_teams(interaction.guild)
    
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

@bot.tree.command(name="kick_new_members", description="Kick unregistered new members (without existing team roles) (Admin only)")
async def kick_new_members(interaction: discord.Interaction):
    """Kick only new members without existing team roles"""
    if not utils.has_admin_permissions(interaction.user):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Check bot permissions
    bot_member = interaction.guild.get_member(bot.user.id)
    if not bot_member or not bot_member.guild_permissions.kick_members:
        await interaction.followup.send("❌ Bot doesn't have kick permissions!", ephemeral=True)
        return
    
    # Ensure member cache is populated
    try:
        await interaction.guild.chunk()
    except Exception as e:
        print(f"Warning: Could not chunk guild members: {e}")
    
    # Get new members who should be kicked
    _, members_without_teams = utils.get_unregistered_members_with_teams(interaction.guild)
    
    # Filter out bots and members we can't kick
    kickable_members = []
    skipped_members = []
    
    for member in members_without_teams:
        # Skip bots
        if member.bot:
            continue
        # Skip if member has higher role than bot
        if member.top_role >= bot_member.top_role:
            skipped_members.append(f"{member.display_name} (higher role)")
            continue
        # Skip administrators
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
    
    # Create confirmation embed with better info
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
    
    # Show preview
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

# Individual Management Commands
@bot.tree.command(name="search_registration", description="Search registration (Admin only)")
async def search_registration(interaction: discord.Interaction, user: discord.Member):
    """Search user registration"""
    if not utils.has_admin_permissions(interaction.user):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    registration = utils.get_user_registration(str(user.id))
    
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

@bot.tree.command(name="delete_registration", description="Delete registration (Admin only)")
async def delete_registration(interaction: discord.Interaction, user: discord.Member):
    """Delete registration"""
    if not utils.has_admin_permissions(interaction.user):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    registration = utils.get_user_registration(str(user.id))
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

@bot.tree.command(name="export_registrations", description="Export CSV (Admin only)")
async def export_registrations(interaction: discord.Interaction):
    """Export CSV"""
    if not utils.has_admin_permissions(interaction.user):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Export to temporary CSV file
        success = utils.export_registrations_to_csv(config.TEMP_CSV_FILE)
        
        if success:
            with open(config.TEMP_CSV_FILE, 'rb') as f:
                file = discord.File(f, filename="registrations.csv")
                await interaction.followup.send("📄 Registration database:", file=file)
            
            # Clean up temp file
            try:
                os.remove(config.TEMP_CSV_FILE)
            except:
                pass
                
            utils.log_action("EXPORT_CSV", interaction.user, "Exported database")
        else:
            await interaction.followup.send("❌ No registrations found or export failed.")
            
    except Exception as e:
        await interaction.followup.send(f"❌ Export error: {e}")

# Error handler
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Avoid replying after timeouts or when the command isn't found
    try:
        from discord.app_commands import CommandNotFound
        if isinstance(error, CommandNotFound):
            print("CommandNotFound for interaction; ignoring.")
            return
    except Exception:
        pass
    print(f"Command error: {error}")
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Command error occurred.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Command error occurred.", ephemeral=True)
    except Exception:
        # Swallow errors like Unknown interaction (already timed out)
        pass

# Run bot
if __name__ == "__main__":
    print("Starting Club Registration Bot...")
    
    # Start health check server
    keep_alive()
    
    # Run Discord bot
    bot.run(config.BOT_TOKEN)