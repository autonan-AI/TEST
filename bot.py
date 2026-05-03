import os
import json
from pathlib import Path
from datetime import datetime

import discord
from discord.ext import commands

ORIGINAL_CHANNEL_NAME = "크리에이터원본"
LOG_CHANNEL_NAME = "로그"

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CONTENTS_FILE = DATA_DIR / "contents.json"


def load_contents():
    if CONTENTS_FILE.exists():
        try:
            with open(CONTENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}

    if "originals" not in data:
        data = {"originals": {}, "thumbnails": data}

    data.setdefault("originals", {})
    data.setdefault("thumbnails", {})
    data.setdefault("buttons", {})
    return data


def save_contents(data):
    with open(CONTENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_original_filename(thumbnail_filename):
    path = Path(thumbnail_filename)
    stem = path.stem
    suffix = path.suffix

    if stem.lower().endswith("s"):
        return stem[:-1] + suffix

    return None


def same_filename(a, b):
    return str(a).lower() == str(b).lower()


def get_original_channel(guild):
    if guild is None:
        return None

    for channel in guild.text_channels:
        if channel.name == ORIGINAL_CHANNEL_NAME:
            return channel

    return None


async def find_original_message_by_filename(guild, filename):
    if not guild or not filename:
        return None

    contents = load_contents()
    saved = contents.get("originals", {}).get(filename)

    if saved:
        try:
            channel = bot.get_channel(int(saved["channel_id"]))
            if channel is None:
                channel = await bot.fetch_channel(int(saved["channel_id"]))

            msg = await channel.fetch_message(int(saved["message_id"]))
            if msg.attachments:
                return msg
        except Exception as e:
            print("저장된 원본 메시지 접근 실패:", filename, repr(e))

    original_channel = get_original_channel(guild)
    if original_channel is None:
        print("원본 채널 없음:", ORIGINAL_CHANNEL_NAME)
        return None

    try:
        async for msg in original_channel.history(limit=1000):
            for attachment in msg.attachments:
                if same_filename(attachment.filename, filename):
                    contents = load_contents()
                    contents["originals"][attachment.filename] = {
                        "message_id": msg.id,
                        "channel_id": msg.channel.id,
                        "user_id": msg.author.id,
                    }
                    save_contents(contents)
                    print("원본 재검색 성공:", attachment.filename)
                    return msg
    except Exception as e:
        print("원본 채널 검색 실패:", filename, repr(e))

    print("원본 검색 실패:", filename)
    return None


async def find_thumbnail_message_for_button(button_message):
    if button_message is None:
        return None

    contents = load_contents()
    button_data = contents.get("buttons", {}).get(str(button_message.id))

    if button_data and button_data.get("thumbnail_message_id"):
        try:
            msg = await button_message.channel.fetch_message(int(button_data["thumbnail_message_id"]))
            if msg.attachments:
                return msg
        except Exception as e:
            print("저장된 썸네일 메시지 접근 실패:", repr(e))

    try:
        async for msg in button_message.channel.history(limit=10, before=button_message):
            if msg.attachments:
                return msg
    except Exception as e:
        print("썸네일 메시지 검색 실패:", repr(e))

    return None


async def send_log(interaction, original_filename, original_message):
    if interaction.guild is None:
        return

    log_channel = discord.utils.get(interaction.guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel is None:
        print("로그 채널 없음:", LOG_CHANNEL_NAME)
        return

    member = interaction.guild.get_member(interaction.user.id)
    server_name = member.display_name if member else interaction.user.name
    discord_name = interaction.user.name

    channel_id = original_message.channel.id if original_message else ""
    message_id = original_message.id if original_message else ""

    await log_channel.send(
        f"{datetime.now()} | 서버닉네임: {server_name} | 디코ID: @{discord_name} | "
        f"유저고유ID: {interaction.user.id} | 파일: {original_filename} | "
        f"원본채널ID: {channel_id} | 원본문자ID: {message_id}"
    )


class DownloadView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="원본 다운로드", custom_id="download_original_button")
    async def download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "열람하시겠습니까?",
            view=ConfirmView(str(interaction.message.id)),
            ephemeral=True,
        )


class ConfirmView(discord.ui.View):
    def __init__(self, button_message_id):
        super().__init__(timeout=60)
        self.button_message_id = str(button_message_id)

    @discord.ui.button(label="예")
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            button_message = interaction.message
            original_message = None
            original_filename = ""

            contents = load_contents()
            button_data = contents.get("buttons", {}).get(self.button_message_id)

            if button_data:
                original_filename = button_data.get("original_filename", "")

            if button_data and button_data.get("original_message_id") and button_data.get("original_channel_id"):
                try:
                    channel = bot.get_channel(int(button_data["original_channel_id"]))
                    if channel is None:
                        channel = await bot.fetch_channel(int(button_data["original_channel_id"]))

                    original_message = await channel.fetch_message(int(button_data["original_message_id"]))
                except Exception as e:
                    print("버튼 기록 원본 접근 실패:", repr(e))
                    original_message = None

            if original_message is None:
                thumbnail_message = await find_thumbnail_message_for_button(button_message)

                if thumbnail_message and thumbnail_message.attachments:
                    thumbnail_filename = thumbnail_message.attachments[0].filename
                    original_filename = get_original_filename(thumbnail_filename)

                    original_message = await find_original_message_by_filename(
                        interaction.guild,
                        original_filename,
                    )

            if original_message is None:
                await interaction.response.edit_message(content="연결된 원본이 없습니다", view=None)
                return

            if not original_message.attachments:
                await interaction.response.edit_message(content="원본 파일을 찾을 수 없습니다", view=None)
                return

            file = await original_message.attachments[0].to_file()
            await interaction.user.send("원본 파일", file=file)

            await send_log(interaction, original_filename, original_message)

            await interaction.response.edit_message(content="DM 전송 완료", view=None)

        except discord.Forbidden:
            await interaction.response.edit_message(
                content="DM 전송 실패 (DM 차단 또는 민감 콘텐츠 설정 문제)",
                view=None,
            )
        except Exception as e:
            print("DM 전송 처리 실패:", repr(e))
            await interaction.response.edit_message(
                content="DM 전송 실패 (원본 접근 또는 설정 문제)",
                view=None,
            )

    @discord.ui.button(label="아니오")
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="취소됨", view=None)


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    bot.add_view(DownloadView())
    print("봇 온라인")


@bot.command()
async def ping(ctx):
    await ctx.send("배달 준비 완료")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        attachment = message.attachments[0]
        contents = load_contents()

        if message.channel.name == ORIGINAL_CHANNEL_NAME:
            contents["originals"][attachment.filename] = {
                "message_id": message.id,
                "channel_id": message.channel.id,
                "user_id": message.author.id,
            }
            save_contents(contents)
            print("원본 저장:", attachment.filename)
            return

        original_filename = get_original_filename(attachment.filename)
        original_message = await find_original_message_by_filename(message.guild, original_filename)
        original_data = None

        if original_message:
            original_data = {
                "channel_id": original_message.channel.id,
                "message_id": original_message.id,
            }

        content_id = str(message.id)
        contents["thumbnails"][content_id] = {
            "channel_id": message.channel.id,
            "user_id": message.author.id,
            "thumbnail_filename": attachment.filename,
            "thumbnail_message_id": message.id,
            "original_filename": original_filename,
            "original_channel_id": original_data["channel_id"] if original_data else None,
            "original_message_id": original_data["message_id"] if original_data else None,
        }
        save_contents(contents)

        button_message = await message.channel.send(view=DownloadView())

        contents = load_contents()
        contents["buttons"][str(button_message.id)] = {
            "thumbnail_message_id": message.id,
            "thumbnail_filename": attachment.filename,
            "original_filename": original_filename,
            "original_channel_id": original_data["channel_id"] if original_data else None,
            "original_message_id": original_data["message_id"] if original_data else None,
        }
        save_contents(contents)

        print("썸네일:", attachment.filename, "원본:", original_filename)

    await bot.process_commands(message)


TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN 환경변수가 설정되지 않았습니다.")

bot.run(TOKEN)
