from machine import Pin, I2C, PWM
import ssd1306
import time

# ============================================
# HARDWARE SETUP
# ============================================

green = Pin(18, Pin.OUT)
yellow = Pin(19, Pin.OUT)
red = Pin(20, Pin.OUT)
blue = Pin(21, Pin.OUT)

buzzer = PWM(Pin(15))
buzzer.duty_u16(0)

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# ============================================
# HELPERS
# ============================================

def leds_off():
    green.value(0)
    yellow.value(0)
    red.value(0)
    blue.value(0)

def beep(ms=200):
    buzzer.freq(2000)
    buzzer.duty_u16(32768)
    time.sleep_ms(ms)
    buzzer.duty_u16(0)

def show(l1, l2="", l3="", l4=""):
    oled.fill(0)
    oled.text("CYPHEX SENTINEL", 0, 0)
    oled.hline(0, 10, 128, 1)
    oled.text(l1, 0, 16)
    oled.text(l2, 0, 28)
    oled.text(l3, 0, 40)
    oled.text(l4, 0, 52)
    oled.show()

# ============================================
# BOOT SEQUENCE
# ============================================
print("CYPHEX Sentinel v1.0 Started!")

show("Booting...", "", "", "")
for led in [green, yellow, red, blue]:
    led.value(1)
    time.sleep_ms(150)
for led in [green, yellow, red, blue]:
    led.value(0)
    time.sleep_ms(100)

beep(100)
time.sleep_ms(50)
beep(100)

# ============================================
# SCAN CYCLE LOOP
# ============================================
while True:
    # Stage 1: Recon
    leds_off()
    blue.value(1)
    show("SCANNING...", "Agent 01: Recon", "Headers + Paths", "")
    print("[STAGE 1] Recon Agent")
    time.sleep(3)

    # Stage 2: Crawler
    show("SCANNING...", "Agent 02: Crawler", "14 endpoints", "8 forms found")
    print("[STAGE 2] Crawler Agent")
    time.sleep(3)

    # Stage 3: Parallel Attack
    attacks = ["SQLi", "XSS", "Auth", "CMDi", "LFI", "Logic"]
    for i, name in enumerate(attacks):
        show("ATTACKING...", "Agent {:02d}: {}".format(i+3, name), "Parallel mode", "{}/6 agents".format(i+1))
        print("[STAGE 3] Agent " + name)
        blue.value(0)
        time.sleep_ms(200)
        blue.value(1)
        time.sleep_ms(300)

    # Stage 4: AI Analysis
    leds_off()
    blue.value(1)
    yellow.value(1)
    show("AI ANALYSIS", "Mistral 7B", "RTX 3050 GPU", "Processing...")
    print("[STAGE 4] AI Analysis")
    time.sleep(4)

    # CRITICAL VULNS FOUND!
    leds_off()
    red.value(1)
    show("!! CRITICAL !!", "3 Vulns Found!", "SQLi, XSS, Auth", "CVSS: 9.8")
    print("[ALERT] 3 CRITICAL vulnerabilities!")
    beep(500)
    time.sleep_ms(300)
    beep(300)
    time.sleep(3)

    # Stage 5: Patching
    leds_off()
    yellow.value(1)
    show("PATCHING...", "Agent 10: Patch", "Generating fixes", "3/3 patches")
    print("[STAGE 5] Patch Agent")
    time.sleep(3)

    # Secure
    leds_off()
    green.value(1)
    show("SECURE", "All patched!", "Score: 92/100", "Next scan: 2h")
    print("[STATUS] SECURE")
    time.sleep(5)

    print("--- Restarting cycle ---")
