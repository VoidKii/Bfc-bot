import os
import json
import random
import asyncio
import urllib.request
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


# ============================================================
# BFC BOT — VERSION 1.1
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from your .env file.")


# ============================================================
# CONFIG
# ============================================================

BOT_NAME = "BFC Bot"
BOT_VERSION = "1.1"

DEFAULT_COLOR = 0x5865F2
SUCCESS_COLOR = 0x57F287
ERROR_COLOR = 0xED4245
WARNING_COLOR = 0xFEE75C

DATA_FILE = "bfc_data.json"


# ============================================================
# DATA
# ============================================================

def default_data():
    return {
        "warnings": {},
        "profiles": {},
        "bounties": {},
        "giveaways": {}
    }


def load_data():
    if not os.path.exists(DATA_FILE):
        return default_data()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            loaded = json.load(file)

        for key, value in default_data().items():
            if key not in loaded:
                loaded[key] = value

        return loaded

    except Exception:
        return default_data()


data = load_data()


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)


# ============================================================
# HELPERS
# ============================================================

def make_embed(
    title=None,
    description=None,
    color=DEFAULT_COLOR,
    footer=True
):
    e = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    if footer:
        e.set_footer(text=f"{BOT_NAME} • BFC")

    return e


def is_staff(interaction: discord.Interaction):
    if not interaction.guild:
        return False

    permissions = interaction.user.guild_permissions

    return (
        permissions.administrator
        or permissions.manage_guild
        or permissions.moderate_members
    )


async def staff_check(interaction: discord.Interaction):
    if not is_staff(interaction):
        await interaction.response.send_message(
            embed=make_embed(
                "❌ Permission Denied",
                "You need Staff permissions to use this command.",
                ERROR_COLOR
            ),
            ephemeral=True
        )
        return False

    return True


def user_key(guild_id, user_id):
    return f"{guild_id}:{user_id}"


def parse_color(color: str):
    try:
        color = color.replace("#", "").strip()

        if len(color) != 6:
            return None

        return int(color, 16)

    except ValueError:
        return None


# ============================================================
# BOT READY
# ============================================================

@bot.event
async def on_ready():

    print("=" * 50)
    print(f"{BOT_NAME} is online!")
    print(f"Logged in as: {bot.user}")
    print(f"Servers: {len(bot.guilds)}")
    print("=" * 50)

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")

    except Exception as error:
        print(f"Command sync error: {error}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="BFC Community"
        )
    )


# ============================================================
# /PING
# ============================================================

@bot.tree.command(name="ping", description="Check BFC Bot latency.")
async def ping(interaction: discord.Interaction):

    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        embed=make_embed(
            "🏓 Pong!",
            f"**Latency:** `{latency}ms`\n"
            "🟢 **BFC Bot is online**",
            SUCCESS_COLOR
        )
    )


# ============================================================
# /HELP
# ============================================================

@bot.tree.command(name="help", description="Show all BFC Bot commands.")
async def help_command(interaction: discord.Interaction):

    e = make_embed(
        "🏴 BFC Bot",
        "**Blox Fruits Community Command Center**\n\n"
        "### ⚙️ Utility\n"
        "`/ping` • `/help` • `/serverinfo` • `/userinfo` • `/avatar`\n\n"
        "### 🛡️ Moderation\n"
        "`/ban` • `/kick` • `/timeout` • `/warn` • `/warnings`\n"
        "`/clear` • `/lock` • `/unlock`\n\n"
        "### 📢 Server Tools\n"
        "`/embed` • `/announce` • `/say`\n\n"
        "### 🎉 Community\n"
        "`/giveaway`\n\n"
        "### 🏴 BFC\n"
        "`/profile` • `/setprofile` • `/bounty` • `/verify`",
        DEFAULT_COLOR
    )

    e.add_field(
        name="🤖 Version",
        value=f"`{BOT_NAME} v{BOT_VERSION}`",
        inline=False
    )

    await interaction.response.send_message(
        embed=e,
        ephemeral=True
    )


# ============================================================
# /SERVERINFO
# ============================================================

@bot.tree.command(
    name="serverinfo",
    description="Show information about this server."
)
async def serverinfo(interaction: discord.Interaction):

    guild = interaction.guild

    if not guild:
        return await interaction.response.send_message(
            "This command can only be used inside a server.",
            ephemeral=True
        )

    e = make_embed(
        f"🏴 {guild.name}",
        f"**Owner:** {guild.owner.mention if guild.owner else 'Unknown'}"
    )

    e.add_field(
        name="👥 Members",
        value=str(guild.member_count),
        inline=True
    )

    e.add_field(
        name="💬 Channels",
        value=str(len(guild.channels)),
        inline=True
    )

    e.add_field(
        name="🎭 Roles",
        value=str(len(guild.roles)),
        inline=True
    )

    e.add_field(
        name="🆔 Server ID",
        value=f"`{guild.id}`",
        inline=False
    )

    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)

    await interaction.response.send_message(embed=e)


# ============================================================
# /USERINFO
# ============================================================

@bot.tree.command(
    name="userinfo",
    description="Show information about a member."
)
@app_commands.describe(member="The member to inspect.")
async def userinfo(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = member or interaction.user

    roles = [
        role.mention
        for role in member.roles[1:]
    ]

    roles_text = ", ".join(roles)

    if not roles_text:
        roles_text = "None"

    if len(roles_text) > 1000:
        roles_text = roles_text[:1000] + "..."

    e = make_embed(
        f"👤 {member.display_name}",
        f"**Username:** `{member}`\n"
        f"**ID:** `{member.id}`\n"
        f"**Mention:** {member.mention}"
    )

    if member.joined_at:
        e.add_field(
            name="📅 Joined Server",
            value=discord.utils.format_dt(member.joined_at, "R"),
            inline=False
        )

    e.add_field(
        name="🎭 Roles",
        value=roles_text,
        inline=False
    )

    e.set_thumbnail(url=member.display_avatar.url)

    await interaction.response.send_message(embed=e)


# ============================================================
# /AVATAR
# ============================================================

@bot.tree.command(
    name="avatar",
    description="Show a member's avatar."
)
@app_commands.describe(member="The member whose avatar you want.")
async def avatar(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = member or interaction.user

    e = make_embed(
        f"🖼️ {member.display_name}'s Avatar",
        f"[Open Avatar]({member.display_avatar.url})"
    )

    e.set_image(url=member.display_avatar.url)

    await interaction.response.send_message(embed=e)


# ============================================================
# /EMBED
# ============================================================

@bot.tree.command(
    name="embed",
    description="Create and send a custom embed as BFC Bot."
)
@app_commands.describe(
    title="Embed title",
    description="Embed description",
    color="Hex color, example: 5865F2",
    image_url="Optional large image URL",
    image_upload="Upload a large image directly",
    thumbnail_url="Optional thumbnail URL",
    thumbnail_upload="Upload a thumbnail directly",
    footer="Footer text",
    author="Author text",
    channel="Channel where the embed will be sent"
)
async def embed_command(
    interaction: discord.Interaction,
    title: str,
    description: str,
    color: str = "5865F2",
    image_url: str = None,
    image_upload: discord.Attachment = None,
    thumbnail_url: str = None,
    thumbnail_upload: discord.Attachment = None,
    footer: str = None,
    author: str = None,
    channel: discord.TextChannel = None
):

    if not await staff_check(interaction):
        return

    color_value = parse_color(color)

    if color_value is None:
        return await interaction.response.send_message(
            embed=make_embed(
                "❌ Invalid Color",
                "Use a 6-character hex color.\nExample: `5865F2` or `#5865F2`.",
                ERROR_COLOR
            ),
            ephemeral=True
        )

    channel = channel or interaction.channel

    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Please select a normal text channel.",
            ephemeral=True
        )

    e = discord.Embed(
        title=title,
        description=description,
        color=color_value,
        timestamp=datetime.now(timezone.utc)
    )

    # MAIN IMAGE
    if image_upload:
        e.set_image(url=image_upload.url)

    elif image_url:
        e.set_image(url=image_url)

    # THUMBNAIL
    if thumbnail_upload:
        e.set_thumbnail(url=thumbnail_upload.url)

    elif thumbnail_url:
        e.set_thumbnail(url=thumbnail_url)

    # FOOTER
    if footer:
        e.set_footer(text=footer)
    else:
        e.set_footer(text=f"{BOT_NAME} • BFC")

    # AUTHOR
    if author:
        e.set_author(name=author)

    try:

        await channel.send(embed=e)

        await interaction.response.send_message(
            embed=make_embed(
                "✅ Embed Sent",
                f"BFC Bot sent your embed to {channel.mention}.",
                SUCCESS_COLOR
            ),
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            embed=make_embed(
                "❌ Missing Permissions",
                "I cannot send messages or embeds in that channel.",
                ERROR_COLOR
            ),
            ephemeral=True
        )


# ============================================================
# /ANNOUNCE
# ============================================================

@bot.tree.command(
    name="announce",
    description="Send an announcement as BFC Bot."
)
@app_commands.describe(
    title="Announcement title",
    message="Announcement message",
    channel="Channel where it will be sent"
)
async def announce(
    interaction: discord.Interaction,
    title: str,
    message: str,
    channel: discord.TextChannel = None
):

    if not await staff_check(interaction):
        return

    channel = channel or interaction.channel

    e = make_embed(
        f"📢 {title}",
        message
    )

    e.set_author(name=f"{BOT_NAME} • Announcement")

    try:
        await channel.send(embed=e)

        await interaction.response.send_message(
            "✅ Announcement sent!",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot send messages there.",
            ephemeral=True
        )


# ============================================================
# /SAY
# ============================================================

@bot.tree.command(
    name="say",
    description="Send a normal message as BFC Bot."
)
@app_commands.describe(
    message="Message to send",
    channel="Channel where it will be sent"
)
async def say(
    interaction: discord.Interaction,
    message: str,
    channel: discord.TextChannel = None
):

    if not await staff_check(interaction):
        return

    channel = channel or interaction.channel

    try:

        await channel.send(message)

        await interaction.response.send_message(
            "✅ Message sent!",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot send messages there.",
            ephemeral=True
        )


# ============================================================
# /BAN
# ============================================================

@bot.tree.command(
    name="ban",
    description="Ban a member."
)
@app_commands.describe(
    member="Member to ban",
    reason="Reason for the ban"
)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided."
):

    if not await staff_check(interaction):
        return

    if member == interaction.user:
        return await interaction.response.send_message(
            "❌ You cannot ban yourself.",
            ephemeral=True
        )

    try:

        await member.ban(reason=reason)

        await interaction.response.send_message(
            embed=make_embed(
                "🔨 Member Banned",
                f"**Member:** {member.mention}\n"
                f"**Reason:** {reason}\n"
                f"**Moderator:** {interaction.user.mention}",
                SUCCESS_COLOR
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot ban that member. Check my role position and permissions.",
            ephemeral=True
        )


# ============================================================
# /KICK
# ============================================================

@bot.tree.command(
    name="kick",
    description="Kick a member."
)
@app_commands.describe(
    member="Member to kick",
    reason="Reason for the kick"
)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided."
):

    if not await staff_check(interaction):
        return

    if member == interaction.user:
        return await interaction.response.send_message(
            "❌ You cannot kick yourself.",
            ephemeral=True
        )

    try:

        await member.kick(reason=reason)

        await interaction.response.send_message(
            embed=make_embed(
                "👢 Member Kicked",
                f"**Member:** {member.mention}\n"
                f"**Reason:** {reason}\n"
                f"**Moderator:** {interaction.user.mention}",
                SUCCESS_COLOR
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot kick that member.",
            ephemeral=True
        )


# ============================================================
# /TIMEOUT
# ============================================================

@bot.tree.command(
    name="timeout",
    description="Timeout a member."
)
@app_commands.describe(
    member="Member to timeout",
    minutes="Timeout duration in minutes",
    reason="Reason"
)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: int,
    reason: str = "No reason provided."
):

    if not await staff_check(interaction):
        return

    if minutes < 1 or minutes > 40320:
        return await interaction.response.send_message(
            "❌ Duration must be between 1 minute and 28 days.",
            ephemeral=True
        )

    until = discord.utils.utcnow() + timedelta(minutes=minutes)

    try:

        await member.timeout(
            until,
            reason=reason
        )

        await interaction.response.send_message(
            embed=make_embed(
                "⏳ Member Timed Out",
                f"**Member:** {member.mention}\n"
                f"**Duration:** `{minutes}` minutes\n"
                f"**Reason:** {reason}",
                SUCCESS_COLOR
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot timeout that member.",
            ephemeral=True
        )


# ============================================================
# /WARN
# ============================================================

@bot.tree.command(
    name="warn",
    description="Warn a member."
)
@app_commands.describe(
    member="Member to warn",
    reason="Reason for the warning"
)
async def warn(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str
):

    if not await staff_check(interaction):
        return

    key = user_key(interaction.guild.id, member.id)

    data["warnings"].setdefault(key, [])

    data["warnings"][key].append({
        "reason": reason,
        "moderator": interaction.user.id,
        "time": datetime.now(timezone.utc).isoformat()
    })

    save_data()

    warning_count = len(data["warnings"][key])

    await interaction.response.send_message(
        embed=make_embed(
            "⚠️ Member Warned",
            f"**Member:** {member.mention}\n"
            f"**Reason:** {reason}\n"
            f"**Total Warnings:** `{warning_count}`",
            WARNING_COLOR
        )
    )


# ============================================================
# /WARNINGS
# ============================================================

@bot.tree.command(
    name="warnings",
    description="View a member's warnings."
)
@app_commands.describe(member="Member to check")
async def warnings(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not await staff_check(interaction):
        return

    key = user_key(interaction.guild.id, member.id)

    warning_list = data["warnings"].get(key, [])

    if not warning_list:
        return await interaction.response.send_message(
            embed=make_embed(
                "📋 Warnings",
                f"{member.mention} has no warnings.",
                SUCCESS_COLOR
            )
        )

    lines = []

    for index, warning in enumerate(warning_list, start=1):

        lines.append(
            f"**{index}.** {warning['reason']}"
        )

    description = "\n".join(lines)

    if len(description) > 4000:
        description = description[:4000] + "\n..."

    e = make_embed(
        f"📋 Warnings • {member.display_name}",
        description,
        WARNING_COLOR
    )

    e.add_field(
        name="Total Warnings",
        value=str(len(warning_list)),
        inline=False
    )

    await interaction.response.send_message(embed=e)


# ============================================================
# /CLEAR
# ============================================================

@bot.tree.command(
    name="clear",
    description="Delete messages from this channel."
)
@app_commands.describe(amount="Number of messages to delete")
async def clear(
    interaction: discord.Interaction,
    amount: int
):

    if not await staff_check(interaction):
        return

    if amount < 1 or amount > 100:
        return await interaction.response.send_message(
            "❌ Choose an amount between 1 and 100.",
            ephemeral=True
        )

    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ This command only works in normal text channels.",
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    deleted = await interaction.channel.purge(limit=amount)

    await interaction.followup.send(
        f"🧹 Deleted `{len(deleted)}` messages.",
        ephemeral=True
    )


# ============================================================
# /LOCK
# ============================================================

@bot.tree.command(
    name="lock",
    description="Lock the current channel."
)
async def lock(interaction: discord.Interaction):

    if not await staff_check(interaction):
        return

    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ This command only works in normal text channels.",
            ephemeral=True
        )

    overwrite = interaction.channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = False

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    await interaction.response.send_message(
        embed=make_embed(
            "🔒 Channel Locked",
            f"{interaction.channel.mention} is now locked.",
            WARNING_COLOR
        )
    )


# ============================================================
# /UNLOCK
# ============================================================

@bot.tree.command(
    name="unlock",
    description="Unlock the current channel."
)
async def unlock(interaction: discord.Interaction):

    if not await staff_check(interaction):
        return

    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ This command only works in normal text channels.",
            ephemeral=True
        )

    overwrite = interaction.channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = None

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    await interaction.response.send_message(
        embed=make_embed(
            "🔓 Channel Unlocked",
            f"{interaction.channel.mention} is now unlocked.",
            SUCCESS_COLOR
        )
    )


# ============================================================
# /PROFILE
# ============================================================

@bot.tree.command(
    name="profile",
    description="View a BFC member profile."
)
@app_commands.describe(member="Member whose profile you want")
async def profile(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = member or interaction.user

    key = user_key(interaction.guild.id, member.id)

    profile_data = data["profiles"].get(key, {})

    roblox = profile_data.get("roblox", "Not set")
    fruit = profile_data.get("fruit", "Not set")
    note = profile_data.get("note", "No profile description.")

    bounty_amount = data["bounties"].get(key, 0)

    e = make_embed(
        f"🏴 {member.display_name}'s BFC Profile",
        note
    )

    e.set_thumbnail(url=member.display_avatar.url)

    e.add_field(
        name="🎮 Roblox",
        value=roblox,
        inline=True
    )

    e.add_field(
        name="🍎 Main Fruit",
        value=fruit,
        inline=True
    )

    e.add_field(
        name="💰 Bounty",
        value=f"`{bounty_amount:,}`",
        inline=True
    )

    await interaction.response.send_message(embed=e)


# ============================================================
# /SETPROFILE
# ============================================================

@bot.tree.command(
    name="setprofile",
    description="Set your BFC profile."
)
@app_commands.describe(
    roblox="Your Roblox username",
    fruit="Your main Blox Fruit",
    note="Short description"
)
async def setprofile(
    interaction: discord.Interaction,
    roblox: str,
    fruit: str,
    note: str
):

    key = user_key(
        interaction.guild.id,
        interaction.user.id
    )

    data["profiles"][key] = {
        "roblox": roblox,
        "fruit": fruit,
        "note": note
    }

    save_data()

    await interaction.response.send_message(
        embed=make_embed(
            "✅ Profile Updated",
            "Your BFC profile has been saved.",
            SUCCESS_COLOR
        ),
        ephemeral=True
    )


# ============================================================
# /BOUNTY
# ============================================================

@bot.tree.command(
    name="bounty",
    description="View or set a BFC bounty."
)
@app_commands.describe(
    member="Member to view or update",
    amount="New bounty amount (Staff only)"
)
async def bounty(
    interaction: discord.Interaction,
    member: discord.Member = None,
    amount: int = None
):

    member = member or interaction.user

    key = user_key(
        interaction.guild.id,
        member.id
    )

    if amount is not None:

        if not await staff_check(interaction):
            return

        if amount < 0:
            return await interaction.response.send_message(
                "❌ Bounty cannot be negative.",
                ephemeral=True
            )

        data["bounties"][key] = amount

        save_data()

        return await interaction.response.send_message(
            embed=make_embed(
                "💰 Bounty Updated",
                f"**Player:** {member.mention}\n"
                f"**Bounty:** `{amount:,}`",
                SUCCESS_COLOR
            )
        )

    current_bounty = data["bounties"].get(key, 0)

    await interaction.response.send_message(
        embed=make_embed(
            "🏴 BFC Bounty",
            f"**Player:** {member.mention}\n"
            f"**Bounty:** `{current_bounty:,}`"
        )
    )


# ============================================================
# ROBLOX LOOKUP
# ============================================================

def roblox_lookup(username):

    url = "https://users.roblox.com/v1/usernames/users"

    body = json.dumps({
        "usernames": [username],
        "excludeBannedUsers": False
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "BFC-Bot"
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=10
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

        if not result.get("data"):
            return None

        return result["data"][0]

    except Exception as error:

        print(f"Roblox lookup error: {error}")
        return None


# ============================================================
# /VERIFY
# ============================================================

@bot.tree.command(
    name="verify",
    description="Verify your Roblox account."
)
@app_commands.describe(
    username="Your Roblox username"
)
async def verify(
    interaction: discord.Interaction,
    username: str
):

    await interaction.response.defer(
        ephemeral=True
    )

    roblox_user = await asyncio.to_thread(
        roblox_lookup,
        username
    )

    if not roblox_user:

        return await interaction.followup.send(
            embed=make_embed(
                "❌ Roblox User Not Found",
                f"I couldn't find a Roblox account named `{username}`.",
                ERROR_COLOR
            ),
            ephemeral=True
        )

    actual_name = roblox_user["name"]
    display_name = roblox_user.get(
        "displayName",
        actual_name
    )
    roblox_id = roblox_user["id"]

    verified_role = discord.utils.find(
        lambda role: role.name.lower() == "verified",
        interaction.guild.roles
    )

    role_text = "No Verified role is configured."

    if verified_role:

        try:

            await interaction.user.add_roles(
                verified_role,
                reason="BFC Roblox verification"
            )

            role_text = f"Role assigned: {verified_role.mention}"

        except discord.Forbidden:

            role_text = (
                "The Verified role exists, but I cannot assign it."
            )

    key = user_key(
        interaction.guild.id,
        interaction.user.id
    )

    data["profiles"].setdefault(key, {})

    data["profiles"][key]["roblox"] = actual_name

    save_data()

    await interaction.followup.send(
        embed=make_embed(
            "✅ Roblox Verified",
            f"**Username:** `{actual_name}`\n"
            f"**Display Name:** `{display_name}`\n"
            f"**Roblox ID:** `{roblox_id}`\n\n"
            f"{role_text}",
            SUCCESS_COLOR
        ),
        ephemeral=True
    )


# ============================================================
# GIVEAWAY BUTTON
# ============================================================

class GiveawayView(discord.ui.View):

    def __init__(self, message_id):
        super().__init__(timeout=None)

        self.message_id = message_id

    @discord.ui.button(
        label="Enter Giveaway",
        emoji="🎉",
        style=discord.ButtonStyle.primary,
        custom_id="bfc_giveaway_enter"
    )
    async def enter(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        giveaway = data["giveaways"].get(
            str(self.message_id)
        )

        if not giveaway:

            return await interaction.response.send_message(
                "❌ This giveaway no longer exists.",
                ephemeral=True
            )

        if giveaway.get("ended"):

            return await interaction.response.send_message(
                "❌ This giveaway has already ended.",
                ephemeral=True
            )

        if interaction.user.id in giveaway["entries"]:

            return await interaction.response.send_message(
                "You are already entered! 🎉",
                ephemeral=True
            )

        giveaway["entries"].append(
            interaction.user.id
        )

        save_data()

        await interaction.response.send_message(
            "🎉 You have entered the giveaway!",
            ephemeral=True
        )


# ============================================================
# END GIVEAWAY
# ============================================================

async def finish_giveaway(message_id):

    giveaway = data["giveaways"].get(
        str(message_id)
    )

    if not giveaway:
        return

    if giveaway.get("ended"):
        return

    giveaway["ended"] = True

    save_data()

    channel = bot.get_channel(
        giveaway["channel_id"]
    )

    if not channel:
        return

    try:

        message = await channel.fetch_message(
            message_id
        )

    except (discord.NotFound, discord.Forbidden):

        return

    entries = giveaway.get("entries", [])

    if not entries:

        winner_text = "Nobody entered."

    else:

        winner_id = random.choice(entries)

        winner_text = f"<@{winner_id}> 🎉"

    e = make_embed(
        "🎉 Giveaway Ended",
        f"## {giveaway['prize']}\n\n"
        f"**Winner:** {winner_text}\n"
        f"**Entries:** `{len(entries)}`",
        SUCCESS_COLOR
    )

    await message.edit(
        embed=e,
        view=None
    )


# ============================================================
# /GIVEAWAY
# ============================================================

@bot.tree.command(
    name="giveaway",
    description="Start a giveaway."
)
@app_commands.describe(
    prize="Prize for the giveaway",
    duration="Duration in minutes",
    channel="Channel where the giveaway will be sent"
)
async def giveaway(
    interaction: discord.Interaction,
    prize: str,
    duration: int,
    channel: discord.TextChannel = None
):

    if not await staff_check(interaction):
        return

    if duration < 1 or duration > 10080:

        return await interaction.response.send_message(
            "❌ Duration must be between 1 minute and 7 days.",
            ephemeral=True
        )

    channel = channel or interaction.channel

    if not isinstance(channel, discord.TextChannel):

        return await interaction.response.send_message(
            "❌ Please select a normal text channel.",
            ephemeral=True
        )

    end_time = (
        datetime.now(timezone.utc)
        + timedelta(minutes=duration)
    )

    e = make_embed(
        "🎉 BFC GIVEAWAY",
        f"## {prize}\n\n"
        "Click the button below to enter!\n\n"
        f"**Ends:** {discord.utils.format_dt(end_time, 'R')}\n"
        f"**Hosted by:** {interaction.user.mention}"
    )

    message = await channel.send(
        embed=e
    )

    view = GiveawayView(
        message.id
    )

    await message.edit(
        view=view
    )

    data["giveaways"][str(message.id)] = {
        "channel_id": channel.id,
        "prize": prize,
        "entries": [],
        "ended": False,
        "end_time": end_time.isoformat()
    }

    save_data()

    await interaction.response.send_message(
        embed=make_embed(
            "✅ Giveaway Created",
            f"Your giveaway was created in {channel.mention}.",
            SUCCESS_COLOR
        ),
        ephemeral=True
    )

    await asyncio.sleep(
        duration * 60
    )

    await finish_giveaway(
        message.id
    )


# ============================================================
# ERROR HANDLER
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error
):

    print(f"Command error: {repr(error)}")

    error_embed = make_embed(
        "❌ Something Went Wrong",
        "The command could not be completed.\n"
        "Please check the options and try again.",
        ERROR_COLOR
    )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                embed=error_embed,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                embed=error_embed,
                ephemeral=True
            )

    except Exception as followup_error:

        print(
            f"Error handler failed: {followup_error}"
        )


# ============================================================
# START BFC BOT
# ============================================================

bot.run(TOKEN)