# -*- coding: utf-8 -*-

{
    'name': "Tea Community Theme",
    'author': "RStudio",
    'website': "",
    'sequence': 1,
    'installable': True,
    'application': True,
    'auto_install': False,
    'summary': u"""
        Backend/AppSwither/Sidebar/Theme Settings.
        """,
    'description': u"""

    """,
    "category": "Themes/Backend",
    'version': '10.0.1.2',
    'depends': [
        'web',
        # 'web', 'website_sale',
    ],
    'data': [
        'views/assets.xml',
        'views/backend.xml',
        'views/login_template.xml',
        'views/login_views.xml',
        'views/setting_views.xml',
    ],
    'qweb': [
        "static/src/xml/*.xml",
    ],
    'live_test_url': 'https://tea.rstudio.xyz',
    'images': ['images/main_screenshot.png'],
    'currency': 'EUR',
    'price': 109,
}
