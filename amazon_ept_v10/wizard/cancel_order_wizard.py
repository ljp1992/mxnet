from openerp import models, fields, api
from openerp.exceptions import Warning

class amazon_cancel_order_wizard(models.TransientModel):
    _name="amazon.cancel.order.wizard"
    
    amazon_cancel_order_line_ids=fields.One2many('amazon.cancel.order.line.wizard','cancel_order_wizard_id',string="Cancel Order Lines")

    @api.model
    def default_get(self,fields=None):
        active_id=self._context.get('active_id')   
        prod={}
        result=[]
        res={}
        sale_order_obj=self.env['amazon.sale.order.ept']     
        orders=sale_order_obj.search([('id','=',active_id),('instance_id','!=',False),('is_amazon_canceled','=',False)])
        for order in orders:
            for line in order.ept_order_line:
                prod={}
                if line.product_id and line.product_id.type!='service':
                    if not line.amazon_order_item_id:
                        raise Warning("Amazon Item id not found for product %s"%(line.product_id.default_code or line.name))
                    prod.update({'product_id':line.product_id.id,
                                 'sale_line_id':line.id,
                                 'ordered_qty':line.product_uom_qty,
                                 'message':'NoInventory',
                                 })
                    result.append((0, 0,prod))
        res.update({'amazon_cancel_order_line_ids':result})
        return res
    """Cancel Order In Amazon using this api we can not cancel partial order"""
    @api.multi
    def cancel_in_amazon(self):    
        active_id=self._context.get('active_id')   
        sale_order_obj=self.env['amazon.sale.order.ept']     
        order=sale_order_obj.browse(active_id)
        if not self.amazon_cancel_order_line_ids:
            return True
        sale_order_obj.send_cancel_request_to_amazon(self.amazon_cancel_order_line_ids,order.instance_id,order)
        order.write({'is_amazon_canceled':True})
        return True

class amazon_cancel_order_lines_wizard(models.TransientModel):
    _name="amazon.cancel.order.line.wizard"
    sale_line_id=fields.Many2one("amazon.sale.order.line.ept",string="Sales Line")
    product_id=fields.Many2one('product.product',string="Product")
    ordered_qty=fields.Float("Ordered Qty")
    cancel_order_wizard_id=fields.Many2one("amazon.cancel.order.wizard",string="Cancel Order Wizard")
    message=fields.Selection([('NoInventory','NoInventory'),
                              ('ShippingAddressUndeliverable','ShippingAddressUndeliverable'),
                              ('CustomerExchange','CustomerExchange'),
                              ('BuyerCanceled','BuyerCanceled'),
                              ('GeneralAdjustment','GeneralAdjustment'),
                              ('CarrierCreditDecision','CarrierCreditDecision'),
                              ('RiskAssessmentInformationNotValid','RiskAssessmentInformationNotValid'),
                              ('CarrierCoverageFailure','CarrierCoverageFailure'),
                              ('CustomerReturn','CustomerReturn'),
                              ('MerchandiseNotReceived','MerchandiseNotReceived')                              
                              ],string="Return Reason",default="NoInventory")    
