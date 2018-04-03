# -*- coding: utf-8 -*-
{
    'name': "hide_attachment",

    'summary': """
        隐藏附件选项""",

    'description': """
        Long description of module's purpose
    """,

    'author': "青岛欧度软件技术有限责任公司",
    'website': "http://www.qdodoo.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['web','document'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}