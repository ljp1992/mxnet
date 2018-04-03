from openerp import models, fields,api
class amazon_transaction_type(models.Model):
    _name="amazon.transaction.type"
    
    name = fields.Char(size=256, string='Name')
    amazon_code = fields.Char(size=256, string='Transaction Code')
    
class amazon_transaction_line_ept(models.Model):
    _name="amazon.transaction.line.ept"
    
    @api.multi
    @api.depends('transaction_type_id')
    def get_transaction_code(self):
        for record in self:
            record.amazon_code=record.transaction_type_id.amazon_code
    
    transaction_type_id = fields.Many2one('amazon.transaction.type', string="Transaction Type")
    seller_id = fields.Many2one('amazon.seller.ept', string="Seller")
    amazon_code=fields.Char("Amazon Code",compute="get_transaction_code",store=True)
    account_id = fields.Many2one('account.account', string="Account") 
    tax_id=fields.Many2one('account.tax',string="Tax")
    
    _sql_constraints=[('amazon_transaction_unique_constraint','unique(seller_id,transaction_type_id)',"Transaction type must be unique by seller.")]