from datetime import datetime, timedelta
from odoo import SUPERUSER_ID
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT

class sale_order_line(models.Model):
    _inherit = 'sale.order.line'
    
    @api.depends('state', 'product_uom_qty', 'qty_delivered', 'qty_to_invoice', 'qty_invoiced')
    def _compute_invoice_status(self):
        """
        Compute the invoice status of a SO line. Possible statuses:
        - no: if the SO is not in status 'sale' or 'done', we consider that there is nothing to
          invoice. This is also hte default value if the conditions of no other status is met.
        - to invoice: we refer to the quantity to invoice of the line. Refer to method
          `_get_to_invoice_qty()` for more information on how this quantity is calculated.
        - upselling: this is possible only for a product invoiced on ordered quantities for which
          we delivered more than expected. The could arise if, for example, a project took more
          time than expected but we decided not to invoice the extra cost to the client. This
          occurs onyl in state 'sale', so that when a SO is set to done, the upselling opportunity
          is removed from the list.
        - invoiced: the quantity invoiced is larger or equal to the quantity ordered.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if not line.order_id.invoice_policy or line.product_id.invoice_policy == 'cost':
                if line.state not in ('sale', 'done'):
                    line.invoice_status = 'no'
                elif not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    line.invoice_status = 'to invoice'
                elif line.state == 'sale' and line.product_id.invoice_policy == 'order' and\
                        float_compare(line.qty_delivered, line.product_uom_qty, precision_digits=precision) == 1:
                    line.invoice_status = 'upselling'
                elif float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) >= 0:
                    line.invoice_status = 'invoiced'
                else:
                    line.invoice_status = 'no'
            else:
                if line.state not in ('sale', 'done'):
                    line.invoice_status = 'no'
                elif not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    line.invoice_status = 'to invoice'
                elif line.state == 'sale' and line.order_id.invoice_policy == 'order' and\
                        float_compare(line.qty_delivered, line.product_uom_qty, precision_digits=precision) == 1:
                    line.invoice_status = 'upselling'
                elif float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) >= 0:
                    line.invoice_status = 'invoiced'
                else:
                    line.invoice_status = 'no'
    
    @api.depends('product_id.invoice_policy','order_id.invoice_policy', 'order_id.state')
    def _compute_qty_delivered_updateable(self):
        for line in self:
            if not line.order_id.invoice_policy or line.product_id.invoice_policy == 'cost':
                line.qty_delivered_updateable = line.product_id.invoice_policy in ('order', 'delivery') and line.order_id.state == 'sale' and line.product_id.track_service == 'manual'
            else:
                line.qty_delivered_updateable = line.order_id.invoice_policy in ('order', 'delivery') and line.order_id.state == 'sale' and line.product_id.track_service == 'manual'
            

    @api.depends('qty_invoiced', 'qty_delivered', 'product_uom_qty', 'order_id.state')
    def _get_to_invoice_qty(self):
        """
        Compute the quantity to invoice. If the invoice policy is order, the quantity to invoice is
        calculated from the ordered quantity. Otherwise, the quantity delivered is used.
        """
        for line in self:
            if not line.order_id.invoice_policy or line.product_id.invoice_policy == 'cost':
                if line.order_id.state in ['sale', 'done']:
                    if line.product_id.invoice_policy == 'order':
                        line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
                    else:
                        if line.product_id.type=='service':
                            if line.product_uom_qty-line.qty_invoiced>0.0:
                                line.qty_to_invoice=line.product_uom_qty-line.qty_invoiced
                        else:
                            line.qty_to_invoice = line.qty_delivered - line.qty_invoiced
                else:
                    line.qty_to_invoice = 0
            else:
                if line.order_id.state in ['sale', 'done']:
                    if line.order_id.invoice_policy == 'order':
                        line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
                    else:
                        if line.product_id.type=='service':
                            if line.product_uom_qty-line.qty_invoiced>0.0:
                                line.qty_to_invoice=line.product_uom_qty-line.qty_invoiced
                        else:
                            line.qty_to_invoice = line.qty_delivered - line.qty_invoiced
                else:
                    line.qty_to_invoice = 0
            
    qty_delivered_updateable = fields.Boolean(compute='_compute_qty_delivered_updateable', string='Can Edit Delivered', readonly=True, default=True)
    
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string='Invoice Status', compute='_compute_invoice_status', store=True, readonly=True, default='no')
    
    qty_to_invoice = fields.Float(
        compute='_get_to_invoice_qty', string='To Invoice', store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    
    
    