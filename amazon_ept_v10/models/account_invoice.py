from openerp import models,api,fields
class account_invoice(models.Model):
    _inherit="account.invoice"
    
    amazon_instance_id = fields.Many2one("amazon.instance.ept","Instances")
    @api.model
    def send_amazon_invoice_via_email(self,args={}):
        instance_obj=self.env['amazon.instance.ept']
        seller_obj=self.env['amazon.seller.ept']
        invoice_obj=self.env['account.invoice']
        seller_id = args.get('seller_id',False)
        if seller_id:
            seller = seller_obj.search([('id','=',seller_id)])
            if not seller:
                return True
            
            email_template= self.env.ref('account.email_template_edi_invoice', False)
            instances = instance_obj.search([('seller_id','=',seller.id)])
            
            for instance in instances:
                if instance.invoice_tmpl_id:
                    email_template=instance.invoice_tmpl_id
                invoices=invoice_obj.search([('amazon_instance_id','=',instance.id),('state','in',['open','paid']),('sent','=',False),('type','=','out_invoice')])
                for invoice in invoices:                
                    email_template.send_mail(invoice.id)
                    invoice.write({'sent':True})                
        return True
    
    @api.model
    def send_amazon_refund_via_email(self,args={}):
        instance_obj=self.env['amazon.instance.ept']
        seller_obj=self.env['amazon.seller.ept']
        invoice_obj=self.env['account.invoice']
        seller_id = args.get('seller_id',False)
        if seller_id:
            seller = seller_obj.search([('id','=',seller_id)])
            if not seller:
                return True
            email_template= self.env.ref('account.email_template_edi_invoice', False)
            instances = instance_obj.search([('seller_id','=',seller.id)])
            for instance in instances:
                if instance.refund_tmpl_id:
                    email_template=instance.refund_tmpl_id
                invoices=invoice_obj.search([('amazon_instance_id','=',instance.id),('state','in',['open','paid']),('sent','=',False),('type','=','out_refund')],limit=1)
                for invoice in invoices:   
                    email_template.send_mail(invoice.id)
                    invoice.write({'sent':True})                
        return True
