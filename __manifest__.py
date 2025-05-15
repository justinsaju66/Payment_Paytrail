# -*- coding: utf-8 -*-


{
    'name': "Payment Paytrail",
    'version': '1.0',
    'depends': ['payment'],
    'author': "Author Name",
    'category': 'all',
    'description': """
    Payment Paytrail
    """,
    # data files always loaded at installation
    'data': [
        "views/payment_method_template.xml",
        "views/payment_provider_views.xml",
        "views/payment_template.xml",
        "data/payment_provider_data.xml",
        "data/payment_method_data.xml",
    ],

    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
