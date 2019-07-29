import time
import json
import queue
import threading
from InstagramAPI import InstagramAPI
import logging


class Instagram(InstagramAPI):
    USER_AGENT = 'Instagram 10.34.0 Android (18/4.3; 320dpi; 720x1280; Xiaomi; HM 1SW; armani; qcom; en_US)'

    def __init__(self, user, passwd, message_queue=queue.Queue(), debug_flag=threading.Event(), *args):
        super(Instagram, self).__init__(user, passwd, *args)
        self.log = logging.getLogger("client")
        self.login()

        self.message_queue = message_queue
        self.response_queue = queue.Queue()
        self.debug_flag = debug_flag

    def direct_message(self, text, recipients):
        if type(recipients) != type([]):
            recipients = [str(recipients)]
        recipient_users = '"",""'.join(str(r) for r in recipients)
        endpoint = 'direct_v2/threads/broadcast/text/'
        boundary = self.uuid
        bodies = [
            {
                'type': 'form-data',
                'name': 'recipient_users',
                'data': '[["{}"]]'.format(recipient_users),
            },
            {
                'type': 'form-data',
                'name': 'client_context',
                'data': self.uuid,
            },
            {
                'type': 'form-data',
                'name': 'thread',
                'data': '["0"]',
            },
            {
                'type': 'form-data',
                'name': 'text',
                'data': text or '',
            },
        ]
        data = self.buildBody(bodies, boundary)
        self.s.headers.update(
            {
                'User-Agent': self.USER_AGENT,
                'Proxy-Connection': 'keep-alive',
                'Connection': 'keep-alive',
                'Accept': '*/*',
                'Content-Type': 'multipart/form-data; boundary={}'.format(boundary),
                'Accept-Language': 'en-en',
            }
        )
        # self.SendRequest(endpoint,post=data) #overwrites 'Content-type' header and boundary is missed
        response = self.s.post(self.API_URL + endpoint, data=data)

        if response.status_code == 200:
            self.LastResponse = response
            self.LastJson = json.loads(response.text)
            return True
        else:
            print("Request return " + str(response.status_code) + " error!")
            # for debugging
            try:
                self.LastResponse = response
                self.LastJson = json.loads(response.text)
            except:
                pass
            return False

    def get_pending_inbox(self):
        pending_inbox = self.SendRequest("direct_v2/pending_inbox/")
        return pending_inbox

    def approve_pending_threads(self, threads):
        data = {
            "_csrftoken": self.token,
            "_uuid": self.uuid,
        }
        if not isinstance(threads, list) or not isinstance(threads, tuple):
            threads = [str(threads)]
        if len(threads) > 1:
            data["thread_ids"] = threads
            succ = self.SendRequest("direct_v2/threads/approve_multiple/", self.generateSignature(json.dumps(data)))
        else:
            succ = self.SendRequest("direct_v2/threads/{}/approve".format(threads[0]), self.generateSignature(json.dumps(data)))
        return succ

    def mark_as_seen(self, thread, item):
        data = json.dumps({
            '_uuid': self.uuid,
            '_csrftoken': self.token,
            'action': 'mark_seen',
            'thread_id': thread,
            'item_id': item,
        })
        request = self.SendRequest("direct_v2/threads/{}/items/{}/seen/".format(thread, item),
                                   self.generateSignature(data))
        return request

    def listen(self):
        self.log.info("Instagram has started listening...")
        while True:
            self.get_new_inbox()
            self.get_new_pending()
            time.sleep(0.5)

    def get_new_inbox(self):
        if not self.getv2Inbox():
            return
        self.process_inbox()

    def get_new_pending(self):
        if not self.get_pending_inbox():
            return
        self.process_inbox()

    def process_inbox(self):
        threads = self.LastJson.get("inbox", {}).get("threads")
        messages = self.get_new_messages(threads)
        if not messages:
            return
        else:
            self.log.info("New message(s) received:" + str(messages))

        self.push_to_queue(messages)
        time.sleep(0.5)
        while not self.response_queue.empty():
            response, author = self.response_queue.get()
            self.log.info("Message: {}, Author: {}".format(response, author))
            if response is not None and self.debug_flag.is_set():
                self.uuid = self.generateUUID(True)
                self.direct_message(response, author)

    def get_new_messages(self, threads):
        for thread in threads:
            if not thread.get("read_state"):
                continue

            thread_id = thread.get("thread_id")
            if not self.getv2Threads(thread_id):
                continue

            thread_details = self.LastJson.get("thread")

            if thread_details.get("pending"):
                self.approve_pending_threads(thread_id)

            last_seen_id = thread_details \
                .get("last_seen_at", {}) \
                .get(str(self.username_id), {}) \
                .get("item_id")

            self.log.info(last_seen_id)
            self.log.info(self.username_id)

            new_messages = []
            for item in thread_details.get("items"):
                if item.get("item_id") == last_seen_id:
                    break
                new_messages.append((item.get("text"), item.get("user_id"), "IG"))

            last_item_id = thread.get("last_permanent_item", {}).get("item_id")
            self.mark_as_seen(thread_id, last_item_id)

            new_messages.reverse()
            return new_messages

    def push_to_queue(self, messages):
        for msg in messages:
            self.message_queue.put(msg)
