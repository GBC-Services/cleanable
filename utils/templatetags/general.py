from django.template.defaulttags import register


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_fee(dictionary, key):
    if not dictionary is None:
        fee = dictionary.get(key)
        if not fee is None:
            fee = fee.normalize()
    else:
        fee = 0
    return fee


@register.filter
def get_company_availability_for_booking(obj, booking):
    return obj.get_availability_for_booking(booking)