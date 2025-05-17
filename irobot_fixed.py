import asyncio
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_UUID = "0bd51777-e7cb-469b-8e4d-2742f1ba77cc"
COMMAND_UUID = "e7add780-b042-4876-aae1-112855353cc2"
PAYLOAD_UUID = "e7add780-b042-4876-aae1-112855353cc1"
READ_UUID = "e7add780-b042-4876-aae1-112855353cc3"
NOTIFY_UUID = "e7add780-b042-4876-aae1-112855353cc4"

IROBOT_NAMES = {"iRobot Braava", "iRobot Braav", "Altadena"}

COMMANDS = {
    'start': [0x17, 0x04, 0x1B, 0x00],
    'dock': [0x04, 0x04, 0x09, 0x01],
    'status': [0x16, 0x03, 0x19]
}

last_notification_value = None

async def notification_handler(sender, data):
    global last_notification_value
    try:
        current_value = int.from_bytes(data[:2], 'little')
        if last_notification_value is not None and current_value == last_notification_value + 1:
            return
        last_notification_value = current_value
        logger.info(f"Notification: {data.hex(' ')}")
    except Exception as e:
        logger.error(f"Notification error: {e}")

async def scan_devices():
    logger.info("Scanning for iRobot devices...")
    async with BleakScanner() as scanner:
        await asyncio.sleep(8.0)
        for _, (device, ad_data) in scanner.discovered_devices_and_advertisement_data.items():
            if (SERVICE_UUID.lower() in [s.lower() for s in ad_data.service_uuids] or device.name in IROBOT_NAMES):
                logger.info(f"Found: {device.name} @ {device.address}")
                return device
    return None

async def send_fsm(client, cmd):
    try:
        if len(cmd) > 20:
            logger.error("Command too long")
            return False

        await client.write_gatt_char(COMMAND_UUID, bytearray([0x01, 0x00, 0x01, 0xF4]))
        await asyncio.sleep(0.08)
        await client.write_gatt_char(COMMAND_UUID, bytearray([0x0D, 0x00, 0x00, len(cmd)]))
        await asyncio.sleep(0.08)
        padded = cmd + [0x00] * (20 - len(cmd))
        await client.write_gatt_char(PAYLOAD_UUID, bytearray(padded), response=False)
        await asyncio.sleep(0.08)
        checksum = sum(cmd) & 0xFFFFFF
        chks = [0x04, 0x00, (checksum >> 16) & 0xFF, checksum & 0xFF]
        await client.write_gatt_char(COMMAND_UUID, bytearray(chks))
        await asyncio.sleep(0.08)
        await client.write_gatt_char(COMMAND_UUID, bytearray([0x05, 0x00, 0x00, 0x00]))
        await asyncio.sleep(0.08)
        await client.write_gatt_char(COMMAND_UUID, bytearray([0x08, 0x00, 0x00, len(cmd)]))
        await asyncio.sleep(0.08)
        await client.write_gatt_char(COMMAND_UUID, bytearray([0x0E, 0x00, 0x00, len(cmd)]))
        await asyncio.sleep(0.08)
        return True
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return False

async def connect_and_control(device):
    async with BleakClient(device.address) as client:
        await client.start_notify(NOTIFY_UUID, notification_handler)
        logger.info("Connected and notifications enabled")
        while True:
            cmd = input("Enter command: ").strip().lower()
            if cmd == 'q':
                break
            if cmd not in COMMANDS:
                logger.info("Invalid command")
                continue
            logger.info(f"Sending command: {bytes(COMMANDS[cmd]).hex(' ')}")
            await send_fsm(client, COMMANDS[cmd])
            await asyncio.sleep(1)

async def main():
    try:
        device = await scan_devices()
        if not device:
            logger.info("No iRobot device found.")
            return
        await connect_and_control(device)
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    except BleakError as e:
        logger.error(f"BLE error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
