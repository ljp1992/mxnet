from odoo import models, fields, api, _
from odoo.api import Environment
import time
from datetime import datetime

# mapping invoice type to journal type
TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale_refund',
    'in_refund': 'purchase_refund',
}

class sale_workflow_process(models.Model):
    _name = "sale.workflow.process.ept"
    _description = "sale workflow process"

    @api.model
    def _default_journal(self):
        inv_type = self._context.get('type', 'out_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', filter(None, map(TYPE2JOURNAL.get, inv_types))),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)
        
    name = fields.Char(string='Name', size=64)
    validate_order = fields.Boolean("Validate Order",default=False,help="Directly Confirm Sale and create Sales Order when importing an order.")
    create_invoice = fields.Boolean('Create Invoice',default=False,help="Create Invoice of the Sales Order that is imported.")
    validate_invoice = fields.Boolean(string='Validate Invoice',default=False,help="Automatically validate invoice of the Sales Order that is imported.")
    register_payment=fields.Boolean(string='Register Payment',default=False,help="Automatically Register Payment of the Sales Order that is imported.")
    invoice_date_is_order_date = fields.Boolean('Force Invoice Date', help="Keep Invoice date same as Order date.")
    journal_id = fields.Many2one('account.journal', string='Payment Journal',domain=[('type','in',['cash','bank'])],help="Select a journal where you want to create supplier invoice entries.")
    sale_journal_id = fields.Many2one('account.journal', string='Sales Journal',default=_default_journal,domain=[('type','=','sale')],help="Select a journal where you want to create customer invoice entries.")
    picking_policy =  fields.Selection([('direct', 'Deliver each product when available'), ('one', 'Deliver all products at once')], string='Shipping Policy',help="Choose if you want to ship all products at once or each product when they are available.")
    auto_check_availability=fields.Boolean("Auto Check Availability",default=False)
    invoice_policy = fields.Selection([('order', 'Ordered quantities'),('delivery', 'Delivered quantities'),],string='Invoicing Policy',help="Choose if you want to create invoice based on ordered quantities or delivered quantities.")
    
    @api.onchange("validate_order")
    def onchange_validate_order(self):
        for record in self:
            if not record.validate_order:
                record.auto_check_availability=False
                record.create_invoice=False
    @api.onchange("create_invoice")
    def onchange_create_invoice(self):
        for record in self:
            if not record.create_invoice:
                record.validate_invoice=False
    @api.onchange("validate_invoice")
    def onchange_validate_invoice(self):
        for record in self:
            if not record.validate_invoice:
                record.register_payment=False
                record.invoice_date_is_order_date=False                
    @api.model
    def auto_workflow_process(self,auto_workflow_process_id=False,ids=[]):
        transaction_log_obj=self.env['transaction.log.ept']
        with Environment.manage():
            env_thread1 = Environment(self._cr,self._uid,self._context)
            sale_order_obj=env_thread1['sale.order']
            sale_order_line_obj=env_thread1['sale.order.line']
            account_payment_obj=env_thread1['account.payment']
            workflow_process_obj=env_thread1['sale.workflow.process.ept']
            if not auto_workflow_process_id:
                work_flow_process_records=workflow_process_obj.search([])
            else:
                work_flow_process_records=workflow_process_obj.browse(auto_workflow_process_id)

            if not work_flow_process_records:
                return True
            
            for work_flow_process_record in work_flow_process_records:
                if not ids:
                    orders=sale_order_obj.search([('auto_workflow_process_id','=',work_flow_process_record.id),('state','not in',('done','cancel','sale')),('invoice_status','!=','invoiced')])#('invoiced','=',False)
                else:
                    orders=sale_order_obj.search([('auto_workflow_process_id','=',work_flow_process_record.id),('id','in',ids)]) 
                if not orders:
                    continue
                for order in orders:
                    if order.invoice_status and order.invoice_status=='invoiced': 
                        continue
                    if work_flow_process_record.validate_order:
                        try:
                            order.action_confirm()
                        except Exception as e:
                            transaction_log_obj.create({
                                'message':"Error while confirm Sale Order %s\n%s"%(order.name,e),
                                'mismatch_details':True,
                                'type':'sales'
                                })
                            continue
                    if work_flow_process_record.invoice_policy=='delivery':
                        continue
                    if not work_flow_process_record.invoice_policy and not sale_order_line_obj.search([('product_id.invoice_policy','!=','delivery'),('order_id','in',order.ids)]):
                        continue    
                    if not order.invoice_ids:
                        if work_flow_process_record.create_invoice:
                            try:
                                order.action_invoice_create()
                            except Exception as e:
                                transaction_log_obj.create({
                                'message':"Error while Create invoice for Order %s\n%s"%(order.name,e),
                                'mismatch_details':True,
                                'type':'invoice'
                                })
                                continue
                    if work_flow_process_record.validate_invoice:
                        for invoice in order.invoice_ids:
                            try:                        
                                invoice.action_invoice_open()
                            except Exception as e:
                                transaction_log_obj.create({
                                    'message':"Error while open Invoice for Order %s\n%s"%(order.name,e),
                                    'mismatch_details':True,
                                    'type':'invoice'
                                    })
                                continue
                            if work_flow_process_record.register_payment:
                                if invoice.residual:
                                # Create Invoice and Make Payment                                                                                                
                                    vals={
                                        'journal_id':work_flow_process_record.journal_id.id,
                                        'invoice_ids':[(6,0,[invoice.id])],
                                        'communication':invoice.reference,
                                        'currency_id':invoice.currency_id.id,
                                        'payment_type':'inbound',
                                        'partner_id':invoice.commercial_partner_id.id,
                                        'amount':invoice.residual,
                                        'payment_method_id':work_flow_process_record.journal_id.inbound_payment_method_ids.id,
                                        'partner_type':'customer'
                                        }
                                    try:
                                        new_rec=account_payment_obj.create(vals)
                                        new_rec.post()
                                    except Exception as e:
                                        transaction_log_obj.create({
                                            'message':"Error while Validating Invoice for Order %s\n%s"%(order.name,e),
                                            'mismatch_details':True,
                                            'type':'invoice'
                                            })
                                        continue                                
        return True
