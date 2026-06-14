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

pomodoro_task: asyncio.Task | None = None
pomodoro_phase = "idle"
pomodoro_end_time = 0.0

COLORS = {
    "work": 0x2D7D46,
    "break": 0x3B82F6,
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


def format_clock(seconds: float) -> str:
    seconds = int(max(0, seconds))
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


def progress_bar(remaining: float, total: float, length: int = 20) -> str:
    fraction = max(0, min(1, 1 - remaining / total)) if total > 0 else 0
    filled = int(fraction * length)
    empty = length - filled
    return f"`{'█' * filled}{'░' * empty}`"


def study_vc_members_list(vc) -> str:
    if not vc or not vc.members:
        return "*No one*"
    names = [m.display_name for m in vc.members if not m.bot]
    if not names:
        return "*No one*"
    return ", ".join(f"**{n}**" for n in names)


async def get_or_create_role(guild: discord.Guild) -> discord.Role:
    role = discord.utils.get(guild.roles, name=config.STUDYING_ROLE_NAME)
    if role is None:
        role = await guild.create_role(
            name=config.STUDYING_ROLE_NAME,
            color=discord.Color.green(),
            mentionable=True,
        )
    return role


def get_notification_channel() -> discord.VoiceChannel | None:
    return bot.get_channel(config.STUDY_VC_ID)


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


def _make_timer_file(phase: str, remaining: float, total: float, cycle: int, vc) -> discord.File:
    members = [m.display_name for m in (vc.members if vc else []) if not m.bot]
    buf = timer_image.generate_timer_image(phase, remaining, total, cycle, members)
    return discord.File(buf, filename="timer.png")


async def pomodoro_loop():
    global pomodoro_phase, pomodoro_end_time

    channel = get_notification_channel()
    cycle = 0

    while True:
        cycle += 1

        pomodoro_phase = "work"
        total_seconds = config.POMODORO_WORK * 60
        pomodoro_end_time = time.time() + total_seconds

        if channel:
            vc = bot.get_channel(config.STUDY_VC_ID)
            file = _make_timer_file("work", total_seconds, total_seconds, cycle, vc)
            timer_msg = await channel.send(file=file)

            for _ in range(60, total_seconds, 60):
                await asyncio.sleep(60)
                remaining = max(0, pomodoro_end_time - time.time())
                vc = bot.get_channel(config.STUDY_VC_ID)
                file = _make_timer_file("work", remaining, total_seconds, cycle, vc)
                await timer_msg.edit(attachments=[file])

            remaining = max(0, pomodoro_end_time - time.time())
            if remaining > 0:
                await asyncio.sleep(remaining)

            done_buf = timer_image.generate_timer_complete_image("work", cycle, f"{config.POMODORO_WORK}:00")
            done_file = discord.File(done_buf, filename="timer.png")
            await timer_msg.edit(attachments=[done_file])
        else:
            await asyncio.sleep(total_seconds)

        study_vc = bot.get_channel(config.STUDY_VC_ID)
        if study_vc and len(study_vc.members) == 0:
            break

        pomodoro_phase = "break"
        total_seconds = config.POMODORO_BREAK * 60
        pomodoro_end_time = time.time() + total_seconds

        if channel:
            vc = bot.get_channel(config.STUDY_VC_ID)
            file = _make_timer_file("break", total_seconds, total_seconds, cycle, vc)
            break_msg = await channel.send(file=file)

            for _ in range(60, total_seconds, 60):
                await asyncio.sleep(60)
                remaining = max(0, pomodoro_end_time - time.time())
                vc = bot.get_channel(config.STUDY_VC_ID)
                file = _make_timer_file("break", remaining, total_seconds, cycle, vc)
                await break_msg.edit(attachments=[file])

            remaining = max(0, pomodoro_end_time - time.time())
            if remaining > 0:
                await asyncio.sleep(remaining)

            done_buf = timer_image.generate_timer_complete_image("break", cycle, f"{config.POMODORO_BREAK}:00")
            done_file = discord.File(done_buf, filename="timer.png")
            await break_msg.edit(attachments=[done_file])
        else:
            await asyncio.sleep(total_seconds)

        study_vc = bot.get_channel(config.STUDY_VC_ID)
        if study_vc and len(study_vc.members) == 0:
            break

    pomodoro_phase = "idle"
    pomodoro_end_time = 0.0


def start_pomodoro():
    global pomodoro_task
    if pomodoro_task is None or pomodoro_task.done():
        pomodoro_task = asyncio.create_task(pomodoro_loop())


def stop_pomodoro():
    global pomodoro_task, pomodoro_phase, pomodoro_end_time
    if pomodoro_task and not pomodoro_task.done():
        pomodoro_task.cancel()
    pomodoro_task = None
    pomodoro_phase = "idle"
    pomodoro_end_time = 0.0


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

    joined_study = (
        after.channel is not None
        and after.channel.id == config.STUDY_VC_ID
        and (before.channel is None or before.channel.id != config.STUDY_VC_ID)
    )
    left_study = (
        before.channel is not None
        and before.channel.id == config.STUDY_VC_ID
        and (after.channel is None or after.channel.id != config.STUDY_VC_ID)
    )

    channel = get_notification_channel()

    if joined_study:
        try:
            role = await get_or_create_role(member.guild)
            await member.add_roles(role)
        except discord.Forbidden:
            pass

        database.start_session(member.id)

        study_vc = bot.get_channel(config.STUDY_VC_ID)
        first_person = study_vc and len(study_vc.members) == 1

        if first_person:
            start_pomodoro()

        if channel:
            if first_person:
                await channel.send(f"{member.mention} started a study session.")
            else:
                remaining = max(0, pomodoro_end_time - time.time())
                phase_label = "Focus" if pomodoro_phase == "work" else "Break"
                await channel.send(f"{member.mention} joined the study session.")
                view = _make_view(
                    COLORS["join"],
                    "## JOINED SESSION",
                    "*Welcome in. Stay locked.*",
                    "---",
                    f"**Phase:** {phase_label}  ·  **Remaining:** {format_clock(remaining)}",
                )
                await channel.send(view=view)

    if left_study:
        try:
            role = discord.utils.get(member.guild.roles, name=config.STUDYING_ROLE_NAME)
            if role and role in member.roles:
                await member.remove_roles(role)
        except discord.Forbidden:
            pass

        duration = database.end_session(member.id)

        if channel:
            await channel.send(f"{member.mention} left the study session.")
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            total_today = database.get_user_total(member.id, today.timestamp())
            sessions_today = database.get_session_count(member.id, today.timestamp())
            streak = database.get_study_streak(member.id)
            buf = session_summary.generate_session_summary(
                name=member.display_name,
                duration_str=format_duration(duration),
                duration_secs=duration,
                total_today_str=format_duration(total_today),
                sessions_today=sessions_today,
                streak=streak,
            )
            await channel.send(file=discord.File(buf, filename="session.png"))

        study_vc = bot.get_channel(config.STUDY_VC_ID)
        if study_vc and len(study_vc.members) == 0:
            stop_pomodoro()
            if channel:
                view = _make_view(
                    COLORS["stop"],
                    "## SESSION ENDED",
                    "*Study VC is empty. Pomodoro timer stopped.*",
                )
                await channel.send(view=view)


async def _build_leaderboard(guild, period: str) -> discord.File:
    if period == "daily":
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        since = today.timestamp()
        title = "STUDY TIME LEADERBOARD"
        subtitle = f"TODAY: {datetime.now(timezone.utc).strftime('%B %d, %Y').upper()}  ·  SERVER: {guild.name.upper()}"
    elif period == "monthly":
        first_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        since = first_of_month.timestamp()
        title = "STUDY TIME LEADERBOARD"
        month = datetime.now(timezone.utc).strftime("%B").upper()
        subtitle = f"THIS MONTH: {month}  ·  SERVER: {guild.name.upper()}"
    else:
        since = 0
        title = "STUDY TIME LEADERBOARD"
        subtitle = f"ALL TIME  ·  SERVER: {guild.name.upper()}"

    rows = database.get_leaderboard(since)
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

    buf = lb.generate_leaderboard_image(title, subtitle, entries)
    return discord.File(buf, filename="leaderboard.png")


def _studytime_view(user_id: int, user_name: str, total: float, label: str) -> discord.ui.LayoutView:
    return _make_view(
        COLORS["info"],
        "## Your Study Time",
        "*Keep showing up.*",
        "---",
        f"**Period:** {label}  ·  **Total:** {format_duration(total)}",
        footer=f"Professor Moore · {user_name}",
    )


def _pomodoro_response():
    if pomodoro_phase == "idle":
        view = _make_view(
            COLORS["stop"],
            "## Pomodoro Status",
            "*No session running. Join the study VC to start one.*",
        )
        return view, None
    remaining = max(0, pomodoro_end_time - time.time())
    total = config.POMODORO_WORK * 60 if pomodoro_phase == "work" else config.POMODORO_BREAK * 60
    vc = bot.get_channel(config.STUDY_VC_ID)
    file = _make_timer_file(pomodoro_phase, remaining, total, 0, vc)
    return None, file


@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard(ctx: commands.Context, period: str = "all"):
    async with ctx.typing():
        file = await _build_leaderboard(ctx.guild, period)
    await ctx.send(file=file)


@bot.command(name="studytime", aliases=["st"])
async def studytime(ctx: commands.Context, period: str = "all"):
    if period == "daily":
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        since, label = today.timestamp(), "Today"
    elif period == "monthly":
        first = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        since, label = first.timestamp(), "This Month"
    else:
        since, label = 0, "All Time"
    total = database.get_user_total(ctx.author.id, since)
    view = _studytime_view(ctx.author.id, ctx.author.display_name, total, label)
    await ctx.send(view=view)


@bot.command(name="pomodoro", aliases=["pomo"])
async def pomodoro_status(ctx: commands.Context):
    view, file = _pomodoro_response()
    if view:
        await ctx.send(view=view)
    else:
        await ctx.send(file=file)


@bot.tree.command(name="leaderboard", description="Show the study leaderboard")
@app_commands.describe(period="Time period: all, daily, or monthly")
@app_commands.choices(period=[
    app_commands.Choice(name="All Time", value="all"),
    app_commands.Choice(name="Daily", value="daily"),
    app_commands.Choice(name="Monthly", value="monthly"),
])
async def slash_leaderboard(interaction: discord.Interaction, period: app_commands.Choice[str] = None):
    p = period.value if period else "all"
    await interaction.response.defer()
    file = await _build_leaderboard(interaction.guild, p)
    await interaction.followup.send(file=file)


@bot.tree.command(name="studytime", description="Check your study time")
@app_commands.describe(period="Time period: all, daily, or monthly")
@app_commands.choices(period=[
    app_commands.Choice(name="All Time", value="all"),
    app_commands.Choice(name="Daily", value="daily"),
    app_commands.Choice(name="Monthly", value="monthly"),
])
async def slash_studytime(interaction: discord.Interaction, period: app_commands.Choice[str] = None):
    p = period.value if period else "all"
    if p == "daily":
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        since, label = today.timestamp(), "Today"
    elif p == "monthly":
        first = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        since, label = first.timestamp(), "This Month"
    else:
        since, label = 0, "All Time"
    total = database.get_user_total(interaction.user.id, since)
    view = _studytime_view(interaction.user.id, interaction.user.display_name, total, label)
    await interaction.response.send_message(view=view)


async def _build_profile(member: discord.Member) -> discord.File:
    total = database.get_user_total(member.id)
    sessions = database.get_session_count(member.id)
    best = database.get_best_session(member.id)
    rank = database.get_user_rank(member.id)
    streak = database.get_study_streak(member.id)
    first_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly = database.get_user_total(member.id, first_of_month.timestamp())
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


@bot.tree.command(name="pomodoro", description="Check current pomodoro timer status")
async def slash_pomodoro(interaction: discord.Interaction):
    view, file = _pomodoro_response()
    if view:
        await interaction.response.send_message(view=view)
    else:
        await interaction.response.send_message(file=file)


def _history_view(member: discord.Member) -> discord.ui.LayoutView:
    rows = database.get_recent_sessions(member.id, 10)
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
    total = database.get_user_total(member.id)
    sessions = database.get_session_count(member.id)
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


HELP_TEXT = (
    "## Professor Moore\n"
    "*Greetings. I am Prof. Jonathan Moore, your study companion.*\n\n"
    "**Commands** (prefix `!` or `/`)\n"
    "` leaderboard [all|daily|monthly] ` — Study time rankings\n"
    "` studytime [all|daily|monthly] ` — Your personal study time\n"
    "` profile [@user] ` — Student profile card\n"
    "` pomodoro ` — Current focus timer status\n"
    "` history [@user] ` — Recent session history\n"
    "` help ` — This message\n\n"
    "**How it works**\n"
    "Join the study voice channel. I will track your time, assign the Studying role, "
    "and run a 50/10 Pomodoro cycle automatically. Stay focused."
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
