from openerp import models,fields,api
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import time
class amazon_operations_ept(models.Model):
    _name="amazon.operations.ept"
    _order = "sequence,id"
    
    @api.model
    def find_amazon_cron(self,action_id):
        xml_ids = ['amazon_ept_v10.ir_cron_import_amazon_orders',
                   'amazon_ept_v10.ir_cron_auto_update_order_status',
                   'amazon_ept_v10.ir_cron_auto_export_inventory',
                   'amazon_ept_v10.ir_cron_send_amazon_invoice_via_email',
                   'amazon_ept_v10.ir_cron_auto_import_settlement_report',
                   'amazon_ept_v10.ir_cron_auto_process_settlement_report'
                   ]
        cron_ids = []
        for xml_id in xml_ids:
            cron_exit = self.env.ref(xml_id,raise_if_not_found=False)
            if cron_exit:
                cron_ids.append(cron_exit.id)

        for instance in self.env['amazon.instance.ept'].search([]):
            for xml_id in xml_ids:
                cron_exit = self.env.ref(xml_id+'_instance_%d'%(instance.id),raise_if_not_found=False)
                if cron_exit:
                    cron_ids.append(cron_exit.id)
                            
        for seller in self.env['amazon.seller.ept'].search([]):
            for xml_id in xml_ids:
                cron_exit = self.env.ref(xml_id+'_seller_%d'%(seller.id),raise_if_not_found=False)
                if cron_exit:
                    cron_ids.append(cron_exit.id)
        
        return cron_ids
            
    @api.one
    def _count_operations(self):
        if self.action_id and self.display_record_count:
            if self.action_id.res_model == 'ir.cron':
                cron_ids = self.find_amazon_cron(self.action_id)
                self.count_record = len(cron_ids) or 0
            else:    
                domain =[]
                if self.action_id.domain:
                    domain = eval(self.action_id.domain)
                count = self.env[self.action_id.res_model].search_count(domain)
                self.count_record = count or 0

    @api.multi
    def count_all(self):
        picking_obj=self.env['stock.picking']
        amazon_sale_order_obj=self.env['amazon.sale.order.ept']
        amazon_product_obj=self.env['amazon.product.ept']
        invoice_obj=self.env['account.invoice']
        amazon_order_refund_obj=self.env['amazon.order.refund.ept']
        for record in self:
            pickings=picking_obj.search([('is_amazon_delivery_order','=',True),('state','=','confirmed')])
            record.count_picking_confirmed=len(pickings.ids)
            pickings=picking_obj.search([('is_amazon_delivery_order','=',True),('state','=','assigned')])
            record.count_picking_assigned=len(pickings.ids)
            pickings=picking_obj.search([('is_amazon_delivery_order','=',True),('state','=','partially_available')])
            record.count_picking_partial=len(pickings.ids)
            pickings=picking_obj.search([('is_amazon_delivery_order','=',True),('state','=','done')])
            record.count_picking_done=len(pickings.ids)

            count_picking_late=[('min_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed', 'partially_available')),('is_amazon_delivery_order','=',True)]
            count_picking_backorders=[('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting', 'partially_available')),('is_amazon_delivery_order','=',True)]
            count_picking=[('state', 'in', ('assigned', 'waiting', 'confirmed', 'partially_available')),('is_amazon_delivery_order','=',True)]

            count_picking=picking_obj.search(count_picking)
            count_picking_late=picking_obj.search(count_picking_late)
            count_picking_backorders=picking_obj.search(count_picking_backorders)
            
            if count_picking:
                record.rate_picking_late=len(count_picking_late.ids)*100/len(count_picking.ids)
                record.rate_picking_backorders=len(count_picking_backorders.ids)*100/len(count_picking.ids)
            else:
                record.rate_picking_late=0
                record.rate_picking_backorders=0
            record.count_picking_late=len(count_picking_late.ids)
            record.count_picking_backorders=len(count_picking_backorders.ids)
            orders=amazon_sale_order_obj.search([('state','in',['draft','sent'])])
            record.count_quotations=len(orders.ids)
            orders=amazon_sale_order_obj.search([('state','not in',['draft','sent','cancel'])])
            record.count_orders=len(orders.ids)

            products=amazon_product_obj.search([('instance_id','!=',False),('exported_to_amazon','=',True)])
            record.count_exported_products=len(products.ids)
            products=amazon_product_obj.search([('instance_id','!=',False),('exported_to_amazon','=',False)])
            record.count_ready_products=len(products.ids)
            
            invoices=invoice_obj.search([('amazon_instance_id','!=',False),('state','=','open'),('type','=','out_invoice')])
            record.count_open_invoices=len(invoices.ids)

            invoices=invoice_obj.search([('amazon_instance_id','!=',False),('state','=','paid'),('type','=','out_invoice')])
            record.count_paid_invoices=len(invoices.ids)
            
            draft_amazon_order_refunds=amazon_order_refund_obj.search([('state','=','draft')])
            record.count_draft_refunds=len(draft_amazon_order_refunds.ids)
            paid_amazon_order_refunds=amazon_order_refund_obj.search([('state','=','validate')])
            record.count_paid_refunds=len(paid_amazon_order_refunds.ids)
                        
    action_id = fields.Many2one('ir.actions.act_window',string='Action')
    url = fields.Char('Image URL')
    sequence = fields.Integer('Sequence')
    color = fields.Integer('Color')
    name = fields.Char('Name', translate=True, required=True)
    count_record = fields.Integer(compute=_count_operations, string='# Record')
    display_inline_image = fields.Boolean('Display Inline Image in Kanban ?')
    display_outline_image = fields.Boolean('Display Outline Image in Kanban ?')
    display_record_count = fields.Boolean('Display Number of records in Kanban ?')
    
    use_quotations=fields.Boolean('Quotations', help="Check this box to manage quotations")
    use_products=fields.Boolean("Products",help="Check this box to manage Products")
    use_invoices=fields.Boolean("Invoices",help="Check This box to manage Invoices")
    use_refunds=fields.Boolean("Refunds",help="Check This box to manage Refunds")
    use_delivery_orders=fields.Boolean("Delivery Orders",help="Check This box to manage Delivery Orders")
    use_amazon_workflow=fields.Boolean("Use Amazon Workflow",help="Check This box to manage Amazon Workflow")    
    use_log=fields.Boolean("Use Log",help="Check this box to manage Amazon Log")
    
    count_exported_products=fields.Integer("Count Exported Products",compute="count_all")
    count_ready_products=fields.Integer("Count Exported Products",compute="count_all")
    
    count_quotations=fields.Integer("Count Sales Quotations",compute="count_all")
    count_orders=fields.Integer("Count Sales Orders",compute="count_all")
        
    count_open_invoices=fields.Integer(string="Count Open Invoices",compute="count_all")
    count_paid_invoices=fields.Integer(string="Count Open Invoices",compute="count_all")
    
    count_draft_refunds=fields.Integer(string="Count Draft Refunds",compute="count_all")
    count_paid_refunds=fields.Integer(string="Count Paid Refunds",compute="count_all")
     
    rate_picking_late=fields.Integer(string="Count Rate Pickings",compute="count_all")
    rate_picking_backorders=fields.Integer(string="Count Back Orders",compute="count_all")
    count_picking_late=fields.Integer(string="Count Rate Pickings",compute="count_all")
    count_picking_backorders=fields.Integer(string="Count Back Orders",compute="count_all")

    count_picking_confirmed=fields.Integer(string="Count Picking Waiting",compute="count_all")
    count_picking_assigned=fields.Integer(string="Count Picking Waiting",compute="count_all")
    count_picking_partial=fields.Integer(string="Count Picking Waiting",compute="count_all")
    count_picking_done=fields.Integer(string="Count Picking Waiting",compute="count_all")
        
    @api.multi
    def view_data(self):
        result = {}
        if self.action_id:
            result = self.action_id and self.action_id.read()[0] or {}
            if self.action_id.res_model == 'ir.cron':
                cron_ids = self.find_amazon_cron(self.action_id)
                result['domain'] = "[('id','in',[" + ','.join(map(str, cron_ids)) + "])]"        
            else:
                result = self.action_id and self.action_id.read()[0] or {}
        return result     