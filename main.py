# SPDX-FileCopyrightText: 2020 Collin Cunningham for Adafruit Industries
#
# SPDX-License-Identifier: MIT

from adafruit_datetime import datetime, timedelta
import time
import board
import alarm
import ipaddress
from adafruit_magtag.magtag import MagTag
import adafruit_connection_manager
from digitalio import DigitalInOut, Direction, Pull

import adafruit_requests
import wifi
import ssl
import neopixel
import socketpool

# from adafruit_led_animation.sequence import AnimationSequence
# from adafruit_led_animation.group import AnimationGroup
# from adafruit_led_animation.animation.comet import Comet
# from adafruit_led_animation.animation.sparkle import Sparkle
# from adafruit_led_animation.animation.chase import Chase
# from adafruit_led_animation.animation.blink import Blink
# from adafruit_led_animation.animation.pulse import Pulse
#
# from adafruit_led_animation.animation.pulse import Pulse
# from adafruit_led_animation.animation.sparkle import Sparkle
from adafruit_led_animation.color import (
    RED,
    GREEN,
    BLUE,
    CYAN,
    WHITE,
    OLD_LACE,
    PURPLE,
    MAGENTA,
    YELLOW,
    ORANGE,
    PINK,
)
import os


magtag = MagTag()

# The strip LED brightness, where 0.0 is 0% (off) and 1.0 is 100% brightness, e.g. 0.3 is 30%
# strip_pixel_brightness = 1
# The MagTag LED brightness, where 0.0 is 0% (off) and 1.0 is 100% brightness, e.g. 0.3 is 30%.
magtag_pixel_brightness = 0.1


magtag_pixels = magtag.peripherals.neopixels
magtag_pixels.brightness = magtag_pixel_brightness
FLOOR_LAMP_ENTITY = os.getenv("FLOOR_LAMP_ENTITY")
SHELF_LAMP_ENTITY = os.getenv("SHELF_LAMP_ENTITY")
VACUUM_ENTITY = os.getenv("VACUUM_AUTOMATION_ID")
HA_URL = os.getenv("HOME_ASSISTANT_URL")
TOKEN = os.getenv("HOME_ASSISTANT_TOKEN")
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
URL = f"{HA_URL}/api/services/switch/toggle"
VACUUM_URL = f"{HA_URL}/api/states/{VACUUM_ENTITY}"

TIME_URL = f"https://io.adafruit.com/api/v2/{os.getenv('AIO_USERNAME')}/integrations/time/strftime?x-aio-key={os.getenv('AIO_KEY')}&tz={os.getenv('TIMEZONE')}"
TIME_URL += "&fmt=%25Y-%25m-%25d+%25H%3A%25M%3A%25S.%25L+%25j+%25u+%25z+%25Z"


USE_AMPM_TIME = False
last_sync = None
last_minute = None

magtag.graphics.set_background("/background.bmp")

magtag.peripherals.neopixel_disable = False
magtag_pixels.fill(PINK)
magtag_pixels.show()

print(f"Connecting to {os.getenv('CIRCUITPY_WIFI_SSID')}")
wifi.radio.connect(
    os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD")
)
print(f"Connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")
print(f"My IP address: {wifi.radio.ipv4_address}")

pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

mid_x = magtag.graphics.display.width // 2 - 1
TXT_MAIN = magtag.add_text(
    text_font="fonts/Arial-12.pcf",
    text_position=(mid_x, 32),
    text_anchor_point=(0.5, 0),
    is_data=False,
)
magtag.set_text("Lights UNKNOWN", index=TXT_MAIN, auto_refresh=False)

TXT_SECONDARY = magtag.add_text(
    text_font="fonts/Arial-12.pcf",
    text_position=(mid_x, 52),
    text_anchor_point=(0.5, 0),
    is_data=False,
)
magtag.set_text("Last Vacuum UNKNOWN", index=TXT_SECONDARY, auto_refresh=False)

TXT_BTNA = magtag.add_text(
    text_font="fonts/Arial-12.pcf",
    text_position=(12, magtag.graphics.display.height - 16),
    text_color=0x500000,
    is_data=False,
)
# magtag.set_text("lamp", index=TXT_BTNA, auto_refresh=False)


TXT_BTNB = magtag.add_text(
    text_font="fonts/Arial-Bold-12.bdf",
    text_position=(78, magtag.graphics.display.height - 16),
    is_data=False,
)
# magtag.set_text("vacuum bath", index=TXT_BTNB, auto_refresh=False)

TXT_BTNC = magtag.add_text(
    text_font="fonts/Arial-Bold-12.bdf",
    text_position=(148, magtag.graphics.display.height - 16),
    is_data=False,
)
# magtag.set_text("wake", index=TXT_BTNC, auto_refresh=False)

TXT_BATT = magtag.add_text(
    # text_font="fonts/Arial-12.pcf",
    text_position=(40, 8),
    text_anchor_point=(0, 0),
    is_data=False,
)
magtag.set_text(
    f"{magtag.peripherals.battery:.2f}v", index=TXT_BATT, auto_refresh=False
)

TXT_WIFI = magtag.add_text(
    # text_font="fonts/Arial-12.pcf",
    text_position=(200, 8),
    text_anchor_point=(0, 0),
    is_data=False,
)
magtag.set_text(
    str(os.getenv("CIRCUITPY_WIFI_SSID")), index=TXT_WIFI, auto_refresh=False
)

ENTITY_TXT_MAP = {
    FLOOR_LAMP_ENTITY: TXT_MAIN,
    SHELF_LAMP_ENTITY: TXT_MAIN,
}


refresh_rate = 60
timestamp = None
animation = None
# [{"entity_id":"switch.power_strip_switch","state":"on","attributes":{"friendly_name":"Power Strip Switch"},"last_changed":"2024-04-21T04:46:40.462644+00:00","last_updated":"2024-04-21T04:46:40.462644+00:00","context":{"id":"01HVZFMK78NEMR1G5ZDHK4NPRR","parent_id":null,"user_id":"e788c2c6eff6464686c800059f9cd745"}}] 200


def format_datetime(then: datetime) -> str:
    weekdays = [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
    ]

    weekday = weekdays[then.weekday()]
    hour = then.hour % 12
    hour = 12 if hour == 0 else hour
    minute = then.minute
    am_pm = "pm" if then.hour >= 12 else "am"
    formatted_time = f"{weekday} {hour}:{minute:02d} {am_pm}"
    return formatted_time


def set_lamp_txt(j):
    try:
        print(j)
        for r_entity in j:
            for entity, txt in ENTITY_TXT_MAP.items():
                if r_entity["entity_id"] == entity:
                    lamp_on = r_entity["state"] == "on"
                    magtag.set_text(
                        "Lights: On" if lamp_on else "Lights: Off",
                        index=txt,
                        auto_refresh=False,
                    )
    except Exception as e:
        print(f"Unable to get status: {e}")


def deep_sleep_until_button():
    print("pre sleep")
    # magtag.peripherals.neopixel_disable = True
    button_pins = [board.BUTTON_A, board.BUTTON_B]  # , board.BUTTON_C, board.BUTTON_D]
    btn_alarms = []
    for button in magtag.peripherals.buttons:
        button.deinit()
    for pin in button_pins:
        btn_alarms.append(alarm.pin.PinAlarm(pin=pin, value=False, pull=True))
    alarm.exit_and_deep_sleep_until_alarms(*btn_alarms)
    # unreachable

    magtag.buttons = []
    for pin in button_pins:
        switch = DigitalInOut(pin)
        switch.direction = Direction.INPUT
        switch.pull = Pull.UP
        magtag.buttons.append(switch)

    print("post sleep")


def a_button():

    # ping_ip = ipaddress.IPv4Address("8.8.8.8")
    # ping = wifi.radio.ping(ip=ping_ip)
    # print(ping)

    for entity in ENTITY_TXT_MAP.keys():
        r = requests.post(URL, headers=headers, json={"entity_id": entity})
        set_lamp_txt(r.json())
        print(f"{entity} -> {r.status_code}")


def b_button():
    vacuum_now()


def get_current_time() -> datetime:
    try:
        response = requests.get(TIME_URL)
        pattern = "%Y-%m-%d %H:%M:%S.%f %j %u %z %Z"
        current_time = datetime.strptime(response.text, pattern)
        return current_time
    except Exception as e:
        print(f"unable to load time {e}")
        return None


def vacuum_now():
    endpoint = f"{HA_URL}/api/services/automation/trigger"
    data = {"entity_id": VACUUM_ENTITY}
    r = requests.post(endpoint, headers=headers, json=data)
    print(f"vacuum post: {r}")


def get_last_vacuum(set_text=False) -> str:
    try:
        r = requests.get(VACUUM_URL, headers=headers)
        print(r)
        j = r.json()
        last_time = j["attributes"]["last_triggered"]
        # utc_time = datetime.strptime(last_time, "%Y-%m-%dT%H:%M:%S.%f%z")
        utc_time = datetime.fromisoformat(last_time)
        localtime = utc_time - timedelta(hours=4)
        print(localtime)
        print(get_current_time)
        text = format_datetime(localtime)
        if set_text:
            magtag.set_text(
                f"Last clean: {text}",
                index=TXT_SECONDARY,
                auto_refresh=False,
            )

    except Exception as e:
        print(f"unable to load last vacuum {e}")
        return "Unknown"


def lights_currently_on(set_text=False) -> bool:
    endpoint = f"{HA_URL}/api/states/{FLOOR_LAMP_ENTITY}"
    try:
        r = requests.get(endpoint, headers=headers)
        j = r.json()
        if set_text:
            set_lamp_txt([j])
        return r["state"] == "on"

    except Exception as e:
        print(f"unable to load lights {e}")
    return False


def handle_buttons():
    global animation

    if magtag.peripherals.button_a_pressed:
        # animation = chase
        a_button()
    elif magtag.peripherals.button_b_pressed:
        # animation = blink
        deep_sleep_until_button()
    elif magtag.peripherals.button_c_pressed:
        # animation = comet
        pass
    elif magtag.peripherals.button_d_pressed:
        # animation = sparkle
        pass

        # magtag.peripherals.neopixel_disable = False
    while magtag.peripherals.any_button_pressed:
        pass
        # animation.animate()

        # magtag.peripherals.neopixel_disable = True


print(alarm.wake_alarm)
# magtag.set_text(f"BATT {magtag.peripherals.battery:.2f}v", index=1, auto_refresh=False)
if alm := alarm.wake_alarm:
    if alm.pin == board.BUTTON_A:
        print("Wake via button a")
        a_button()
    elif alm.pin == board.BUTTON_B:
        print("Wake btn B")
        b_button()

        # while True:
        # handle_buttons()
    else:
        print("Other wake")

lights_currently_on(True)
get_last_vacuum(True)
magtag.refresh()
deep_sleep_until_button()
# handle_buttons()

# while True:
#    magtag.set_text(f"BATT {magtag.peripherals.battery}v", index=1, auto_refresh=False)
#
#    if not last_sync or (time.monotonic() - last_sync) > 3600:
#        # at start or once an hour
#        # magtag.network.get_local_time()
#        if not last_sync and not alarm.wake_alarm:
#            magtag.refresh()
#
#        last_sync = time.monotonic()
#
#    # get current time
#    #now = time.localtime()
#
#    # minute updated, refresh display!
#    #if not last_toronto_time = utc_time.astimezone(toronto_tz)
#   handle_buttons()
