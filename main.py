import discord
from discord.ext import commands
from discord.ui import Button, View
import os
import io
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Change this to your ticket category name
TICKET_CATEGORY_NAME = "TICKETS"
LOG_CHANNEL_NAME = "ticket-logs"  # channel where transcripts are sent


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


# ------------------------
# Ticket Panel Command
# ------------------------
@bot.slash_command(description="Send the ticket creation panel")
async def ticketpanel(ctx):
    embed = discord.Embed(
        title="🎫 Floh Official Ticket Hub",
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

    await ctx.respond(embed=embed, view=view)


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
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)

        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True),
        }

        # --------- SUPPORT ---------
        if interaction.data["custom_id"] == "support":
            channel_name = f"support-{interaction.user.name}".replace(" ", "-")
            channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
            await channel.send(
                f"{interaction.user.mention} 🎫 Support Ticket has been created! An admin will assist you shortly.",
                view=CloseView()
            )
            await interaction.response.send_message(f"{interaction.user.mention}, your **Support Ticket** has been created: {channel.mention}", ephemeral=True)

        # --------- PURCHASE ---------
        elif interaction.data["custom_id"] == "purchase":
            channel_name = f"purchase-{interaction.user.name}".replace(" ", "-")
            channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
            await channel.send(
                f"{interaction.user.mention} 🛒 Purchase Ticket has been created! Please describe what you’d like to buy.",
                view=CloseView()
            )
            await interaction.response.send_message(f"{interaction.user.mention}, your **Purchase Ticket** has been created: {channel.mention}", ephemeral=True)

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
                timestamp=datetime.utcnow()
            )

            await log_channel.send(embed=embed, file=transcript_file)

            # Wait 5s then delete ticket
            await interaction.channel.send("📌 Transcript saved. This ticket will be deleted in **5 seconds**...")
            await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=5))
            await interaction.channel.delete()


# ------------------------
# Run Bot
# ------------------------
bot.run(os.getenv("DISCORD_TOKEN"))

Code Made by GOOBER
