import asyncio
import itertools
import time
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import database
import leaderboard as lb
import timer_image
import profile_card
import session_summary


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

STATUS_CYCLE = itertools.cycle([
    discord.Activity(type=discord.ActivityType.watching, name="the study hall"),
    discord.Activity(type=discord.ActivityType.listening, name="pages turning"),
    discord.Activity(type=discord.ActivityType.watching, name="your progress"),
    discord.Activity(type=discord.ActivityType.listening, name="silence and focus"),
    discord.Activity(type=discord.ActivityType.watching, name="who's studying"),
])


@tasks.loop(minutes=5)
async def rotate_status():
    await bot.change_presence(activity=next(STATUS_CYCLE))


COLORS = {
    "join": 0x8B5CF6,
    "leave": 0xEF4444,
    "stop": 0x6B7280,
    "gold": 0xF59E0B,
    "info": 0x6366F1,
}


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _get_guild_config(guild_id: int) -> dict | None:
    return database.get_server_config(guild_id)


def _get_study_vc(guild: discord.Guild) -> discord.VoiceChannel | None:
    cfg = _get_guild_config(guild.id)
    if cfg is None:
        return None
    return bot.get_channel(cfg["study_vc_id"])


async def get_or_create_role(guild: discord.Guild) -> discord.Role:
    cfg = _get_guild_config(guild.id)
    role_name = cfg["role_name"] if cfg else "Studying"
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        role = await guild.create_role(
            name=role_name,
            color=discord.Color.green(),
            mentionable=True,
        )
    return role


def _make_view(color: int, *text_blocks: str, footer: str = "Professor Moore") -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    container = discord.ui.Container(accent_colour=color)
    for i, text in enumerate(text_blocks):
        if text == "---":
            container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        elif text == "===":
            container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
        else:
            container.add_item(discord.ui.TextDisplay(text))
    if footer:
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(discord.ui.TextDisplay(f"-# {footer}"))
    view.add_item(container)
    return view


def _make_focus_file(vc, guild_id: int) -> discord.File:
    members = []
    now = time.time()
    oldest_join = now
    for m in (vc.members if vc else []):
        if m.bot:
            continue
        join_time = database.get_active_join_time(m.id, guild_id)
        if join_time:
            oldest_join = min(oldest_join, join_time)
            elapsed = format_duration(now - join_time)
        else:
            elapsed = "0s"
        members.append((m.display_name, elapsed))
    total_elapsed = now - oldest_join if members else 0
    buf = timer_image.generate_focus_image(total_elapsed, members)
    return discord.File(buf, filename="focus.png")


@bot.event
async def on_ready():
    database.init_db()
    await bot.tree.sync()
    rotate_status.start()
    print(f"Logged in as {bot.user} — slash commands synced")


@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
):
    if member.bot:
        return

    guild_id = member.guild.id
    cfg = _get_guild_config(guild_id)
    if cfg is None:
        return

    vc_id = cfg["study_vc_id"]

    joined_study = (
        after.channel is not None
        and after.channel.id == vc_id
        and (before.channel is None or before.channel.id != vc_id)
    )
    left_study = (
        before.channel is not None
        and before.channel.id == vc_id
        and (after.channel is None or after.channel.id != vc_id)
    )

    channel = bot.get_channel(vc_id)

    if joined_study:
        try:
            role = await get_or_create_role(member.guild)
            await member.add_roles(role)
        except discord.Forbidden:
            pass

        database.start_session(member.id, guild_id)

        if channel:
            await channel.send(f"{member.mention} joined the study session.")

    if left_study:
        try:
            role_name = cfg["role_name"]
            role = discord.utils.get(member.guild.roles, name=role_name)
            if role and role in member.roles:
                await member.remove_roles(role)
        except discord.Forbidden:
            pass

        duration = database.end_session(member.id)

        if channel:
            await channel.send(f"{member.mention} left the study session.")
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            total_today = database.get_user_total(member.id, guild_id, today.timestamp())
            sessions_today = database.get_session_count(member.id, guild_id, today.timestamp())
            streak = database.get_study_streak(member.id, guild_id)
            buf = session_summary.generate_session_summary(
                name=member.display_name,
                duration_str=format_duration(duration),
                duration_secs=duration,
                total_today_str=format_duration(total_today),
                sessions_today=sessions_today,
                streak=streak,
            )
            await channel.send(file=discord.File(buf, filename="session.png"))

        study_vc = bot.get_channel(vc_id)
        human_count = len([m for m in study_vc.members if not m.bot]) if study_vc else 0
        if human_count == 0:
            if channel:
                view = _make_view(
                    COLORS["stop"],
                    "## SESSION ENDED",
                    "*Study VC is empty.*",
                )
                await channel.send(view=view)


def _get_since(period: str) -> tuple[float, str]:
    now = datetime.now(timezone.utc)
    if period == "daily":
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return today.timestamp(), "Today"
    elif period == "weekly":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), "This Week"
    elif period == "monthly":
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return first.timestamp(), "This Month"
    return 0, "All Time"


async def _build_leaderboard(guild, period: str) -> discord.File:
    now = datetime.now(timezone.utc)
    since, label = _get_since(period)

    if period == "daily":
        subtitle = f"TODAY: {now.strftime('%B %d, %Y').upper()}  ·  SERVER: {guild.name.upper()}"
    elif period == "weekly":
        subtitle = f"THIS WEEK  ·  SERVER: {guild.name.upper()}"
    elif period == "monthly":
        month = now.strftime("%B").upper()
        subtitle = f"THIS MONTH: {month}  ·  SERVER: {guild.name.upper()}"
    else:
        subtitle = f"ALL TIME  ·  SERVER: {guild.name.upper()}"

    rows = database.get_leaderboard(guild.id, since)
    entries = []
    for i, (user_id, total_secs) in enumerate(rows):
        member = guild.get_member(user_id)
        name = member.display_name if member else f"User {user_id}"
        avatar = None
        if member and member.display_avatar:
            avatar = await lb.fetch_avatar(member.display_avatar.with_size(128).url)
        entries.append({
            "rank": i + 1,
            "name": name,
            "time_str": format_duration(total_secs),
            "avatar": avatar,
        })

    buf = lb.generate_leaderboard_image("STUDY TIME LEADERBOARD", subtitle, entries)
    return discord.File(buf, filename="leaderboard.png")


def _studytime_view(user_id: int, guild_id: int, user_name: str, total: float, label: str) -> discord.ui.LayoutView:
    return _make_view(
        COLORS["info"],
        "## Your Study Time",
        "*Keep showing up.*",
        "---",
        f"**Period:** {label}  ·  **Total:** {format_duration(total)}",
        footer=f"Professor Moore · {user_name}",
    )


def _focus_response(guild: discord.Guild):
    vc = _get_study_vc(guild)
    if not vc or len([m for m in vc.members if not m.bot]) == 0:
        view = _make_view(
            COLORS["stop"],
            "## Focus Session",
            "*No one is studying right now. Join the study VC to start.*",
        )
        return view, None
    file = _make_focus_file(vc, guild.id)
    return None, file


@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard(ctx: commands.Context, period: str = "all"):
    async with ctx.typing():
        file = await _build_leaderboard(ctx.guild, period)
    await ctx.send(file=file)


@bot.command(name="studytime", aliases=["st"])
async def studytime(ctx: commands.Context, period: str = "all"):
    since, label = _get_since(period)
    total = database.get_user_total(ctx.author.id, ctx.guild.id, since)
    view = _studytime_view(ctx.author.id, ctx.guild.id, ctx.author.display_name, total, label)
    await ctx.send(view=view)


@bot.command(name="focus", aliases=["f"])
async def cmd_focus(ctx: commands.Context):
    view, file = _focus_response(ctx.guild)
    if view:
        await ctx.send(view=view)
    else:
        await ctx.send(file=file)


@bot.tree.command(name="leaderboard", description="Show the study leaderboard")
@app_commands.describe(period="Time period: all, daily, weekly, or monthly")
@app_commands.choices(period=[
    app_commands.Choice(name="All Time", value="all"),
    app_commands.Choice(name="Daily", value="daily"),
    app_commands.Choice(name="Weekly", value="weekly"),
    app_commands.Choice(name="Monthly", value="monthly"),
])
async def slash_leaderboard(interaction: discord.Interaction, period: app_commands.Choice[str] = None):
    p = period.value if period else "all"
    await interaction.response.defer()
    file = await _build_leaderboard(interaction.guild, p)
    await interaction.followup.send(file=file)


@bot.tree.command(name="studytime", description="Check your study time")
@app_commands.describe(period="Time period: all, daily, weekly, or monthly")
@app_commands.choices(period=[
    app_commands.Choice(name="All Time", value="all"),
    app_commands.Choice(name="Daily", value="daily"),
    app_commands.Choice(name="Weekly", value="weekly"),
    app_commands.Choice(name="Monthly", value="monthly"),
])
async def slash_studytime(interaction: discord.Interaction, period: app_commands.Choice[str] = None):
    p = period.value if period else "all"
    since, label = _get_since(p)
    total = database.get_user_total(interaction.user.id, interaction.guild.id, since)
    view = _studytime_view(interaction.user.id, interaction.guild.id, interaction.user.display_name, total, label)
    await interaction.response.send_message(view=view)


@bot.tree.command(name="focus", description="See who's studying and how long they've been at it")
async def slash_focus(interaction: discord.Interaction):
    view, file = _focus_response(interaction.guild)
    if view:
        await interaction.response.send_message(view=view)
    else:
        await interaction.response.send_message(file=file)


async def _build_profile(member: discord.Member) -> discord.File:
    gid = member.guild.id
    total = database.get_user_total(member.id, gid)
    sessions = database.get_session_count(member.id, gid)
    best = database.get_best_session(member.id, gid)
    rank = database.get_user_rank(member.id, gid)
    streak = database.get_study_streak(member.id, gid)
    first_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly = database.get_user_total(member.id, gid, first_of_month.timestamp())
    avatar = None
    if member.display_avatar:
        avatar = await lb.fetch_avatar(member.display_avatar.with_size(128).url)
    buf = profile_card.generate_profile_card(
        name=member.display_name,
        avatar=avatar,
        total_time=format_duration(total),
        sessions=sessions,
        best_session=format_duration(best),
        rank=rank,
        streak=streak,
        monthly_time=format_duration(monthly),
    )
    return discord.File(buf, filename="profile.png")


@bot.command(name="profile", aliases=["p"])
async def cmd_profile(ctx: commands.Context, member: discord.Member = None):
    member = member or ctx.author
    async with ctx.typing():
        file = await _build_profile(member)
    await ctx.send(file=file)


@bot.tree.command(name="profile", description="View your study profile card")
async def slash_profile(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    await interaction.response.defer()
    file = await _build_profile(member)
    await interaction.followup.send(file=file)


def _history_view(member: discord.Member) -> discord.ui.LayoutView:
    gid = member.guild.id
    rows = database.get_recent_sessions(member.id, gid, 10)
    if not rows:
        return _make_view(
            COLORS["info"],
            f"## Session History — {member.display_name}",
            "*No sessions recorded yet.*",
            footer=f"Professor Moore · {member.display_name}",
        )
    lines = []
    for join_time, duration in rows:
        dt = datetime.fromtimestamp(join_time, tz=timezone.utc)
        date_str = dt.strftime("%b %d, %H:%M UTC")
        lines.append(f"` {date_str} ` — **{format_duration(duration)}**")
    total = database.get_user_total(member.id, gid)
    sessions = database.get_session_count(member.id, gid)
    return _make_view(
        COLORS["info"],
        f"## Session History — {member.display_name}",
        f"**{sessions}** sessions  ·  **{format_duration(total)}** total",
        "---",
        "\n".join(lines),
        footer=f"Professor Moore · Last {len(rows)} sessions",
    )


@bot.command(name="history", aliases=["hist"])
async def cmd_history(ctx: commands.Context, member: discord.Member = None):
    member = member or ctx.author
    view = _history_view(member)
    await ctx.send(view=view)


@bot.tree.command(name="history", description="View recent study session history")
@app_commands.describe(member="User to check history for")
async def slash_history(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    view = _history_view(member)
    await interaction.response.send_message(view=view)


@bot.tree.command(name="setup", description="Configure Professor Moore for this server")
@app_commands.describe(
    channel="The voice channel to use as the study room",
    role_name="Name of the role to assign while studying (default: Studying)",
)
@app_commands.default_permissions(manage_guild=True)
async def slash_setup(
    interaction: discord.Interaction,
    channel: discord.VoiceChannel,
    role_name: str = "Studying",
):
    database.set_server_config(interaction.guild.id, channel.id, role_name)
    view = _make_view(
        COLORS["gold"],
        "## Server Configured",
        f"**Study VC:** {channel.mention}\n**Role:** {role_name}",
        "---",
        "*Students who join this voice channel will be tracked automatically.*",
    )
    await interaction.response.send_message(view=view)


HELP_TEXT = (
    "## Professor Moore\n"
    "*Greetings. I am Prof. Jonathan Moore, your study companion.*\n\n"
    "**Commands** (prefix `!` or `/`)\n"
    "` setup #vc [role] ` — Configure study VC for this server (admin)\n"
    "` leaderboard [all|daily|weekly|monthly] ` — Study time rankings\n"
    "` studytime [all|daily|weekly|monthly] ` — Your personal study time\n"
    "` profile [@user] ` — Student profile card\n"
    "` focus ` — See who's studying right now\n"
    "` history [@user] ` — Recent session history\n"
    "` help ` — This message\n\n"
    "**How it works**\n"
    "An admin runs `/setup` to pick the study voice channel. "
    "Join it and I will track your time and assign the Studying role. "
    "Use `/focus` to see the current session. Stay focused."
)


@bot.command(name="help", aliases=["h"])
async def cmd_help(ctx: commands.Context):
    view = _make_view(COLORS["info"], HELP_TEXT, footer="Professor Moore  ·  Created by Ryuga")
    await ctx.send(view=view)


@bot.tree.command(name="help", description="Show all commands and how the bot works")
async def slash_help(interaction: discord.Interaction):
    view = _make_view(COLORS["info"], HELP_TEXT, footer="Professor Moore  ·  Created by Ryuga")
    await interaction.response.send_message(view=view)


bot.run(config.BOT_TOKEN)
