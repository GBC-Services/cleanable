LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'console_notset': {
            'level': 'NOTSET',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'console_info': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'console_error': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        '': {
            'handlers': ['console_notset'],
            'level': 'NOTSET',
        },
        'django.request': {
            'handlers': ['console_error'],
            'propagate': False,
            'level': 'ERROR'
        }
    }
}