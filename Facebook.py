import fbchat
from fbchat import models
import queue
import logging
import time


class Facebook(fbchat.Client):
    def __init__(self, user, passwd, message_queue, debug_flag, *args, **kwargs):
        super(Facebook, self).__init__(user, passwd, *args, **kwargs)
        self.log = logging.getLogger("client")

        self.message_queue = message_queue
        self.response_queue = queue.Queue()
        self.debug_flag = debug_flag

    def onMessage(self, author_id, message_object, thread_id, thread_type, **kwargs):
        self.log.info("{} from {} in {}".format(message_object, thread_id, thread_type.name))

        if thread_type == models.ThreadType.USER and message_object.text and message_object.text[0] != "$":
            self.markAsDelivered(thread_id, message_object.uid)
            self.markAsRead(thread_id)
            self.message_queue.put((message_object.text, author_id, "FB"))
            time.sleep(0.5)
            if not self.response_queue.empty():
                response, author = self.response_queue.get()
            else:
                response, author = None, None
            if response is not None and (self.debug_flag.is_set() or self.uid == thread_id):
                self.send(models.Message(text='$ ' + response), thread_id=thread_id, thread_type=thread_type)

    def onInbox(self, unseen=None, unread=None, recent_unread=None, msg=None):
        thread = self.fetchThreadList(self, limit=1, thread_location=models.ThreadLocation.OTHER)[0]
        msg = self.fetchThreadMessages(thread_id=thread.uid, limit=1)[0]
        if not msg.is_read:
            self.onMessage(author_id=msg.author, message_object=msg, thread_id=thread.uid, thread_type=thread.type)

    def listen(self, markAlive=None):
        """
        Initializes and runs the listening loop continually

        :param markAlive: Whether this should ping the Facebook server each time the loop runs
        :type markAlive: bool
        """
        if markAlive is not None:
            self.setActiveStatus(markAlive)

        self.startListening()
        self.onListening()

        while self.listening and self.doOneListen():
            time.sleep(0.05)

        self.stopListening()
