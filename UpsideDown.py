import Facebook
import Instagram
import Display
import threading
import queue
import unidecode
import re
import json
import random
import time

import os
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env')

with open('word-list.txt', 'r') as f:
    PASSWORD_LIST = f.readlines()


class UpsideDown:
    MAX_CHAR = 25
    MAX_MESSAGES_PER_USER = 5

    def __init__(self):
        self.message_queue = queue.Queue()
        self.debug_flag = threading.Event()

        try:
            with open("eggos", "r") as cookies:
                session_cookies = json.loads(cookies.readline())
        except FileNotFoundError:
            session_cookies = None

        self.facebook = Facebook.Facebook(os.getenv('FB_USER'), os.getenv('FB_PASSWD'),
                                          self.message_queue, self.debug_flag, session_cookies=session_cookies)

        with open("eggos", "w") as cookies:
            cookies.write(json.dumps(self.facebook.getSession()))

        self.facebook_thread = threading.Thread(target=self.facebook.listen)
        self.facebook_thread.start()

        self.instagram = Instagram.Instagram(os.getenv('IG_USER'), os.getenv('IG_PASSWD'),
                                             self.message_queue, self.debug_flag)
        self.instagram_thread = threading.Thread(target=self.instagram.listen)
        self.instagram_thread.start()

        self.display = Display.Display()
        self.display_thread = threading.Thread(target=self.display.run_forever)
        self.display_thread.start()

        self.users = {}

        self.received_message_count = 0

        self.commands = {"MAXMESSAGES": self.max_messages,
                         "MAXLENGTH": self.max_length,
                         "STATS": self.stats,
                         "ANIMATION": self.animation,
                         "SHOW": self.display_message,
                         "HELP": self.help,
                         "DEBUG": self.debug,
                         "PW": self.password}

    def process_message(self, message, author):
        message = unidecode.unidecode(message).upper()

        if author in (self.facebook.uid, self.instagram.username_id) and len(message) > 0 and message[0] != "$":
            match = re.search("^(?P<command>[A-Z]+)", message)
            if not match:
                return "Wrong command pattern"
            command = match.group("command")

            match = re.search("^[A-Z]+\s+(?P<args>.*)", message)
            args = match.group("args") if match else None

            func = self.commands.get(command)
            if not func:
                return "Command {} not found".format(command)
            return func(args)

        elif message[0] == '#':
            message = re.sub("[^A-Z ]", "", message)
            match = re.search("^\s*(?P<passwd>[A-Z]+)\s+(?P<text>[A-Z ]+)$", message)
            if not match:
                return "Invalid password format"
            passwd = match.group("passwd")
            if passwd in PASSWORD_LIST:
                PASSWORD_LIST.remove(passwd)
                return self.push_to_display(1, match.group("text"), author, True)
            else:
                return "Invalid password."
        else:
            message = re.sub("[^A-Z]", "", message)
            return self.push_to_display(2, message, author)

    def push_to_display(self, priority, message, author, skip_check=False):
        while not self.display.out_queue.empty():
            returned_uid = self.display.out_queue.get()
            if returned_uid in self.users:
                self.users[returned_uid] -= 1

        self.users[author] = self.users.get(author, 0)
        if skip_check:
            self.display.in_queue.put((priority, message, author))
            return "Message was placed into the queue without checking"

        if self.users[author] < self.MAX_MESSAGES_PER_USER and len(message) <= self.MAX_CHAR:
            self.users[author] += 1
            self.display.in_queue.put((priority, message, author))
            self.received_message_count += 1
            return "Your message was placed into the queue"
        else:
            return "You reached one or more of the limits. Max number of characters per message is {}.\n" \
                   "Max number of messages enqueued per user is {}".format(self.MAX_CHAR, self.MAX_MESSAGES_PER_USER)

    def max_messages(self, arg):
        try:
            if arg is None:
                return "Max messages per user: {}".format(self.MAX_MESSAGES_PER_USER)
            else:
                old = self.MAX_MESSAGES_PER_USER
                self.MAX_MESSAGES_PER_USER = int(arg)
                return "Max messages per user is now set to {} was {}".format(arg, old)
        except ValueError:
            return "Parameter has to be an integer"

    def max_length(self, arg):
        try:
            if arg is None:
                return "Max message length: {}".format(self.MAX_CHAR)
            else:
                old = self.MAX_CHAR
                self.MAX_CHAR = int(arg)
                return "Max message length is now set to {} was {}".format(arg, old)
        except ValueError:
            return "Parameter has to be an integer"

    def stats(self, _):
        return "Received message count: {}\n" \
               "Messages in queue: {}".format(self.received_message_count, self.display.in_queue.qsize())

    def animation(self, _):
        return self.push_to_display(0, "ANIMATION", self.facebook.uid, True)

    def display_message(self, arg):
        return self.push_to_display(0, arg, self.facebook.uid, True)

    def help(self, _):
        return "Available commands: " + "\n".join(self.commands.keys())

    def debug(self, arg):
        try:
            if int(arg) == 0:
                if self.debug_flag.is_set():
                    self.debug_flag.clear()
                    return "Debug output has been disabled."
                return "Debug output stayed unchanged. (disabled)"
            elif int(arg) == 1:
                if not self.debug_flag.is_set():
                    self.debug_flag.set()
                    return "Debug output has been enabled."
                return "Debug output stayed unchanged. (enabled)"
            elif arg is None:
                return "Debug output is set to {}".format(self.debug_flag.is_set())
        except ValueError:
            return "Parameter has to be either 0 or 1."

    def password(self, _):
        return "#" + PASSWORD_LIST[random.randint(0, len(PASSWORD_LIST)-1)]

    def run_forever(self):
        while True:
            message, author, source = self.message_queue.get(block=True)
            time.sleep(0.1)
            response = self.process_message(message, author)
            if source == "IG":
                self.instagram.response_queue.put((response, author))
            elif source == "FB":
                self.facebook.response_queue.put((response, author))


if __name__ == "__main__":
    server = UpsideDown()
    server.run_forever()
