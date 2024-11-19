from .models import NotificationTemplate, Notification


class ProcessNotification:
    channels = [NotificationTemplate.CHANNEL_SMS, NotificationTemplate.CHANNEL_EMAIL]
    
    def send_if_needed(self, cleaning):
        templates = self.get_or_create_template(cleaning)
        if templates:
            for user, template in templates:
                is_duplicate = template.check_duplicate(cleaning)
                if not is_duplicate:
                    template.send(user, cleaning=cleaning)
        return True

    def get_or_create_template(self, cleaning):
        """Notification.name is a duplicate of a cleaning status here, because it can be other notifications,
        not related to a cleaning, so it makes no sense to add cleaning status as a separate field to
        a notification instead of using the name."""
        templates = list()
        text = None
        if cleaning.status == cleaning.STATUS_CLEANER_IS_ON_THE_WAY:
            text = "Cleaner is on the way"
        elif cleaning.status == cleaning.STATUS_STARTED:
            text = "The cleaning has been started"
        elif cleaning.status == cleaning.STATUS_COMPLETED:
            text = "The cleaning has been completed"
        elif cleaning.status == cleaning.STATUS_NOT_COMPLETED:
            text = "Some issue occurred during the cleaning"

        if not text is None:
            user = cleaning.booking.client
            for channel in self.channels:
                kwargs = dict(name=f"{cleaning.get_status_display()}",
                              channel=channel,
                              defaults=dict(text=text))
                template, _ = NotificationTemplate.objects.get_or_create(**kwargs)
                if channel == NotificationTemplate.CHANNEL_EMAIL:
                    if template.subject is None:
                        template.subject = text
                        template.save(force_update=True)

                templates.append((user, template))

        return templates