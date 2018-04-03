# -*- coding: utf-8 -*-
{
    'name': "Amazon api",

    'summary': """
        """,

    'description': """
    """,

    'author': "青岛欧度软件技术有限责任公司",
    'website': "http://www.qdodoo.com",

    'category': 'Uncategorized',
    'version': 'v11-1.0',

    # any module necessary for this one to work correctly
    'depends': ['amazon_ept_v10', 'b2b_platform', 'add_button_in_tree_view'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/res_groups.xml',
        'data/data.xml',
        'data/ir_sequence.xml',
        'views/product_template.xml',
        'views/product_product.xml',
        'views/amazon_sale_order.xml',
        'views/active_product_listing_view.xml',
        'views/sync_product_wizard.xml',
        'views/amazon_process_log_book.xml',
        'views/sync_browse_node.xml',
        'views/feed_result.xml',
        'views/b2b_shop_collect_convert.xml',
        'views/amazon_seller_ept.xml',
        'views/amazon_process_import_export.xml',
        'views/b2b_distributor_amazon_template.xml',
        'views/product_attribute_value.xml',
        'views/get_product_info.xml',
        'views/sale_order.xml',
        'views/product_attribute.xml',
        'views/stock_picking.xml',
        'views/amazon_category_ept.xml',
        'views/res_partner.xml',
        # 'views/amazon_instance_ept.xml',
        # 'cs/upload_product.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}