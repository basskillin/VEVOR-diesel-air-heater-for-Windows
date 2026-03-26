import asyncio
import sys
from bleak import BleakClient, BleakScanner

WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"


class Heater5199:
    def __init__(self, device_identifier: str):
        self.device_identifier = device_identifier.strip()
        self.client = None
        self.last_rx = None
        self.notify_event = asyncio.Event()

    async def resolve_device(self):
        devices = await BleakScanner.discover(timeout=8.0)

        for d in devices:
            if (d.address or "").lower() == self.device_identifier.lower():
                return d

        needle = self.device_identifier.lower()
        for d in devices:
            if needle in (d.name or "").lower():
                return d

        raise RuntimeError(f"Could not find device: {self.device_identifier}")

    def notify_handler(self, sender, data: bytearray):
        self.last_rx = bytes(data)
        self.notify_event.set()
        print(f"RX: {self.last_rx.hex(' ')}")
        self.decode_status(self.last_rx)

    async def connect(self):
        dev = await self.resolve_device()
        self.client = BleakClient(dev.address)
        await self.client.connect()

        if not self.client.is_connected:
            raise RuntimeError("Connect failed")

        await self.client.start_notify(NOTIFY_UUID, self.notify_handler)
        print(f"Connected: {dev.address} {dev.name}")
        print("Notifications enabled on FFF1")

    async def disconnect(self):
        if self.client:
            try:
                if self.client.is_connected:
                    try:
                        await self.client.stop_notify(NOTIFY_UUID)
                    except Exception:
                        pass
                    await self.client.disconnect()
            finally:
                self.client = None
                print("Disconnected")

    @staticmethod
    def checksum8(data: bytes) -> int:
        return sum(data) & 0xFF

    def make_baab(self, cmd: int, d1: int = 0x00, d2: int = 0x00, d3: int = 0x00) -> bytes:
        frame = bytes([0xBA, 0xAB, 0x04, cmd, d1, d2, d3])
        return frame + bytes([self.checksum8(frame)])

    async def send(self, payload: bytes, wait_reply: float = 2.0):
        if not self.client or not self.client.is_connected:
            raise RuntimeError("Not connected")

        self.last_rx = None
        self.notify_event.clear()

        try:
            await self.client.write_gatt_char(WRITE_UUID, payload, response=True)
        except Exception:
            await self.client.write_gatt_char(WRITE_UUID, payload, response=False)

        print(f"TX: {payload.hex(' ')}")

        try:
            await asyncio.wait_for(self.notify_event.wait(), timeout=wait_reply)
            return self.last_rx
        except asyncio.TimeoutError:
            print("No reply")
            return None

    def decode_status(self, frame: bytes):
        # Conservative decoder: only prints values we have evidence for.
        if len(frame) < 8:
            return

        if frame[0] != 0xAB or frame[1] != 0xBA:
            return

        if frame[3] != 0xCC:
            return

        print("Decoded:")
        print(f"  header: AB BA")
        print(f"  type:   0x{frame[3]:02X}")

        # Based on observed frames and protocol family:
        state = frame[4] if len(frame) > 4 else None
        mode = frame[5] if len(frame) > 5 else None
        level_like = frame[6] if len(frame) > 6 else None

        state_map = {
            0x00: "off",
            0x01: "heating",
            0x02: "cooling",
            0x04: "ventilation",
        }

        state_text = state_map.get(state, f"unknown(0x{state:02X})" if state is not None else "n/a")
        print(f"  state:  {state_text}")
        print(f"  mode:   0x{mode:02X}" if mode is not None else "  mode:   n/a")
        print(f"  level?: 0x{level_like:02X}" if level_like is not None else "  level?: n/a")

        # Heuristic fields for your clone, printed but not claimed as final truth
        if len(frame) > 11:
            print(f"  byte9:  0x{frame[9]:02X}")
            print(f"  byte10: 0x{frame[10]:02X}")
            print(f"  byte11: 0x{frame[11]:02X}")

        if len(frame) > 20:
            print(f"  csum:   0x{frame[-1]:02X}")

    async def status(self):
        return await self.send(self.make_baab(0xCC))

    async def on(self):
        return await self.send(self.make_baab(0xBB, 0xA1, 0x00, 0x00))

    async def vent(self):
        return await self.send(self.make_baab(0xBB, 0xA4, 0x00, 0x00))

    async def off(self):
        # known safe-ish app-like sequence for this protocol family
        await self.vent()
        await asyncio.sleep(0.6)
        await self.on()
        await asyncio.sleep(0.6)
        return await self.vent()

    async def up(self):
        return await self.send(self.make_baab(0xBB, 0xA2, 0x00, 0x00))

    async def down(self):
        return await self.send(self.make_baab(0xBB, 0xA3, 0x00, 0x00))

    async def raw(self, hexstr: str):
        payload = bytes.fromhex(hexstr.replace(" ", ""))
        return await self.send(payload)


async def main():
    if len(sys.argv) < 2:
        print('Usage: py heater5199_windows.py "Heater5199"')
        return

    heater = Heater5199(sys.argv[1])

    try:
        await heater.connect()

        print("\nCommands:")
        print("  status")
        print("  on")
        print("  off")
        print("  vent")
        print("  up")
        print("  down")
        print("  raw <hex>")
        print("  exit")

        while True:
            cmd = await asyncio.to_thread(input, "> ")
            cmd = cmd.strip().lower()

            if cmd == "exit":
                break
            elif cmd == "status":
                await heater.status()
            elif cmd == "on":
                await heater.on()
            elif cmd == "off":
                await heater.off()
            elif cmd == "vent":
                await heater.vent()
            elif cmd == "up":
                await heater.up()
            elif cmd == "down":
                await heater.down()
            elif cmd.startswith("raw "):
                await heater.raw(cmd[4:])
            else:
                print("Unknown command")

            await asyncio.sleep(0.6)

    finally:
        await heater.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
