import rpi_ws281x as npx
import colorsys
import random
import time
import multiprocessing
import queue

ADDR_MAP = {'A': 24, 'B': 23, 'C': 22, 'D': 21, 'E': 20,
            'F': 15, 'G': 16, 'H': 17, 'I': 18, 'J': 19,
            'K': 10, 'L': 11, 'M': 12, 'N': 13, 'O': 14,
            'P': 5, 'R': 6, 'S': 7, 'T': 8, 'U': 9,
            'V': 4, 'W': 3, 'X': 2, 'Y': 1, 'Z': 0}

# LED strip configuration:
LED_COUNT      = 25      # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 9      # DMA channel to use for genera ting signal (try 10)
LED_BRIGHTNESS = 255     # Set to 0 for darkest aand 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

CHAR_ON_PERIOD = 1.3
DELAY_BETWEEN_CHARS = 0.2
MESSAGE_DELAY = 1.5


def random_color():
    h = random.uniform(0.0, 1.0)
    s = random.uniform(0.5, 1.0)
    v = random.uniform(0.7, 1.0)
    color = colorsys.hsv_to_rgb(h, s, v)
    rgb255 = [int(x * 255) for x in color]
    return npx.Color(*rgb255)


def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return npx.Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return npx.Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return npx.Color(0, pos * 3, 255 - pos * 3)


class Display:
    def __init__(self):
        self.strip = npx.Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        self.strip.begin()

        self.in_queue = queue.PriorityQueue()
        self.out_queue = queue.Queue()

        self.animation_process = None

    def show_char(self, c, color=None):
        led = ADDR_MAP.get(c, 26)  # 26 is out of range, nothing will light up
        self.strip.setPixelColor(led, color if color else random_color())
        self.strip.show()

        time.sleep(CHAR_ON_PERIOD)

        self.strip.setPixelColor(led, npx.Color(0, 0, 0))
        self.strip.show()

    def show_message(self, msg):
        for c in msg.replace(' ', ''):
            self.show_char(c)
            time.sleep(DELAY_BETWEEN_CHARS)

    def start_random_animations(self):
        self.strip.setBrightness(8)
        self.animation_process = multiprocessing.Process(target=self.random_forever)
        self.animation_process.start()

    def run_forever(self):
        while True:
            if self.in_queue.empty():
                self.start_random_animations()
            _, msg, uuid = self.in_queue.get()
            if self.animation_process is not None and self.animation_process.is_alive():
                self.animation_process.terminate()
                self.clear_strip()
                self.strip.setBrightness(255)
            if msg == "ANIMATION":
                self.random_animation()
                self.clear_strip()
                self.strip.setBrightness(255)
                continue
            self.show_message(msg)
            self.out_queue.put(uuid)
            time.sleep(MESSAGE_DELAY)

    def clear_strip(self):
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, npx.Color(0, 0, 0))
        self.strip.show()

    def theater_chase(self, color=random_color(), wait_ms=50, iterations=20):
        """Movie theater light style chaser animation."""
        for j in range(iterations):
            for q in range(3):
                for i in range(0, self.strip.numPixels(), 3):
                    self.strip.setPixelColor(i + q, color)
                self.strip.show()
                time.sleep(wait_ms / 1000.0)
                for i in range(0, self.strip.numPixels(), 3):
                    self.strip.setPixelColor(i + q, 0)

    def rainbow(self, wait_ms=20, iterations=1):
        """Draw rainbow that fades across all pixels at once."""
        for j in range(256*iterations):
            for i in range(self.strip.numPixels()):
                self.strip.setPixelColor(i, wheel((i+j) & 255))
            self.strip.show()
            time.sleep(wait_ms/1000.0)

    def rainbow_cycle(self, wait_ms=20, iterations=5):
        """Draw rainbow that uniformly distributes itself across all pixels."""
        for j in range(256*iterations):
            for i in range(self.strip.numPixels()):
                self.strip.setPixelColor(i, wheel((int(i * 256 / self.strip.numPixels()) + j) & 255))
            self.strip.show()

            time.sleep(wait_ms/1000.0)

    def theater_chase_rainbow(self, wait_ms=50):
        """Rainbow movie theater light style chaser animation."""
        for j in range(256):
            for q in range(3):
                for i in range(0, self.strip.numPixels(), 3):
                    self.strip.setPixelColor(i+q, wheel((i+j) % 255))
                self.strip.show()
                time.sleep(wait_ms/1000.0)
                for i in range(0, self.strip.numPixels(), 3):
                    self.strip.setPixelColor(i+q, 0)

    def wills_speech(self):
        self.show_message("RIGHTHERE")
        time.sleep(2)
        self.show_message("RUN")

    def dun_dun(self, delay=1, scalar=0.85):
        addr = [x for x in range(len(ADDR_MAP))]
        for i in range(len(addr)):
            rand_addr = random.choice(addr)
            self.strip.setPixelColor(rand_addr, random_color())
            self.strip.show()
            addr.remove(rand_addr)
            time.sleep(delay*scalar**i)
        time.sleep(3)
        addr = [x for x in range(len(ADDR_MAP))]
        for _ in range(len(addr)):
            a = random.choice(addr)
            addr.remove(a)
            self.strip.setPixelColor(a, npx.Color(0, 0, 0))
            self.strip.show()
            time.sleep(0.03)
        time.sleep(0.3)


    def random_animation(self):
        self.clear_strip()
        animation_list = [self.theater_chase,
                          self.rainbow,
                          self.rainbow_cycle,
                          self.dun_dun]
        random.choice(animation_list)()

    def random_forever(self):
        while True:
            self.random_animation()

