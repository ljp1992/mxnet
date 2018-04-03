
from odoo import models, fields, api, _
from odoo.osv.osv import except_osv
from odoo.exceptions import Warning


class sale_order(models.Model):
    _inherit = "sale.order"
    
    invoice_policy = fields.Selection(
        [('order', 'Ordered quantities'),
         ('delivery', 'Delivered quantities')],
        string='Invoicing Policy',readonly=True,states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, copy=False)

    auto_workflow_process_id = fields.Many2one('sale.workflow.process.ept', string='Workflow Process',copy=False)        

    @api.multi
    def _prepare_invoice(self):
        invoice_vals = super(sale_order, self)._prepare_invoice()
        
        if self.auto_workflow_process_id:
            invoice_vals.update({'journal_id':self.auto_workflow_process_id.sale_journal_id.id})
            if self.auto_workflow_process_id.invoice_date_is_order_date:
                invoice_vals['date_invoice'] = self.date_order
        return invoice_vals


    
class saleorderline(models.Model):
    _inherit = "sale.order.line"

    @api.multi
    def _action_procurement_create(self):
        res = super(saleorderline, self)._action_procurement_create()
        orders = list(set(x.order_id for x in self))
        procurement_jit=self.env['ir.module.module'].sudo().search([('name','=','procurement_jit'),('state','=','installed')])
        if not procurement_jit:
            for order in orders:
                if order.auto_workflow_process_id and order.auto_workflow_process_id.auto_check_availability:
                    for picking in order.picking_ids:
                        if picking.state=='confirmed':
                            picking.action_assign()
            return res
