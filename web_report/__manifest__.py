# -*- coding: utf-8 -*-
{
    'name': 'Odoo web report',
    'version': '1.0',
    'summary': u'嵌入controller方式开发',
    'category': 'base',
    'description':
    """
     """,
    'data': [
        'views/web_report_views.xml',
        'views/web_report_templates.xml',
    ],
    'depends': ['base','b2b_platform'],
    'qweb': [
        'static/src/xml/web_report.xml',
        'static/src/xml/web_ex_report.xml',
        'static/src/xml/web_b2b_dashboard.xml'
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
