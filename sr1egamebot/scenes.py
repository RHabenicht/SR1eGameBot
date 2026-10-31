"""Prepared scene and private-GM-channel commands."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .repository import LegacyRepository


class SceneService:
    def __init__(
        self,
        repository: LegacyRepository,
        *,
        client: Any | None = None,
        add_status: Callable[[Any, str], Any] = lambda _msg, text: text,
        log: Callable[[str], Any] = lambda _message: None,
    ) -> None:
        self._repository = repository
        self._client = client
        self._add_status = add_status
        self._log = log

    async def check_channel(self, msg: Any) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        channel = await self._repository.get_play_channel(
            msg.guild.id, msg.channel.id, msg.author.id
        )
        await self._reply(msg, f"Your current play channel is set to <#{channel}>.")

    async def set_channel(self, msg: Any, args: Sequence[str]) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        if len(args) != 1:
            await self._reply(msg, "This command requires one (and only one) argument, a channel link.")
            return
        token = args[0]
        if not (token.startswith("<#") and token.endswith(">")):
            await self._reply(msg, "Error: make sure this command is followed only by a link to a channel.")
            return
        channel_id = token[2:-1]
        await self._repository.set_play_channel(
            msg.guild.id, msg.channel.id, msg.author.id, channel_id
        )
        await self._reply(
            msg,
            f"Play channel is now set to <#{channel_id}>. You can now issue commands for initiative and "
            f"scenes in this channel, and they will be saved to <#{channel_id}>.",
        )

    async def set_scene(self, msg: Any, args: Sequence[str]) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        if not args:
            await self._reply(msg, "Please provide a scene name and its text.")
            return
        channel = await self._play_channel(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, channel, msg.author.id)
        name = args[0]
        tail = list(args[1:])
        if tail and tail[0][:4].lower() == "http":
            music = tail.pop(0)
        else:
            music = ""
        text = " ".join(tail)
        await self._repository.set_string(f"gmScene_{name}", str(folder), f"{name}\n|||\n{music}\n|||\n{text}")
        record = await self._repository.find_string(f"gmScene_{name}", str(folder))
        scene_id = str(record["_id"])
        rows = await self._scene_rows(str(folder))
        existing = next((row for row in rows if row["name"] == name), None)
        if existing is None:
            rows.append({"name": name, "dbID": scene_id})
        else:
            existing["dbID"] = scene_id
        await self._save_scene_rows(str(folder), rows)
        await self._reply(msg, f"You now have {len(rows)} scenes in channel <#{channel}>.")
        self._log(f"🎲🎲🎲 {msg.guild.id}/{msg.channel.id}({channel})/{msg.author.id}")

    async def delete_scenes(self, msg: Any, args: Sequence[str]) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        channel = await self._play_channel(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, channel, msg.author.id)
        if not args:
            await self._reply(msg, "This command requires one or more names of scenes.")
            return
        rows = await self._scene_rows(str(folder))
        for name in args:
            file = await self._repository.find_string(f"gmScene_{name}", str(folder))
            if file is None:
                await self._reply(msg, f"The scene named {name} wasn't found.")
                continue
            await self._repository.delete_string(str(file["_id"]))
            rows = [row for row in rows if row["name"] != name]
            await self._save_scene_rows(str(folder), rows)
        await self._reply(msg, f"You now have {len(rows)} scenes in channel <#{channel}>.")

    async def get_scene(self, msg: Any, args: Sequence[str]) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        channel = await self._play_channel(msg)
        if len(args) != 1:
            await self._reply(msg, "Error: this command requires a single argument, the name of the scene. "
                              f"Try !listscenes for a list of your scenes in channel {channel}.")
            return
        folder = await self._repository.ensure_user_folder(msg.guild.id, channel, msg.author.id)
        file = await self._repository.find_string(f"gmScene_{args[0]}", str(folder))
        content = await self._repository.get_string(str(file["_id"])) if file else ""
        parts = content.split("\n|||\n")
        if not content or len(parts) < 3:
            await self._reply(msg, "That scene wasn't found.")
            return
        scene_name, music, text = parts[0], parts[1], "\n|||\n".join(parts[2:])
        client = self._client or msg.client
        destination = client.get_channel(int(channel))
        if destination is None:
            destination = await client.fetch_channel(int(channel))
        music_text = f"\n\nSoundtrack:\n{music}" if music else ""
        await destination.send(f"{text}{music_text}")
        await self._reply(msg, f'Scene "{scene_name}" was just deployed in channel <#{channel}>.')

    async def list_scenes(self, msg: Any) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        channel = await self._play_channel(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, channel, msg.author.id)
        rows = await self._scene_rows(str(folder))
        if rows:
            names = "\n".join(row["name"] for row in rows)
            await self._reply(msg, f"Your scene names in channel <#{channel}> are: ```\n{names}\n```")
        else:
            await self._reply(msg, f"You have no scenes yet in channel <#{channel}>.")

    async def _play_channel(self, msg: Any) -> str:
        return await self._repository.get_play_channel(msg.guild.id, msg.channel.id, msg.author.id)

    async def _scene_rows(self, folder_id: str) -> list[dict[str, str]]:
        record = await self._repository.find_string("gmSceneList", folder_id)
        content = await self._repository.get_string(str(record["_id"])) if record else ""
        rows = []
        for entry in content.split("\n|||||\n"):
            if not entry:
                continue
            fields = entry.split("\n|||\n")
            if len(fields) > 1:
                rows.append({"name": fields[0], "dbID": fields[1]})
        return rows

    async def _save_scene_rows(self, folder_id: str, rows: list[dict[str, str]]) -> None:
        content = "".join(f'{row["name"]}\n|||\n{row["dbID"]}\n|||||\n' for row in rows)
        await self._repository.set_string("gmSceneList", folder_id, content)

    async def _reply(self, msg: Any, text: str) -> None:
        await msg.reply(await _await(self._add_status(msg, text)))

    @staticmethod
    def _in_guild(msg: Any) -> bool:
        return getattr(msg, "guild", None) is not None


async def _await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
