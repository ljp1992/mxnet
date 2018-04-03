from openerp import models, fields
class amazon_tax_code_ept(models.Model):
    _name="amazon.tax.code.ept"

    name=fields.Char("Tax Name")
    tax_id = fields.Many2one('account.tax', 'Account Tax')
