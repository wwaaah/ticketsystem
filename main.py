import discord
from discord.ext import commands
from discord.ui import Button, View
import os
import io
import json
from datetime import datetime, timedelta, timezone
from flask import Flask
from threading import Thread
import asyncio

# ------------------------
# Flask Server (Keep Alive)
# ------------------------
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is running!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()


# ------------------------
# Discord Bot Setup
# ------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

TICKET_CATEGORY_NAME = "TICKETS"
LOG_CHANNEL_NAME = "ticket-logs"  # where transcripts go
SUPPORT_ROLE_NAME = "Support Team"  # role that sees all tickets


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")


# ------------------------
# Ticket Panel Command
# ------------------------
@bot.tree.command(name="ticketpanel", description="Send the ticket creation panel")
async def ticketpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Ramirez Official Ticket Hub",
        description="Need assistance or looking to make a purchase?\n\n"
                    "📕 **Support Ticket** - For bot issues, bugs, questions.\n"
                    "🛒 **Purchase Ticket** - For purchases, pricing, or custom items.\n\n"
                    "Click a button below to create your ticket.",
        color=discord.Color.blurple()
    )

    support_btn = Button(label="📕 Support", style=discord.ButtonStyle.danger, custom_id="support")
    purchase_btn = Button(label="🛒 Purchase", style=discord.ButtonStyle.success, custom_id="purchase")

    view = View()
    view.add_item(support_btn)
    view.add_item(purchase_btn)

    await interaction.response.send_message(embed=embed, view=view)


# ------------------------
# Giveaway System
# ------------------------
import random

active_giveaways = {}  # Store active giveaways

class GiveawayView(View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.add_item(Button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.primary, custom_id=f"enter_giveaway_{giveaway_id}"))

@bot.tree.command(name="embed", description="Create a custom embed message")
async def embed_command(
    interaction: discord.Interaction,
    title: str,
    description: str,
    image_url: str = None,
    color: str = "blurple"
):
    # Color mapping
    color_map = {
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "blue": discord.Color.blue(),
        "yellow": discord.Color.yellow(),
        "orange": discord.Color.orange(),
        "purple": discord.Color.purple(),
        "blurple": discord.Color.blurple(),
        "gold": discord.Color.gold(),
        "dark_red": discord.Color.dark_red(),
        "dark_green": discord.Color.dark_green(),
        "dark_blue": discord.Color.dark_blue(),
        "dark_purple": discord.Color.dark_purple(),
        "dark_gold": discord.Color.dark_gold(),
        "teal": discord.Color.teal(),
        "dark_teal": discord.Color.dark_teal(),
        "magenta": discord.Color.magenta(),
        "dark_magenta": discord.Color.dark_magenta()
    }
    
    # Get the color, default to blurple if invalid
    embed_color = color_map.get(color.lower(), discord.Color.blurple())
    
    # Create the embed
    embed = discord.Embed(
        title=title,
        description=description,
        color=embed_color,
        timestamp=datetime.now(timezone.utc)
    )
    
    # Add image if provided
    if image_url:
        try:
            embed.set_image(url=image_url)
        except:
            await interaction.response.send_message("❌ Invalid image URL provided!", ephemeral=True)
            return
    
    # Add footer with author info
    embed.set_footer(text=f"Created by {interaction.user.display_name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    
    try:
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to create embed: {str(e)}", ephemeral=True)

@bot.tree.command(name="giveaway", description="Create a giveaway")
async def giveaway(
    interaction: discord.Interaction,
    title: str,
    description: str,
    duration_minutes: int,
    winners: int = 1
):
    if winners < 1:
        await interaction.response.send_message("❌ Number of winners must be at least 1!", ephemeral=True)
        return
    
    if duration_minutes < 1:
        await interaction.response.send_message("❌ Duration must be at least 1 minute!", ephemeral=True)
        return

    giveaway_id = f"{interaction.guild.id}_{int(datetime.now(timezone.utc).timestamp())}"
    end_time = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
    
    embed = discord.Embed(
        title=f"🎉 {title}",
        description=f"{description}\n\n"
                   f"**Winners:** {winners}\n"
                   f"**Duration:** {duration_minutes} minutes\n"
                   f"**Ends:** <t:{int(end_time.timestamp())}:R>\n\n"
                   f"**Participants:** 0",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
    
    view = GiveawayView(giveaway_id)
    
    # Store giveaway data
    active_giveaways[giveaway_id] = {
        "title": title,
        "description": description,
        "winners": winners,
        "end_time": end_time,
        "participants": set(),
        "channel_id": interaction.channel.id,
        "message_id": None,
        "host": interaction.user.id
    }
    
    await interaction.response.send_message(embed=embed, view=view)
    
    # Get the message ID for later editing
    message = await interaction.original_response()
    active_giveaways[giveaway_id]["message_id"] = message.id
    
    # Schedule the giveaway end
    asyncio.create_task(end_giveaway_after_delay(giveaway_id, duration_minutes * 60))

async def end_giveaway_after_delay(giveaway_id: str, delay_seconds: int):
    await asyncio.sleep(delay_seconds)
    await end_giveaway(giveaway_id)

async def end_giveaway(giveaway_id: str):
    if giveaway_id not in active_giveaways:
        return
    
    giveaway = active_giveaways[giveaway_id]
    channel = bot.get_channel(giveaway["channel_id"])
    
    if not channel:
        del active_giveaways[giveaway_id]
        return
    
    participants = list(giveaway["participants"])
    
    try:
        message = await channel.fetch_message(giveaway["message_id"])
    except:
        del active_giveaways[giveaway_id]
        return
    
    if len(participants) == 0:
        # No participants
        embed = discord.Embed(
            title=f"🎉 {giveaway['title']} - ENDED",
            description=f"{giveaway['description']}\n\n"
                       f"**Winners:** {giveaway['winners']}\n"
                       f"**Result:** No participants! 😢",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
        
        await message.edit(embed=embed, view=None)
        await channel.send("🎉 **Giveaway Ended!** No one participated in this giveaway. 😢")
        
    else:
        # Pick winners
        num_winners = min(giveaway["winners"], len(participants))
        winners = random.sample(participants, num_winners)
        
        winner_mentions = [f"<@{winner}>" for winner in winners]
        winner_text = ", ".join(winner_mentions)
        
        embed = discord.Embed(
            title=f"🎉 {giveaway['title']} - ENDED",
            description=f"{giveaway['description']}\n\n"
                       f"**Winners:** {num_winners}\n"
                       f"**🏆 Winner(s):** {winner_text}\n"
                       f"**Total Participants:** {len(participants)}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
        
        await message.edit(embed=embed, view=None)
        
        congratulations_msg = f"🎉 **Giveaway Results!** 🎉\n\n"
        congratulations_msg += f"**{giveaway['title']}** has ended!\n\n"
        congratulations_msg += f"🏆 **Winner(s):** {winner_text}\n\n"
        congratulations_msg += f"Congratulations! 🥳"
        
        await channel.send(congratulations_msg)
    
    # Clean up
    del active_giveaways[giveaway_id]

@bot.tree.command(name="reroll", description="Reroll winners for a giveaway")
async def reroll_giveaway(
    interaction: discord.Interaction,
    giveaway_id: str
):
    # Check if the giveaway exists in our records (we'll need to modify this to keep ended giveaways)
    # For now, let's find the giveaway message by ID
    try:
        # Try to find the giveaway message in the current channel
        messages = []
        async for message in interaction.channel.history(limit=100):
            if message.author == bot.user and message.embeds:
                embed = message.embeds[0]
                if embed.footer and giveaway_id in embed.footer.text:
                    messages.append(message)
        
        if not messages:
            await interaction.response.send_message("❌ Giveaway not found! Make sure you're in the correct channel and using the right giveaway ID.", ephemeral=True)
            return
        
        giveaway_message = messages[0]
        embed = giveaway_message.embeds[0]
        
        # Check if giveaway has ended
        if "ENDED" not in embed.title:
            await interaction.response.send_message("❌ This giveaway hasn't ended yet! You can only reroll ended giveaways.", ephemeral=True)
            return
        
        # Get reactions from the original giveaway message to find participants
        participants = []
        if giveaway_message.reactions:
            for reaction in giveaway_message.reactions:
                if str(reaction.emoji) == "🎉":
                    async for user in reaction.users():
                        if not user.bot:
                            participants.append(user.id)
        
        # If no reactions, try to extract from button interactions (this is a fallback)
        if not participants:
            await interaction.response.send_message("❌ No participants found for this giveaway! The original participants data may have been lost.", ephemeral=True)
            return
        
        # Extract number of winners from the embed
        description_lines = embed.description.split('\n')
        winners_count = 1
        for line in description_lines:
            if "**Winners:**" in line:
                try:
                    winners_count = int(line.split("**Winners:**")[1].strip().split()[0])
                except:
                    winners_count = 1
                break
        
        # Pick new winners
        num_winners = min(winners_count, len(participants))
        new_winners = random.sample(participants, num_winners)
        
        winner_mentions = [f"<@{winner}>" for winner in new_winners]
        winner_text = ", ".join(winner_mentions)
        
        # Extract original title
        original_title = embed.title.replace(" - ENDED", "")
        
        # Update the embed
        new_embed = discord.Embed(
            title=f"{original_title} - REROLLED",
            description=f"{embed.description.split('**🏆 Winner(s):**')[0]}**🏆 New Winner(s):** {winner_text}\n"
                       f"**Total Participants:** {len(participants)}\n\n"
                       f"🔄 **Rerolled by:** {interaction.user.mention}",
            color=discord.Color.purple()
        )
        new_embed.set_footer(text=embed.footer.text)
        
        await giveaway_message.edit(embed=new_embed)
        
        # Send reroll announcement
        reroll_msg = f"🔄 **Giveaway Rerolled!** 🔄\n\n"
        reroll_msg += f"**{original_title.replace('🎉 ', '')}** has been rerolled by {interaction.user.mention}!\n\n"
        reroll_msg += f"🏆 **New Winner(s):** {winner_text}\n\n"
        reroll_msg += f"Congratulations to the new winners! 🥳"
        
        await interaction.response.send_message(reroll_msg)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error rerolling giveaway: {str(e)}", ephemeral=True)


# ------------------------
# Close Ticket Button
# ------------------------
class CloseView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="🔒 Close Ticket", style=discord.ButtonStyle.secondary, custom_id="close_ticket"))


# ------------------------
# Handle Button Interactions
# ------------------------
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        guild = interaction.guild

        # Find or create ticket category
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False)
            }
            support_role = discord.utils.get(guild.roles, name=SUPPORT_ROLE_NAME)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

            category = await guild.create_category(TICKET_CATEGORY_NAME, overwrites=overwrites)

        # --------- SUPPORT ---------
        if interaction.data["custom_id"] == "support":
            channel_name = f"support-{interaction.user.name}".replace(" ", "-")
            channel = await guild.create_text_channel(channel_name, category=category)
            await channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
            await channel.set_permissions(guild.me, view_channel=True)
            await channel.send(
                f"{interaction.user.mention} 🎫 Support Ticket has been created! An admin will assist you shortly.",
                view=CloseView()
            )
            await interaction.response.send_message(f"{interaction.user.mention}, your **Support Ticket** has been created: {channel.mention}", ephemeral=True)

        # --------- PURCHASE ---------
        elif interaction.data["custom_id"] == "purchase":
            channel_name = f"purchase-{interaction.user.name}".replace(" ", "-")
            channel = await guild.create_text_channel(channel_name, category=category)
            await channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
            await channel.set_permissions(guild.me, view_channel=True)
            await channel.send(
                f"{interaction.user.mention} 🛒 Purchase Ticket has been created! Please describe what you’d like to buy.",
                view=CloseView()
            )
            await interaction.response.send_message(f"{interaction.user.mention}, your **Purchase Ticket** has been created: {channel.mention}", ephemeral=True)

        # --------- GIVEAWAY ENTRY ---------
        elif interaction.data["custom_id"].startswith("enter_giveaway_"):
            giveaway_id = interaction.data["custom_id"].replace("enter_giveaway_", "")
            
            if giveaway_id not in active_giveaways:
                await interaction.response.send_message("❌ This giveaway has ended or doesn't exist!", ephemeral=True)
                return
            
            giveaway = active_giveaways[giveaway_id]
            user_id = interaction.user.id
            
            # Check if giveaway has ended
            if datetime.now(timezone.utc) >= giveaway["end_time"]:
                await interaction.response.send_message("❌ This giveaway has already ended!", ephemeral=True)
                return
            
            # Check if user is already participating
            if user_id in giveaway["participants"]:
                await interaction.response.send_message("❌ You're already participating in this giveaway!", ephemeral=True)
                return
            
            # Add user to participants
            giveaway["participants"].add(user_id)
            
            # Update the embed with new participant count
            embed = discord.Embed(
                title=f"🎉 {giveaway['title']}",
                description=f"{giveaway['description']}\n\n"
                           f"**Winners:** {giveaway['winners']}\n"
                           f"**Ends:** <t:{int(giveaway['end_time'].timestamp())}:R>\n\n"
                           f"**Participants:** {len(giveaway['participants'])}",
                color=discord.Color.gold()
            )
            embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
            
            try:
                await interaction.response.edit_message(embed=embed)
                await interaction.followup.send("✅ You've successfully entered the giveaway! Good luck! 🍀", ephemeral=True)
            except:
                await interaction.response.send_message("✅ You've successfully entered the giveaway! Good luck! 🍀", ephemeral=True)

        # --------- CLOSE TICKET ---------
        elif interaction.data["custom_id"] == "close_ticket":
            await interaction.response.send_message("🔒 Closing ticket in 5 seconds...", ephemeral=True)

            # Collect transcript
            transcript = ""
            async for msg in interaction.channel.history(limit=None, oldest_first=True):
                time = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                transcript += f"[{time}] {msg.author}: {msg.content}\n"

            if not transcript.strip():
                transcript = "No messages were sent in this ticket."

            transcript_file = discord.File(
                io.BytesIO(transcript.encode()),
                filename=f"transcript-{interaction.channel.name}.txt"
            )

            # Find or create logs channel
            log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
            if log_channel is None:
                log_channel = await guild.create_text_channel(LOG_CHANNEL_NAME)

            embed = discord.Embed(
                title="📑 Ticket Closed",
                description=f"Ticket `{interaction.channel.name}` closed by {interaction.user.mention}",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )

            await log_channel.send(embed=embed, file=transcript_file)

            # Wait 5s then delete ticket
            await interaction.channel.send("📌 Transcript saved. This ticket will be deleted in **5 seconds**...")
            await asyncio.sleep(5)
            await interaction.channel.delete()

# ========== WELCOMER SYSTEM ==========
WELCOME_FILE = "welcomer_settings.json"

# Load saved settings
def load_welcomer():
    if os.path.exists(WELCOME_FILE):
        with open(WELCOME_FILE, "r") as f:
            return json.load(f)
    return {"welcome": {}, "leave": {}, "custom": {}}

# Save settings
def save_welcomer(data):
    with open(WELCOME_FILE, "w") as f:
        json.dump(data, f, indent=4)

welcomer_data = load_welcomer()

# Helper: format placeholders
def format_text(text: str, member: discord.Member):
    return (
        text.replace("{user}", member.mention)
            .replace("{user_name}", member.name)
            .replace("{server}", member.guild.name)
            .replace("{member_count}", str(member.guild.member_count))
    )

# --- Slash Commands ---

@bot.tree.command(name="welcomer_set", description="Set the welcome channel")
async def welcomer_set(interaction: discord.Interaction, channel: discord.TextChannel):
    welcomer_data["welcome"][str(interaction.guild.id)] = channel.id
    save_welcomer(welcomer_data)
    await interaction.response.send_message(f"✅ Welcome channel set to {channel.mention}")

@bot.tree.command(name="leave_set", description="Set the leave channel")
async def leave_set(interaction: discord.Interaction, channel: discord.TextChannel):
    welcomer_data["leave"][str(interaction.guild.id)] = channel.id
    save_welcomer(welcomer_data)
    await interaction.response.send_message(f"✅ Leave channel set to {channel.mention}")

@bot.tree.command(name="customize", description="Customize welcome/leave messages")
async def customize(
    interaction: discord.Interaction,
    target: str,
    title: str,
    description: str,
    image_url: str = None
):
    if target.lower() not in ["welcome", "leave"]:
        await interaction.response.send_message("❌ Please choose either 'welcome' or 'leave'", ephemeral=True)
        return

    gid = str(interaction.guild.id)
    if gid not in welcomer_data["custom"]:
        welcomer_data["custom"][gid] = {}

    welcomer_data["custom"][gid][target.lower()] = {
        "title": title,
        "description": description,
        "image": image_url or None
    }
    save_welcomer(welcomer_data)
    await interaction.response.send_message(f"✅ Customized {target.lower()} embed successfully!\n\n📌 Placeholders you can use:\n`{user}`, `{user_name}`, `{server}`, `{member_count}`")

# --- Events ---

@bot.event
async def on_member_join(member: discord.Member):
    gid = str(member.guild.id)
    if gid in welcomer_data["welcome"]:
        channel = member.guild.get_channel(welcomer_data["welcome"][gid])
        if channel:
            settings = welcomer_data["custom"].get(gid, {}).get("welcome", {})
            embed = discord.Embed(
                title=format_text(settings.get("title", "🎉 Welcome to {server}!"), member),
                description=format_text(settings.get("description", "Hey {user}, glad to have you here! You are member #{member_count}."), member),
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            if settings.get("image"):
                embed.set_image(url=settings["image"])
            await channel.send(embed=embed)

@bot.event
async def on_member_remove(member: discord.Member):
    gid = str(member.guild.id)
    if gid in welcomer_data["leave"]:
        channel = member.guild.get_channel(welcomer_data["leave"][gid])
        if channel:
            settings = welcomer_data["custom"].get(gid, {}).get("leave", {})
            embed = discord.Embed(
                title=format_text(settings.get("title", "👋 Goodbye from {server}"), member),
                description=format_text(settings.get("description", "{user_name} has left the server. We now have {member_count} members."), member),
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            if settings.get("image"):
                embed.set_image(url=settings["image"])
            await channel.send(embed=embed)

# Sync commands to Discord on ready
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Synced slash commands as {bot.user}")


# ------------------------
# Keep Alive + Run Bot
# ------------------------
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
