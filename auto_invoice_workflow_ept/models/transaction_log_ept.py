from odoo import fields,models

class transaction_log_ept(models.Model):
    _name='transaction.log.ept'
    _order='id desc'
    _rec_name = 'create_date'
    _description = "Auto Invoice Workflow Process Job"
    
    create_date=fields.Datetime("Create Date")
    mismatch_details=fields.Boolean("Mismatch Details")
    message=fields.Text("Message")
    type=fields.Selection([('sales','Sales'),('inventory','Inventory'),('invoice','Invoice')],string="Type")