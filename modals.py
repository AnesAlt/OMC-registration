# modals.py - Discord UI Modals

import discord
import utils
from datetime import datetime
import re

class RegistrationModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Team Re-Registration")
        
        # Define all form fields
        self.nom = discord.ui.TextInput(
            label="Last Name",
            placeholder="Enter your last name...",
            required=True,
            max_length=100
        )
        
        self.prenom = discord.ui.TextInput(
            label="First Name", 
            placeholder="Enter your first name...",
            required=True,
            max_length=100
        )
        
        self.photo = discord.ui.TextInput(
            label="Photo URL",
            placeholder="https://example.com/your-photo.jpg",
            required=True,
            max_length=500
        )
        
        self.annee_specialite = discord.ui.TextInput(
            label="Year + Field of Study",
            placeholder="e.g., 3rd Year Computer Science",
            required=True,
            max_length=150
        )
        
        self.matricule = discord.ui.TextInput(
            label="Student ID (numbers only)",
            placeholder="Enter your student ID number...",
            required=True,
            max_length=20
        )
        
        # Add all fields to modal
        self.add_item(self.nom)
        self.add_item(self.prenom)
        self.add_item(self.photo)
        self.add_item(self.annee_specialite)
        self.add_item(self.matricule)

    async def on_submit(self, interaction: discord.Interaction):
        # Check registration eligibility
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
        
        # Real-time validation with specific error messages
        errors = []
        
        # Validate required fields
        if not self.nom.value.strip():
            errors.append("Last Name cannot be empty")
        if not self.prenom.value.strip():
            errors.append("First Name cannot be empty")
        if not self.annee_specialite.value.strip():
            errors.append("Year + Field of Study cannot be empty")
        
        # Validate photo URL
        if not self.photo.value.strip():
            errors.append("Photo URL cannot be empty")
        
        # Validate student ID with detailed feedback
        if not self.matricule.value.strip():
            errors.append("Student ID cannot be empty")
        elif not self.matricule.value.strip().isdigit():
            errors.append("Student ID must contain only numbers (no letters, spaces, or symbols)")
        elif len(self.matricule.value.strip()) < 5:
            errors.append("Student ID must be at least 5 digits long")
        
        if errors:
            error_msg = "❌ **Please fix these issues:**\n" + "\n".join(f"• {error}" for error in errors)
            error_msg += "\n\n**Please try again with the correct information.**"
            await interaction.response.send_message(error_msg, ephemeral=True)
            return
        
        # Send contact info message
        await interaction.response.send_message(
            "✅ **Basic information validated!** Please provide your contact details:",
            view=ContactInfoView(
                nom=self.nom.value.strip(),
                prenom=self.prenom.value.strip(),
                photo=self.photo.value.strip(),
                annee_specialite=self.annee_specialite.value.strip(),
                matricule=self.matricule.value.strip()
            ),
            ephemeral=True
        )

class ContactInfoView(discord.ui.View):
    def __init__(self, nom, prenom, photo, annee_specialite, matricule):
        super().__init__(timeout=300)  # 5 minute timeout
        
        # Store previous form data
        self.nom = nom
        self.prenom = prenom
        self.photo = photo
        self.annee_specialite = annee_specialite
        self.matricule = matricule

    @discord.ui.button(label="Continue with Contact Info", style=discord.ButtonStyle.primary, emoji="📞")
    async def contact_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        contact_modal = ContactInfoModal(
            nom=self.nom,
            prenom=self.prenom,
            photo=self.photo,
            annee_specialite=self.annee_specialite,
            matricule=self.matricule
        )
        await interaction.response.send_modal(contact_modal)

class ContactInfoModal(discord.ui.Modal):
    def __init__(self, nom, prenom, photo, annee_specialite, matricule):
        super().__init__(title="Contact Information")
        
        # Store previous form data
        self.nom = nom
        self.prenom = prenom
        self.photo = photo
        self.annee_specialite = annee_specialite
        self.matricule = matricule
        
        # Contact info fields with better hints
        self.phone = discord.ui.TextInput(
            label="Phone Number",
            placeholder="0123456789 (no spaces or symbols)",
            required=True,
            max_length=10,
            min_length=10
        )
        
        self.email = discord.ui.TextInput(
            label="Email Address",
            placeholder="your.name@example.com",
            required=True,
            max_length=100
        )
        
        self.add_item(self.phone)
        self.add_item(self.email)

    async def on_submit(self, interaction: discord.Interaction):
        from views import TeamSelectionView  # Import here to avoid circular import
        
        # Check eligibility again
        is_eligible, reason = utils.check_registration_eligibility(interaction.user)
        if not is_eligible:
            await interaction.response.send_message(
                f"❌ **{reason}**",
                ephemeral=True
            )
            return
        
        # Double-check if user is already registered
        if utils.is_user_registered(str(interaction.user.id)):
            await interaction.response.send_message(
                "❌ **Already Registered!**\n"
                "You have already completed your club registration while filling out the form.",
                ephemeral=True
            )
            return
        
        # Real-time validation for contact info
        errors = []
        
        # Validate phone number - must be exactly 10 digits
        phone_clean = re.sub(r'[^\d]', '', self.phone.value)
        if not phone_clean:
            errors.append("Phone number cannot be empty")
        elif len(phone_clean) != 10:
            errors.append("Phone number must be exactly 10 digits long")
        
        # Validate email with detailed feedback
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not self.email.value.strip():
            errors.append("Email address cannot be empty")
        elif not re.match(email_pattern, self.email.value.strip()):
            errors.append("Please enter a valid email address (e.g., name@example.com)")
        elif len(self.email.value.strip()) > 100:
            errors.append("Email address is too long (maximum 100 characters)")
        
        if errors:
            error_msg = "❌ **Please fix these issues:**\n" + "\n".join(f"• {error}" for error in errors)
            error_msg += "\n\n**Please try again with the correct information.**"
            await interaction.response.send_message(error_msg, ephemeral=True)
            return
        
        # Show team selection buttons
        view = TeamSelectionView(
            nom=self.nom,
            prenom=self.prenom,
            photo=self.photo,
            annee_specialite=self.annee_specialite,
            matricule=self.matricule,
            phone=phone_clean,  # Clean phone number
            email=self.email.value.strip(),
            discord_id=str(interaction.user.id)
        )
        
        await interaction.response.send_message(
            "Select your team:",
            view=view,
            ephemeral=True
        )