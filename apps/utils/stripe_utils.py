import os
import sys

import datetime

from django.conf import settings
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeUtils:

    def create_invoice(self, booking, dt):
        """This endpoint creates a draft invoice for a given customer. 
        The invoice remains a draft until you finalize the invoice, 
        which allows you to pay or send the invoice to your customers."""
        invoice = stripe.Invoice.create(customer=booking.stripe_customer_id,
                                        auto_advance=True,
                                        collection_method="charge_automatically",
                                        )
        invoice_id = invoice["id"]
        stripe.InvoiceItem.create(customer=booking.stripe_customer_id,
                                                 amount=int(float(booking.total_fee_final)*100),  # in cents
                                                 currency='usd',
                                                 description=f'Cleaning {dt.strftime("%m/%d/%Y")}',
                                                 invoice=invoice_id)

        stripe.Invoice.finalize_invoice(invoice_id)
        return invoice_id


if __name__ == "__main__":
    os.environ['DJANGO_SETTINGS_MODULE'] = 'cleaning.settings'
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    import django
    django.setup()

    from apps.bookings.models import Booking

    booking = Booking.objects.last()
    dt = datetime.datetime.now()
    StripeUtils().create_invoice(booking, dt)
