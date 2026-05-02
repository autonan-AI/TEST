import os
import json
from pathlib import Path
from datetime import datetime

import discord
from discord.ext import commands

ORIGINAL_CHANNEL_NAME = "크리에이터원본"

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

CONTENTS_FILE = DATA_DIR / "contents.json"
VIEW_LOG_FILE = LOG_DIR / "view_log.txt"


def load_contents():
    if CONTENTS_FILE.exists():
        with open(CONTENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
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


async def get_original_message(channel_id, message_id):
    channel = bot.get_channel(int(channel_id))
    if channel is None:
        channel = await bot.fetch_channel(int(channel_id))
    return await channel.fetch_message(int(message_id))


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
        contents = load_contents()
        button_data = contents.get("buttons", {}).get(self.button_message_id)

        if not button_data:
            await interaction.response.edit_message(content="연결된 원본이 없습니다", view=None)
            return

        try:
            original_message = await get_original_message(
                button_data["original_channel_id"],
                button_data["original_message_id"],
            )

            if not original_message.attachments:
                await interaction.response.edit_message(content="원본 파일을 찾을 수 없습니다", view=None)
                return

            file = await original_message.attachments[0].to_file()
            await interaction.user.send("원본 파일", file=file)

            with open(VIEW_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.now()} | {interaction.user} | {interaction.user.id} | "
                    f"{interaction.user.display_name} | "
                    f"{button_data.get('original_filename', '')} | "
                    f"{button_data['original_channel_id']} | {button_data['original_message_id']}\n"
                )

            await interaction.response.edit_message(content="DM 전송 완료", view=None)

        except discord.Forbidden:
            await interaction.response.edit_message(
                content="DM 전송 실패 (DM 차단 또는 민감 콘텐츠 설정 문제)",
                view=None,
            )
        except Exception:
            await interaction.response.edit_message(
                content="DM 전송 실패 (DM 차단 또는 설정 문제)",
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
        original_data = None
        if original_filename and original_filename in contents["originals"]:
            original_data = contents["originals"][original_filename]

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
