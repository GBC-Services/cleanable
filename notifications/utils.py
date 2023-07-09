from .models import NotificationTemplate, Notification


class ProcessNotification:
    
    def send_if_needed(self, cleaning):
        templates = self.get_or_create_template(cleaning)
        if templates:
            for user, template in templates:
                is_duplicate = template.check_duplicate(cleaning)
                if not is_duplicate:
                    template.send(user, cleaning=cleaning)
        return True

    def get_or_create_template(self, cleaning):
        templates = list()
        if cleaning.status == cleaning.STATUS_CLEANER_IS_ON_THE_WAY:
            text = "Cleaner is on the way"
            template, _ = NotificationTemplate.objects.get_or_create(name=f"{cleaning.get_status_display()}",
                                                                     channel=NotificationTemplate.CHANNEL_SMS,
                                                                     defaults=dict(text=text))
            user = cleaning.booking.client
            templates.append((user, template))
        elif cleaning.status == cleaning.STATUS_STARTED:
            text = "The cleaning has been started"
            template, _ = NotificationTemplate.objects.get_or_create(name=f"{cleaning.get_status_display()}",
                                                                     channel=NotificationTemplate.CHANNEL_SMS,
                                                                     defaults=dict(text=text))
            user = cleaning.booking.client
            templates.append((user, template))
        elif cleaning.status == cleaning.STATUS_COMPLETED:
            text = "The cleaning has been completed"
            template, _ = NotificationTemplate.objects.get_or_create(name=f"{cleaning.get_status_display()}",
                                                                     channel=NotificationTemplate.CHANNEL_SMS,
                                                                     defaults=dict(text=text))
            user = cleaning.booking.client
            templates.append((user, template))
        elif cleaning.status == cleaning.STATUS_NOT_COMPLETED:
            text = "Some issue occurred during the cleaning"
            template, _ = NotificationTemplate.objects.get_or_create(name=f"{cleaning.get_status_display()}",
                                                                     channel=NotificationTemplate.CHANNEL_SMS,
                                                                     defaults=dict(text=text))
            user = cleaning.booking.client
            templates.append((user, template))
        return templates