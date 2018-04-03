{
    'name': 'auto_invoice_workflow_ept',
    'version': '8.0',
    'category': 'Generic Modules/Others',
    'license': 'AGPL-3',
    'description': """
        This Module Confirm Workflow Automatic as well as create or validate or payed Invoice based on configuration
    """,
    'author': 'Emipro Technologies',
    'website': 'http://www.emiprotechnologies.com/',
    'depends': ['sale','account','stock'], 
    'init_xml': [],
    'data': [ 
            'view/sale_workflow_process_view.xml',
            'view/automatic_workflow_data.xml',
            'view/sale_view.xml',
            'view/transaction_log_view.xml',
            'security/ir.model.access.csv',
    ],
    'demo_xml': [],
    'installable': True,
    'active': False,
}

