from django.core.mail import EmailMessage


class EmailsSending:

    def send(self, subject, email_body, to_emails):
        email_message = EmailMessage(subject, email_body, to=to_emails)
        email_message.content_subtype = "html"
        email_message.send()
        return True
