# views.py - Discord UI Views (MySQL version)

import discord
from datetime import datetime
import config
import utils

class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view

    @discord.ui.button(label="Register for Club", style=discord.ButtonStyle.primary, emoji="📝", custom_id="registration_button")
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check registration eligibility first
        is_eligible, reason = utils.check_registration_eligibility(interaction.user)
        if not is_eligible:
            await interaction.response.send_message(
                f"❌ **{reason}**",
                ephemeral=True
            )
            return
        
        # Check if user is already registered
        if utils.is_user_registered(str(interaction.user.id)):
            await interaction.response.send_message(
                "❌ **Already Registered!**\n"
                "You have already completed your club registration. "
                "Each member can only register once.",
                ephemeral=True
            )
            return
        
        from modals import RegistrationModal  # Import here to avoid circular import
        modal = RegistrationModal()
        await interaction.response.send_modal(modal)

class TeamSelectionView(discord.ui.View):
    def __init__(self, nom, prenom, photo, annee_specialite, matricule, phone, email, discord_id):
        super().__init__(timeout=config.REGISTRATION_TIMEOUT)
        
        # Store all registration data
        self.registration_data = {
            'nom': nom,
            'prenom': prenom,
            'photo': photo,
            'annee_specialite': annee_specialite,
            'matricule': matricule,
            'phone': phone,
            'email': email,
            'discord_id': discord_id,
            'timestamp': datetime.now().isoformat()
        }

    @discord.ui.button(label="IT", emoji="💻", style=discord.ButtonStyle.secondary, row=0)
    async def it_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_team_selection(interaction, "IT")

    @discord.ui.button(label="Design", emoji="🎨", style=discord.ButtonStyle.secondary, row=0)
    async def design_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_team_selection(interaction, "Design")

    @discord.ui.button(label="Marketing", emoji="📢", style=discord.ButtonStyle.secondary, row=0)
    async def marketing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_team_selection(interaction, "Marketing")

    @discord.ui.button(label="B2B", emoji="🤝", style=discord.ButtonStyle.secondary, row=1)
    async def b2b_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_team_selection(interaction, "B2B")

    @discord.ui.button(label="OPS", emoji="⚙️", style=discord.ButtonStyle.secondary, row=1)
    async def ops_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_team_selection(interaction, "OPS")

    @discord.ui.button(label="HR", emoji="👥", style=discord.ButtonStyle.secondary, row=1)
    async def hr_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_team_selection(interaction, "HR")

    async def handle_team_selection(self, interaction: discord.Interaction, team_value: str):
        # Final eligibility check
        is_eligible, reason = utils.check_registration_eligibility(interaction.user)
        if not is_eligible:
            await interaction.response.edit_message(
                content=f"❌ **Registration Error!**\n{reason}",
                view=None
            )
            return
        
        # Final check if user is already registered (race condition protection)
        if utils.is_user_registered(self.registration_data['discord_id']):
            await interaction.response.edit_message(
                content="❌ **Registration Error!**\n"
                       "You have already been registered. Each member can only register once.",
                view=None
            )
            return
        
        # Store the team name in database
        self.registration_data['team'] = team_value
        
        # Save to database
        success = utils.save_registration_to_db(self.registration_data)
        
        if success:
            # Log the registration
            utils.log_action(
                "REGISTRATION", 
                interaction.user, 
                f"Team: {team_value}, Name: {self.registration_data['prenom']} {self.registration_data['nom']}"
            )
            
            await interaction.response.edit_message(
                content=f"🎉 **Registration Complete!**\n"
                       f"Welcome {self.registration_data['prenom']} {self.registration_data['nom']}!\n"
                       f"Team: {team_value}\n\n"
                       f"Thank you for registering with the club!",
                view=None
            )
        else:
            await interaction.response.edit_message(
                content="❌ **Error:** Failed to save registration. Please try again or contact an administrator.",
                view=None
            )

    async def on_timeout(self):
        # Disable the view when it times out
        for item in self.children:
            item.disabled = True

class ConfirmationView(discord.ui.View):
    def __init__(self, members_to_kick: list):
        super().__init__(timeout=60)  # 1 minute timeout
        self.members_to_kick = members_to_kick
        self.confirmed = False

    @discord.ui.button(label="Confirm Kick", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        
        await interaction.response.edit_message(
            content="⏳ **Processing kicks...** This may take a moment.",
            view=None
        )
        
        processed = 0
        errors = 0
        
        for member in self.members_to_kick:
            try:
                await member.kick(reason="Failed to complete club registration within deadline")
                processed += 1
            except Exception as e:
                print(f"Error kicking {member}: {e}")
                errors += 1
        
        # Log the action
        utils.log_action(
            "DEADLINE_ENFORCEMENT", 
            interaction.user, 
            f"Kicked: {processed}, Errors: {errors}"
        )
        
        await interaction.edit_original_response(
            content=f"✅ **Deadline Enforcement Complete**\n"
                   f"Kicked {processed} unregistered members\n"
                   f"Errors: {errors}"
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ **Action cancelled.**",
            view=None
        )
        self.stop()

class DeleteConfirmationView(discord.ui.View):
    def __init__(self, user: discord.Member, registration: dict):
        super().__init__(timeout=60)  # 1 minute timeout
        self.user = user
        self.registration = registration

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="⏳ **Deleting registration...** Please wait.",
            view=None
        )
        
        success = utils.remove_user_from_db(str(self.user.id))
        
        if success:
            await interaction.edit_original_response(
                content=f"✅ **Registration Deleted Successfully**\n\n"
                       f"**Deleted registration for:** {self.user.mention}\n"
                       f"**Name:** {self.registration['first_name']} {self.registration['last_name']}\n"
                       f"**Team:** {self.registration['team']}\n"
                       f"**Email:** {self.registration['email']}\n\n"
                       f"The user can now register again if needed."
            )
            
            # Log the action
            utils.log_action(
                "DELETE_REGISTRATION", 
                interaction.user, 
                f"Deleted: {self.user} ({self.registration['first_name']} {self.registration['last_name']})"
            )
        else:
            await interaction.edit_original_response(
                content="❌ **Error:** Failed to delete registration. Please try again or check the logs."
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ **Deletion cancelled.** Registration remains unchanged.",
            view=None
        )
        self.stop()