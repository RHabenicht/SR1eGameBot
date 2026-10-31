import unittest
from types import SimpleNamespace

from test_storage import MemoryStore
from sr1egamebot.ammo import AmmoService, parse_ammo, parse_guns, save_ammo, save_guns
from sr1egamebot.crypto_compat import AESCipher
from sr1egamebot.repository import LegacyRepository


class AmmoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = LegacyRepository(
            MemoryStore(), AESCipher(bytes([7]) * 32, bytes([8]) * 16)
        )
        self.service = AmmoService(self.repository)

    def message(self, channel="gm-screen", guild=True):
        replies = []
        async def reply(value): replies.append(value)
        msg = SimpleNamespace(
            guild=SimpleNamespace(id="server") if guild else None,
            channel=SimpleNamespace(id=channel),
            author=SimpleNamespace(id="gm"),
            reply=reply,
        )
        return msg, replies

    def test_legacy_ammo_and_gun_serialization_round_trip(self):
        ammo = [{"qtyContainers": "2", "containerType": "clip", "qtyRounds": "10",
                 "roundType": "AP", "maxRounds": "12"}]
        guns = [{"name": "Predator", "maxROF": "2", "ammoContainerType": "clip",
                 "ammoCapacity": "12", "ammoTypeLoaded": "not loaded", "ammoQtyLoaded": "0",
                 "ammoTypes": "AP regular"}]
        self.assertEqual(parse_ammo(save_ammo(ammo)), ammo)
        self.assertEqual(parse_guns(save_guns(guns)), guns)

    async def test_add_reload_fire_and_round_trip_through_legacy_files(self):
        msg, replies = self.message()
        await self.service.command(msg, ["addgun", "Predator", "2", "clip", "12", "AP", "regular"])
        await self.service.command(msg, ["addammo", "2", "clip", "10", "AP", "12"])
        await self.service.command(msg, ["reload", "Predator"])
        self.assertEqual(replies[-1], "Your weapon was reloaded.")

        folder = await self.repository.find_user_folder("server", "gm-screen", "gm")
        gun_file = await self.repository.find_string("gunList", str(folder["_id"]))
        ammo_file = await self.repository.find_string("ammoList", str(folder["_id"]))
        guns = parse_guns(await self.repository.get_string(str(gun_file["_id"])))
        ammo = parse_ammo(await self.repository.get_string(str(ammo_file["_id"])))
        self.assertEqual((guns[0]["ammoTypeLoaded"], guns[0]["ammoQtyLoaded"]), ("AP", "10"))
        self.assertEqual(ammo, [{"qtyContainers": "1", "containerType": "clip",
                                "qtyRounds": "10", "roundType": "AP", "maxRounds": "12"}])

        await self.service.command(msg, ["fire", "Predator", "2"])
        guns = parse_guns(await self.repository.get_string(str(gun_file["_id"])))
        self.assertEqual(guns[0]["ammoQtyLoaded"], "8")
        self.assertIn("You fired 2 APs from your Predator.", replies[-1])

    async def test_reload_uses_fullest_compatible_magazine_and_dm_is_rejected(self):
        msg, replies = self.message()
        await self.service.command(msg, ["addgun", "Predator", "2", "clip", "12", "AP"])
        await self.service.command(msg, ["addammo", "1", "clip", "4", "AP", "12"])
        await self.service.command(msg, ["addammo", "1", "clip", "10", "AP", "12"])
        await self.service.command(msg, ["reload", "Predator"])
        folder = await self.repository.find_user_folder("server", "gm-screen", "gm")
        gun_file = await self.repository.find_string("gunList", str(folder["_id"]))
        guns = parse_guns(await self.repository.get_string(str(gun_file["_id"])))
        self.assertEqual(guns[0]["ammoQtyLoaded"], "10")

        dm, dm_replies = self.message(guild=False)
        await self.service.command(dm, ["list"])
        self.assertEqual(dm_replies, ["This command doesn't work via DM. You must be in a server channel."])


if __name__ == "__main__":
    unittest.main()
