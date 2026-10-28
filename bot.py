"""
Discord Bot แจ้งเตือนเวลากิจกรรม Ragnarok: The New World
- อ่านตารางกิจกรรมจาก events.json (แก้ไขได้เอง ไม่ต้องแก้โค้ด)
- แจ้งเตือนล่วงหน้าตามจำนวนนาทีที่ตั้งไว้ + ตอนเริ่มกิจกรรม
- ตั้งค่าห้อง/ยศที่จะแท็กต่อเซิร์ฟเวอร์ด้วย slash command
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

import sys

# ถ้าถูกแพ็กเป็น .exe (PyInstaller) ให้ใช้โฟลเดอร์ที่ไฟล์ .exe อยู่ เพื่อหา events.json / .env
BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
load_dotenv(BASE / ".env")
TOKEN = os.getenv("DISCORD_TOKEN")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")

EVENTS_FILE = BASE / "events.json"
# บน Railway ให้ตั้ง SETTINGS_PATH ชี้ไปที่ Volume (เช่น /data/settings.json) เพื่อไม่ให้ค่าหายตอน redeploy
SETTINGS_FILE = Path(os.getenv("SETTINGS_PATH", BASE / "settings.json"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ro-bot")

DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
DAY_TH = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]


# ---------------------------------------------------------------- ข้อมูลกิจกรรม
@dataclass
class Event:
    id: str
    name: str
    emoji: str = "📅"
    days: set[int] = field(default_factory=set)
    times: list[dtime] = field(default_factory=list)
    window: dict | None = None  # {"start": time, "end": time, "every_min": int}
    duration_min: int = 0
    remind_before: list[int] = field(default_factory=list)
    note: str = ""

    def occurrences_on(self, day: datetime) -> list[datetime]:
        """คืนเวลาเริ่มทั้งหมดของกิจกรรมในวันที่กำหนด (timezone-aware)"""
        if day.weekday() not in self.days:
            return []
        tz = day.tzinfo
        d = day.date()
        starts = [datetime.combine(d, t, tz) for t in self.times]
        if self.window:
            cur = datetime.combine(d, self.window["start"], tz)
            end = datetime.combine(d, self.window["end"], tz)
            step = timedelta(minutes=self.window["every_min"])
            while cur <= end:
                starts.append(cur)
                cur += step
        return sorted(set(starts))


def _parse_time(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


class Schedule:
    def __init__(self, path: Path):
        self.path = path
        self.tz = ZoneInfo("Asia/Bangkok")
        self.events: list[Event] = []
        self.load()

    def load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.tz = ZoneInfo(raw.get("timezone", "Asia/Bangkok"))
        default_before = raw.get("default_remind_before", [15, 5])
        events: list[Event] = []
        for e in raw["events"]:
            days_raw = e.get("days", ["daily"])
            if "daily" in days_raw:
                days = set(range(7))
            else:
                days = {DAY_MAP[d.lower()[:3]] for d in days_raw}
            window = None
            if "window" in e:
                w = e["window"]
                window = {
                    "start": _parse_time(w["start"]),
                    "end": _parse_time(w["end"]),
                    "every_min": int(w.get("every_min", 60)),
                }
            events.append(
                Event(
                    id=e["id"],
                    name=e["name"],
                    emoji=e.get("emoji", "📅"),
                    days=days,
                    times=[_parse_time(t) for t in e.get("times", [])],
                    window=window,
                    duration_min=int(e.get("duration_min", 0)),
                    remind_before=sorted(set(int(x) for x in e.get("remind_before", default_before)), reverse=True),
                    note=e.get("note", ""),
                )
            )
        self.events = events
        log.info("โหลดกิจกรรม %d รายการ (timezone %s)", len(events), self.tz)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def upcoming(self, hours: int = 48) -> list[tuple[Event, datetime]]:
        """กิจกรรมที่จะเริ่มภายใน N ชั่วโมงข้างหน้า เรียงตามเวลา"""
        now = self.now()
        horizon = now + timedelta(hours=hours)
        out: list[tuple[Event, datetime]] = []
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        while day <= horizon:
            for ev in self.events:
                for start in ev.occurrences_on(day):
                    if now - timedelta(minutes=1) <= start <= horizon:
                        out.append((ev, start))
            day += timedelta(days=1)
        out.sort(key=lambda x: x[1])
        return out

    def on_day(self, day: datetime) -> list[tuple[Event, datetime]]:
        out = [(ev, s) for ev in self.events for s in ev.occurrences_on(day)]
        out.sort(key=lambda x: x[1])
        return out


# ---------------------------------------------------------------- การตั้งค่าต่อเซิร์ฟเวอร์
class Settings:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict] = {}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def get(self, guild_id: int) -> dict:
        # ค่าเริ่มต้นจาก env (DEFAULT_CHANNEL_ID / DEFAULT_ROLE_ID) ใช้กับโฮสต์ฟรีที่ดิสก์ไม่ถาวร
        # ค่าที่ตั้งด้วย /ro setchannel จะทับค่าเหล่านี้จนกว่าจะ redeploy
        def _env_int(name: str) -> int | None:
            v = os.getenv(name, "").strip()
            return int(v) if v.isdigit() else None

        return self.data.setdefault(
            str(guild_id),
            {"channel_id": _env_int("DEFAULT_CHANNEL_ID"), "role_id": _env_int("DEFAULT_ROLE_ID"), "disabled": []},
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- ตัวบอท
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
schedule = Schedule(EVENTS_FILE)
settings = Settings(SETTINGS_FILE)
sent_keys: set[str] = set()  # กันแจ้งซ้ำ: "guild:event:start_iso:before"


def ts(dt: datetime, style: str = "t") -> str:
    """Discord timestamp แสดงเวลาตาม timezone ของผู้ใช้แต่ละคน"""
    return f"<t:{int(dt.timestamp())}:{style}>"


def event_embed(ev: Event, start: datetime, minutes_left: int) -> discord.Embed:
    if minutes_left <= 0:
        title = f"{ev.emoji} {ev.name} เริ่มแล้ว!"
        color = discord.Color.green()
    else:
        title = f"{ev.emoji} {ev.name} จะเริ่มในอีก {minutes_left} นาที"
        color = discord.Color.orange()
    emb = discord.Embed(title=title, color=color)
    emb.add_field(name="เวลาเริ่ม", value=f"{ts(start)} ({ts(start, 'R')})", inline=True)
    if ev.duration_min > 0:
        end = start + timedelta(minutes=ev.duration_min)
        emb.add_field(name="สิ้นสุด", value=ts(end), inline=True)
    if ev.note:
        emb.add_field(name="หมายเหตุ", value=ev.note, inline=False)
    emb.set_footer(text="Ragnarok: The New World • เวลาแสดงตามโซนเวลาของคุณ")
    return emb


@tasks.loop(seconds=30)
async def reminder_loop() -> None:
    now = schedule.now()
    upcoming = schedule.upcoming(hours=2)
    for guild in bot.guilds:
        conf = settings.get(guild.id)
        if not conf.get("channel_id"):
            continue
        channel = guild.get_channel(conf["channel_id"])
        if channel is None:
            continue
        disabled = set(conf.get("disabled", []))
        for ev, start in upcoming:
            if ev.id in disabled:
                continue
            # เช็กทั้งเตือนล่วงหน้า (before > 0) และตอนเริ่ม (before = 0)
            for before in [*ev.remind_before, 0]:
                fire_at = start - timedelta(minutes=before)
                # ยิงเมื่อถึงเวลา และไม่เกิน 90 วิ (กันกรณีบอทเพิ่งเปิดแล้วยิงย้อนหลังทั้งหมด)
                if not (fire_at <= now < fire_at + timedelta(seconds=90)):
                    continue
                key = f"{guild.id}:{ev.id}:{start.isoformat()}:{before}"
                if key in sent_keys:
                    continue
                sent_keys.add(key)
                mention = f"<@&{conf['role_id']}> " if conf.get("role_id") else ""
                try:
                    await channel.send(
                        content=mention or None,
                        embed=event_embed(ev, start, before),
                        allowed_mentions=discord.AllowedMentions(roles=True),
                    )
                    log.info("แจ้งเตือน %s (%s นาที) -> %s/%s", ev.name, before, guild.name, channel.name)
                except discord.HTTPException as exc:
                    log.warning("ส่งข้อความไม่ได้ใน %s: %s", guild.name, exc)
    # ล้าง key เก่าไม่ให้โตไม่สิ้นสุด
    if len(sent_keys) > 5000:
        sent_keys.clear()


async def start_health_server() -> None:
    """เปิด HTTP endpoint เล็กๆ เมื่อมีตัวแปร PORT (โฮสต์อย่าง Render/Koyeb ต้องการ)"""
    port = os.getenv("PORT")
    if not port:
        return
    from aiohttp import web  # มากับ discord.py อยู่แล้ว

    async def ok(_: web.Request) -> web.Response:
        return web.Response(text=f"ok • {bot.user} • {schedule.now():%Y-%m-%d %H:%M}")

    app = web.Application()
    app.add_routes([web.get("/", ok), web.get("/health", ok)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(port)).start()
    log.info("health server เปิดที่พอร์ต %s", port)


@bot.event
async def setup_hook() -> None:
    await start_health_server()


@reminder_loop.before_loop
async def _wait_ready() -> None:
    await bot.wait_until_ready()


@bot.event
async def on_ready() -> None:
    log.info("ล็อกอินเป็น %s (%s)", bot.user, bot.user.id)
    try:
        if DEV_GUILD_ID:
            g = discord.Object(id=int(DEV_GUILD_ID))
            bot.tree.copy_global_to(guild=g)
            await bot.tree.sync(guild=g)
        await bot.tree.sync()
        log.info("sync slash commands เรียบร้อย")
    except Exception as exc:  # noqa: BLE001
        log.exception("sync commands ล้มเหลว: %s", exc)
    if not reminder_loop.is_running():
        reminder_loop.start()


# ---------------------------------------------------------------- Slash commands
ro = app_commands.Group(name="ro", description="แจ้งเตือนกิจกรรม Ragnarok: The New World")


@ro.command(name="setchannel", description="ตั้งห้องที่จะให้บอทแจ้งเตือน (ค่าเริ่มต้น = ห้องนี้)")
@app_commands.checks.has_permissions(manage_guild=True)
async def setchannel(inter: discord.Interaction, channel: discord.TextChannel | None = None) -> None:
    channel = channel or inter.channel
    conf = settings.get(inter.guild_id)
    conf["channel_id"] = channel.id
    settings.save()
    await inter.response.send_message(f"✅ จะแจ้งเตือนกิจกรรมที่ {channel.mention}", ephemeral=True)


@ro.command(name="setrole", description="ตั้งยศที่จะแท็กเวลาแจ้งเตือน (ไม่ใส่ = ยกเลิกการแท็ก)")
@app_commands.checks.has_permissions(manage_guild=True)
async def setrole(inter: discord.Interaction, role: discord.Role | None = None) -> None:
    conf = settings.get(inter.guild_id)
    conf["role_id"] = role.id if role else None
    settings.save()
    msg = f"✅ จะแท็ก {role.mention} เวลาแจ้งเตือน" if role else "✅ ยกเลิกการแท็กยศแล้ว"
    await inter.response.send_message(msg, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


async def _event_choices(inter: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=f"{e.emoji} {e.name}"[:100], value=e.id)
        for e in schedule.events
        if current.lower() in e.name.lower() or current.lower() in e.id
    ][:25]


@ro.command(name="toggle", description="เปิด/ปิดการแจ้งเตือนของกิจกรรมหนึ่งๆ ในเซิร์ฟเวอร์นี้")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.autocomplete(event=_event_choices)
async def toggle(inter: discord.Interaction, event: str) -> None:
    ev = next((e for e in schedule.events if e.id == event), None)
    if not ev:
        await inter.response.send_message("❌ ไม่พบกิจกรรมนี้", ephemeral=True)
        return
    conf = settings.get(inter.guild_id)
    disabled = set(conf.get("disabled", []))
    if ev.id in disabled:
        disabled.remove(ev.id)
        state = "เปิด 🔔"
    else:
        disabled.add(ev.id)
        state = "ปิด 🔕"
    conf["disabled"] = sorted(disabled)
    settings.save()
    await inter.response.send_message(f"{state} การแจ้งเตือน **{ev.name}** แล้ว", ephemeral=True)


@ro.command(name="next", description="กิจกรรมที่กำลังจะมาถึง")
async def next_events(inter: discord.Interaction, count: app_commands.Range[int, 1, 15] = 5) -> None:
    disabled = set(settings.get(inter.guild_id).get("disabled", [])) if inter.guild_id else set()
    items = [(e, s) for e, s in schedule.upcoming(hours=24 * 7) if e.id not in disabled][:count]
    if not items:
        await inter.response.send_message("ไม่มีกิจกรรมในสัปดาห์นี้", ephemeral=True)
        return
    emb = discord.Embed(title="⏭️ กิจกรรมถัดไป", color=discord.Color.blurple())
    emb.description = "\n".join(f"{e.emoji} **{e.name}** — {ts(s, 'f')} ({ts(s, 'R')})" for e, s in items)
    await inter.response.send_message(embed=emb)


@ro.command(name="today", description="ตารางกิจกรรมของวันนี้")
async def today(inter: discord.Interaction) -> None:
    now = schedule.now()
    disabled = set(settings.get(inter.guild_id).get("disabled", [])) if inter.guild_id else set()
    items = [(e, s) for e, s in schedule.on_day(now) if e.id not in disabled]
    emb = discord.Embed(
        title=f"📅 กิจกรรมวัน{DAY_TH[now.weekday()]} {now:%d/%m/%Y}",
        color=discord.Color.blurple(),
    )
    if not items:
        emb.description = "วันนี้ไม่มีกิจกรรม"
    else:
        # รวมกิจกรรมที่เกิดถี่ (เช่น Mimic Chest ทุก 30 นาที) ให้เป็นบรรทัดเดียว
        grouped: dict[str, list[datetime]] = {}
        order: list[Event] = []
        for e, s in items:
            if e.id not in grouped:
                grouped[e.id] = []
                order.append(e)
            grouped[e.id].append(s)
        lines = []
        for e in order:
            starts = grouped[e.id]
            done = "~~" if all(s < now for s in starts) else ""
            if len(starts) > 4:
                when = f"{starts[0]:%H:%M}–{starts[-1]:%H:%M} (ทุก {e.window['every_min']} นาที)"
            else:
                when = ", ".join(f"{s:%H:%M}" for s in starts)
            lines.append(f"{done}{e.emoji} **{e.name}** — {when}{done}")
        emb.description = "\n".join(lines)
    emb.set_footer(text=f"เวลาเซิร์ฟเวอร์ ({schedule.tz})")
    await inter.response.send_message(embed=emb)


@ro.command(name="week", description="ตารางกิจกรรมทั้งสัปดาห์")
async def week(inter: discord.Interaction) -> None:
    emb = discord.Embed(title="🗓️ ตารางกิจกรรมประจำสัปดาห์", color=discord.Color.blurple())
    for wd in range(7):
        lines = []
        for e in schedule.events:
            if wd not in e.days:
                continue
            if e.window:
                when = f"{e.window['start']:%H:%M}–{e.window['end']:%H:%M} ทุก {e.window['every_min']} นาที"
            else:
                when = ", ".join(f"{t:%H:%M}" for t in e.times)
            lines.append(f"{e.emoji} {e.name} — {when}")
        emb.add_field(name=f"วัน{DAY_TH[wd]}", value="\n".join(lines) or "—", inline=False)
    emb.set_footer(text=f"เวลาเซิร์ฟเวอร์ ({schedule.tz}) • แก้ตารางได้ที่ events.json")
    await inter.response.send_message(embed=emb)


@ro.command(name="reload", description="โหลดไฟล์ events.json ใหม่ (หลังแก้ตาราง)")
@app_commands.checks.has_permissions(manage_guild=True)
async def reload(inter: discord.Interaction) -> None:
    try:
        schedule.load()
    except Exception as exc:  # noqa: BLE001
        await inter.response.send_message(f"❌ โหลดไม่สำเร็จ: `{exc}`", ephemeral=True)
        return
    await inter.response.send_message(f"✅ โหลดใหม่แล้ว {len(schedule.events)} กิจกรรม", ephemeral=True)


@ro.command(name="test", description="ส่งข้อความทดสอบไปยังห้องแจ้งเตือน")
@app_commands.checks.has_permissions(manage_guild=True)
async def test(inter: discord.Interaction) -> None:
    conf = settings.get(inter.guild_id)
    channel = inter.guild.get_channel(conf["channel_id"]) if conf.get("channel_id") else None
    if channel is None:
        await inter.response.send_message("❌ ยังไม่ได้ตั้งห้อง ใช้ `/ro setchannel` ก่อน", ephemeral=True)
        return
    ev = schedule.events[0]
    start = schedule.now() + timedelta(minutes=15)
    mention = f"<@&{conf['role_id']}> " if conf.get("role_id") else ""
    await channel.send(content=mention or None, embed=event_embed(ev, start, 15),
                       allowed_mentions=discord.AllowedMentions(roles=True))
    await inter.response.send_message(f"✅ ส่งข้อความทดสอบไปที่ {channel.mention} แล้ว", ephemeral=True)


@ro.error
async def ro_error(inter: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ ต้องมีสิทธิ์ Manage Server ถึงจะใช้คำสั่งนี้ได้"
    else:
        log.exception("คำสั่งผิดพลาด: %s", error)
        msg = f"❌ เกิดข้อผิดพลาด: `{error}`"
    if inter.response.is_done():
        await inter.followup.send(msg, ephemeral=True)
    else:
        await inter.response.send_message(msg, ephemeral=True)


bot.tree.add_command(ro)


def first_run_setup() -> str:
    """ไม่มีโทเคน -> ถามผู้ใช้แล้วบันทึกลง .env ให้ (สำหรับคนที่รันบนเครื่องตัวเอง)"""
    print("=" * 60)
    print(" RO: The New World - Discord Event Reminder Bot")
    print(" ยังไม่ได้ตั้งค่าโทเคน ทำตามนี้ครั้งเดียว:")
    print("  1) https://discord.com/developers/applications -> New Application")
    print("  2) เมนู Bot -> Reset Token -> คัดลอก")
    print("  3) วางโทเคนด้านล่างแล้วกด Enter")
    print("=" * 60)
    token = input("DISCORD_TOKEN: ").strip()
    if not token:
        raise SystemExit("ไม่ได้ใส่โทเคน ปิดโปรแกรม")
    guild = input("Guild ID ของเซิร์ฟเวอร์ (ไม่บังคับ กด Enter ข้าม): ").strip()
    (BASE / ".env").write_text(f"DISCORD_TOKEN={token}\nDEV_GUILD_ID={guild}\n", encoding="utf-8")
    print("บันทึกลง .env แล้ว ครั้งหน้าจะไม่ถามอีก\n")
    os.environ["DEV_GUILD_ID"] = guild
    return token


if __name__ == "__main__":
    token = TOKEN or first_run_setup()
    DEV_GUILD_ID = os.getenv("DEV_GUILD_ID") or DEV_GUILD_ID
    try:
        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        (BASE / ".env").unlink(missing_ok=True)
        print("\n❌ โทเคนไม่ถูกต้อง ลบไฟล์ .env แล้ว เปิดโปรแกรมใหม่เพื่อใส่โทเคนอีกครั้ง")
    except KeyboardInterrupt:
        pass
    finally:
        if getattr(sys, "frozen", False) or os.name == "nt":
            input("\nกด Enter เพื่อปิดหน้าต่าง...")
