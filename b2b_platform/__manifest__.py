# -*- coding: utf-8 -*-
{
    'name': "B2B分销平台",

    'summary': """
        电子商务B2B分销平台管理模块
        """,

    'description': """
        预设产品分类，管理供应商、经销商，产品发布与收录，与电商平台同步数据，各方结算
    """,

    'author': "杭州敏行网络有限责任公司",
    'website': "http://www.mxnet.cn",

    'category': 'sale',
    'version': '10.0.1',

    'depends': ['sale','purchase','stock','account_accountant','l10n_cn_small_business',
                'website_sale','web_tree_image', 'amazon_ept_v10',
                'document_multi_upload','website_product_attachments',
                'add_button_in_tree_view','delivery',
                'add_button_inventory_import','download_file','hide_attachment',
                'web_export_view','access_restricted','group_menu_no_access','access_apps',
                'access_apps_website','currency_rate_update','base_currency_inverse_rate',
                'web_sheet_full_width','muk_web_preview_image'],

    'data': [
        'security/security.xml',
        'data/partner_data.xml',
        'security/rules.xml',
        'security/ir.model.access.csv',
        'data/payment_data.xml',
        'views/partner.xml',
        'views/actions.xml',
        'views/deposit.xml',
        'views/settlement.xml',
        'views/withdrawal.xml',
        'views/complaint.xml',
        'views/templates.xml',
        'views/product_images.xml',
        'views/product.xml',
        'views/purchase.xml',
        'views/sale.xml',
        'views/invoice.xml',
        'views/warehouse.xml',
        'views/fba.xml',
        'views/markup.xml',
        'views/trader_data.xml',
        'views/menus.xml',
        'wizard/b2b_resend.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],
    'application': True,
    'installable': True,
    'qweb': [],
}