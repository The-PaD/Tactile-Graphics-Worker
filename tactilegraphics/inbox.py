import imaplib
import email

class TGInbox:
    """Represents an IMAP inbox. Iterable!"""
    def __init__(self, server, port, username, password):
        self.email_uids = []
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(username, password)
        mail.select('INBOX')
        self.mail = mail

        status, response = mail.status('INBOX', "(UNSEEN)")
        unreadcount = int(response[0].split()[2].strip(').,]'))
        self.unreadcount = unreadcount

        if(unreadcount > 0):
            # search and return uids
            result, data = mail.uid('search', None, "(UNSEEN)")
            self.email_uids = data[0].split()

    def __iter__(self):
        return self.iterate_emails()

    def iterate_emails(self):
        for email_uid in self.email_uids:
            result, data = self.mail.uid('fetch', email_uid, '(RFC822)')
            raw_email = data[0][1]
            yield email.message_from_string(raw_email)
            
