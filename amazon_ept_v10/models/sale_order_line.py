from openerp import models, fields, api
import openerp.addons.decimal_precision as dp

class amazon_sale_order_line_ept(models.Model):
    _name = 'amazon.sale.order.line.ept'
    _inherits={'sale.order.line':'sale_order_line_id'}
    amazon_order_id = fields.Many2one('amazon.sale.order.ept', string='Amazon Sales Reference',required=True,ondelete='cascade')
    sale_order_line_id = fields.Many2one('sale.order.line', string='OE Order Line',  required=True,ondelete="cascade")
    amazon_order_item_id = fields.Char(string="Amazon Order Item Id")
    instance_id=fields.Many2one("amazon.instance.ept",string="Instance",related="amazon_order_id.instance_id",required=True,readonly=True)
    amazon_product_id=fields.Many2one("amazon.product.ept","Amazon Product")
    amazon_order_qty = fields.Float("Amazon Order Qty")
    merchant_adjustment_item_id = fields.Char(string="Merchant Adjustment Item Id",default=False)    
    order_product_id=fields.Many2one('amazon.product.ept',string='Order Product')
    shipping_charge_ept = fields.Float("Shipping Charge",default=0.0,digits=dp.get_precision("Product Price"))
    shipping_discount_ept = fields.Float("Shipping Discount",default=0.0,digits=dp.get_precision("Product Price"))
    gift_wrapper_charge = fields.Float("Gift Wrapper Charge",default=0.0,digits=dp.get_precision("Product Price"))
    promotion_discount = fields.Float("Promotion Discount",default=0.0,digits=dp.get_precision("Product Price"))    
    shipping_charge_tax = fields.Float("Shipping Charge",default=0.0,digits=dp.get_precision("Product Price"))
    order_line_tax = fields.Float("Order Line Tax",default=0.0,digits=dp.get_precision("Product Price"))
    shipping_charge_tax = fields.Float("Shipping Charge Tax",default=0.0,digits=dp.get_precision("Product Price"))
    gift_wrapper_tax = fields.Float("Shipping Charge Tax",default=0.0,digits=dp.get_precision("Product Price"))
    return_reason=fields.Selection([('NoInventory','NoInventory'),
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
    promotion_claim_code=fields.Char("Promotion Claim Code")
    merchant_promotion_id=fields.Char("MerchantPromotionID") 
    gift_message_text=fields.Text("Gift Message Text")#for flat report
    gift_wrap_type=fields.Char("gift_wrap_type")#for flat report
    
    #for xml report
    @api.multi 
    def get_item_price_by_xml_report(self,order_line):
        tax_amount=float(order_line.get('Tax',0.0))
        item_price=float(order_line.get('Principal',0.0))
        return tax_amount+item_price
    
    @api.multi 
    def get_shipping_price_by_xml_report(self,order_line):
        item_price=float(order_line.get('Shipping',0.0))
        tax_amount=float(order_line.get('ShippingTax',0.0))
        return tax_amount+item_price

    @api.multi 
    def get_item_tax_amount_by_xml_report(self,order_line,item_price):
        tax_amount=float(order_line.get('Tax',0.0))
        return tax_amount
    @api.multi 
    def get_shipping_tax_amount_by_xml_report(self,order_line,shipping_charge):
        tax_amount=float(order_line.get('ShippingTax',0.0))
        return tax_amount
  
    @api.model
    def create_sale_order_line_by_xml_report(self,order_line,instance,amazon_order):
        fulfillment_by = amazon_order.fulfillment_by
        amazon_product = self.search_or_create_or_update_product_by_xml_report(order_line,instance,fulfillment_by)
        prod_order_line=False
        price_component = order_line.get('ItemPrice',{}).get('Component',[])
        prices_dict = {}
        amazon_order_item_id = order_line.get('AmazonOrderItemCode',{}).get('value','')
        for comp in price_component:
            price_type = comp.get('Type',{}).get('value')
            amount = float(comp.get('Amount',{}).get('value',0.0))
            prices_dict.update({price_type:amount})
            
        """selling Product Line"""
        if amazon_product:                          
            item_price = self.get_item_price_by_xml_report(prices_dict)
            order_qty = float(order_line.get('Quantity',{}).get('value',0.0))
            title=order_line.get('Title',{}).get('value',False)
            qty_price_dict = self.calculate_order_qty_and_price_based_on_asin_qty(amazon_product,item_price,order_qty)
            qty_price_dict.update({'amazon_order_qty':order_qty,'AmazonOrderItemCode':amazon_order_item_id})
            tax_amount=self.get_item_tax_amount_by_xml_report(prices_dict,item_price)
            order_line_vals = self.create_sale_order_line_vals_by_xml_report(order_line,qty_price_dict,False, amazon_product,amazon_product.product_id, amazon_order, instance,title)
            order_line_vals.update({'line_tax_amount':tax_amount})
            prod_order_line=self.create(order_line_vals)
        
        """Shipment Charge Line"""
        shipping_charge = self.get_shipping_price_by_xml_report(prices_dict)
        shipping_tax = self.get_shipping_tax_amount_by_xml_report(prices_dict, shipping_charge)
        if shipping_charge:
            shipment_product = False
            shipping_charge_description = ''
            shipment_product=amazon_order.carrier_id and amazon_order.carrier_id.product_id 

            if not shipment_product and instance.shipment_charge_product_id:
                shipment_product = instance.shipment_charge_product_id
            else:
                shipping_charge_description = "Shipping and Handling"
                
            qty_price_dict.update({'order_qty':1,'amount_per_unit':shipping_charge,'amazon_order_qty':1,'AmazonOrderItemCode':amazon_order_item_id+'_ship'})
            order_line_vals = self.create_sale_order_line_vals_by_xml_report(order_line,qty_price_dict,False,False,shipment_product, amazon_order, instance,shipment_product.name or shipping_charge_description)
            prod_order_line and prod_order_line.write({'shipping_charge_ept':shipping_charge,'shipping_charge_tax':shipping_tax})
            order_line_vals.update({'line_tax_amount':shipping_tax})
            self.create(order_line_vals)                 

        promotion_discount=order_line.get('Promotion',{}).get('Component',[])
        if isinstance(promotion_discount,dict):
            promotion_discount=[promotion_discount]
      

        total_promotion_discount=0.0
        for discount in promotion_discount:
            total_promotion_discount+=float(discount.get('Amount',{}).get('value'))  
        if total_promotion_discount<0.0:
            promotion_claim_code=order_line.get('Promotion',{}).get('PromotionClaimCode',{}).get('value')
            merchant_promotion_id=order_line.get('Promotion',{}).get('MerchantPromotionID',{}).get('value')
            qty_price_dict.update({'order_qty':1,'amount_per_unit':total_promotion_discount,'amazon_order_qty':1})
            promotion_discount_description ='Promotion Discount'         
            promotion_discount_product= instance.promotion_discount_product_id
            order_line_vals = self.create_sale_order_line_vals_by_xml_report(order_line,qty_price_dict,False,False,promotion_discount_product, amazon_order, instance,promotion_discount_product.name or promotion_discount_description)

            order_line_vals.update({'promotion_claim_code':promotion_claim_code,'merchant_promotion_id':merchant_promotion_id})
            prod_order_line and prod_order_line.write({'promotion_discount':total_promotion_discount,
                                                       'promotion_claim_code':promotion_claim_code,
                                                       'merchant_promotion_id':merchant_promotion_id
                                                       })
            self.create(order_line_vals)

    def create_sale_order_line_vals_by_xml_report(self,order_line,qty_price_dict,tax_id,amazon_product=False,odoo_product=False,amazon_order=False,instance=False,title=False):
        order_qty=qty_price_dict.get('order_qty')
        
        """If In amazon Response we got 0.0 amazon in tax then search from the product if we got tax in product then we 
          set default tax based on instance configuration"""
          
        new_record=self.env['sale.order.line'].new({'order_id':amazon_order.sale_order_id.id,
                  'company_id':amazon_order.company_id.id,
                  'product_id':amazon_product and amazon_product.product_id.id or odoo_product and odoo_product.id or False,
                  'product_uom':amazon_product and amazon_product.product_tmpl_id.uom_id or odoo_product and odoo_product.product_tmpl_id.uom_id,
                  'name':title
                  })
        new_record.product_id_change()
        order_vals=new_record._convert_to_write(new_record._cache)          
        order_vals.update({
            'amazon_order_id':amazon_order.id,
            'instance_id':instance.id,
            'product_uom_qty' : order_qty,
            'amazon_order_qty':order_line.get('Quantity',{}).get('value',0.0),
            'price_unit' : qty_price_dict.get('amount_per_unit'),
            'customer_lead' :amazon_product and amazon_product.sale_delay or False,
            'invoice_status' : False,
            'state' : 'draft',
            'amazon_order_item_id':order_line.get('AmazonOrderItemCode',{}).get('value'),
            'discount':0.0,
            'amazon_product_id':amazon_product and amazon_product.id or False,
            'product_uom':new_record.product_uom.id
        })                
        return order_vals
    
    @api.multi
    def search_or_create_or_update_product_by_xml_report(self,order_line,instance,fulfillment_by):
        amazon_product_obj=self.env['amazon.product.ept']
        seller_sku=order_line.get('SKU',{}).get('value',False)
        domain = [('instance_id','=',instance.id)]
        seller_sku and domain.append(('seller_sku','=',seller_sku))

        """Search Product Which we will deliver to the customer"""
        amazon_product = amazon_product_obj.search_amazon_product(instance.id,seller_sku)
                        
        if not amazon_product:
            odoo_product = amazon_product_obj.search_product(seller_sku)
            product_vals = self.create_product_vals(order_line,instance, odoo_product,fulfillment_by)
            sku = order_line.get('SKU',{}).get('value')
            if not odoo_product:
                product_vals.update({'default_code':sku})
            product_vals.update({'seller_sku':sku})
            amazon_product = amazon_product_obj.create(product_vals)
        return amazon_product and amazon_product[0]
    
    #for flat report
    @api.multi 
    def get_item_price_by_flat_report(self,order_line):
        tax_amount=float(order_line.get('item_tax',0.0))
        item_price=float(order_line.get('item_price',0.0))
        return tax_amount+item_price
    
    @api.multi 
    def get_shipping_price_by_flat_report(self,order_line):
        item_price=float(order_line.get('shipping_price',0.0))
        tax_amount=float(order_line.get('shipping_tax',0.0))
        return tax_amount+item_price
    
    @api.multi 
    def get_gift_wrapper_price_by_flat_report(self,order_line):
        item_price=float(order_line.get('gift_wrap_price',0.0))
        tax_amount=float(order_line.get('gift_wrap_tax',0.0))
        return item_price+tax_amount

    @api.multi 
    def get_item_tax_amount_by_flat_report(self,order_line,item_price):
        tax_amount=float(order_line.get('item_tax',0.0))
        return tax_amount
    @api.multi 
    def get_shipping_tax_amount_by_flat_report(self,order_line,shipping_charge):
        tax_amount=float(order_line.get('shipping_tax',0.0))
        return tax_amount
    
    @api.multi 
    def get_gift_wrapper_tax_amount_by_flat_report(self,order_line,gift_wrapper_charge):
        tax_amount=float(order_line.get('gift_wrap_tax',0.0))
        return tax_amount  
    
    @api.model
    def create_sale_order_line_by_flat_report(self,order_line,instance,amazon_order):
        fulfillment_by = amazon_order.fulfillment_by
        amazon_product = self.search_or_create_or_update_product_by_flat_report(order_line,instance,fulfillment_by)
        prod_order_line=False
        amazon_order_item_id = order_line.get('order_item_id')
            
        """selling Product Line"""
        if amazon_product:                          
            item_price = self.get_item_price_by_flat_report(order_line)
            order_qty = float(order_line.get('qty',0.0))
            title=order_line.get('product_name',False)
            qty_price_dict = self.calculate_order_qty_and_price_based_on_asin_qty(amazon_product,item_price,order_qty)
            qty_price_dict.update({'amazon_order_qty':order_qty,'AmazonOrderItemCode':amazon_order_item_id})
            tax_amount=self.get_item_tax_amount_by_flat_report(order_line,item_price)
            order_line_vals = self.create_sale_order_line_vals_by_flat_report(order_line,qty_price_dict,False, amazon_product,amazon_product.product_id, amazon_order, instance,title)
            order_line_vals.update({'line_tax_amount':tax_amount})
            prod_order_line=self.create(order_line_vals)
        
        """Shipment Charge Line"""
        shipping_charge = self.get_shipping_price_by_flat_report(order_line)
        shipping_tax = self.get_shipping_tax_amount_by_flat_report(order_line, shipping_charge)
        if shipping_charge:
            shipment_product = False
            shipping_charge_description = ''
            shipment_product=amazon_order.carrier_id and amazon_order.carrier_id.product_id 

            if not shipment_product and instance.shipment_charge_product_id:
                shipment_product = instance.shipment_charge_product_id
            else:
                shipping_charge_description = "Shipping and Handling"
                
            qty_price_dict.update({'order_qty':1,'amount_per_unit':shipping_charge,'amazon_order_qty':1,'AmazonOrderItemCode':amazon_order_item_id+'_ship'})
            order_line_vals = self.create_sale_order_line_vals_by_flat_report(order_line,qty_price_dict,False,False,shipment_product, amazon_order, instance,shipment_product.name or shipping_charge_description)
            prod_order_line and prod_order_line.write({'shipping_charge_ept':shipping_charge,'shipping_charge_tax':shipping_tax})
            order_line_vals.update({'line_tax_amount':shipping_tax})
            self.create(order_line_vals)          
            
            
        """Gift Wrapper Line"""
        gift_wrapper_charge=self.get_gift_wrapper_price_by_flat_report(order_line)        
        gift_wrapper_tax=self.get_gift_wrapper_tax_amount_by_flat_report(order_line,gift_wrapper_charge)
        if gift_wrapper_charge:
            gift_wrapper_product=False
            gift_wrapper_charge_description=''
            gift_wrapper_product=instance.gift_wrapper_product_id
            if not gift_wrapper_product:
                gift_wrapper_charge_description='Gift Wrapper Fee'
            
            qty_price_dict.update({'order_qty':1,'amount_per_unit':gift_wrapper_charge})
            order_line_vals=self.create_sale_order_line_vals_by_flat_report(order_line, qty_price_dict, False,False,gift_wrapper_product or False, amazon_order, instance,gift_wrapper_product and gift_wrapper_product.name or gift_wrapper_charge_description)
            prod_order_line and prod_order_line.write({'gift_wrapper_charge':gift_wrapper_charge,'gift_wrapper_tax':tax_amount})
            order_line_vals.update({'line_tax_amount':gift_wrapper_tax})
            self.create(order_line_vals)
           
        """Promotion Discount """
        promotion_discount=order_line.get('item_promotion_discount',0.0)
        promotion_claim_code=order_line.get('item_promotion_id',False)
        if float(promotion_discount)<0.0:
            qty_price_dict.update({'order_qty':1,'amount_per_unit':promotion_discount,'amazon_order_qty':1})
            promotion_discount_description ='Item Promotion Discount '         
            promotion_discount_product= instance.promotion_discount_product_id
            order_line_vals = self.create_sale_order_line_vals_by_flat_report(order_line,qty_price_dict,False,False,promotion_discount_product, amazon_order, instance,promotion_discount_description)
            prod_order_line and prod_order_line.write({'promotion_discount':promotion_discount,'promotion_claim_code':promotion_claim_code})
            self.create(order_line_vals)
            
        """Shipment Discount Line"""
        ship_promotion_discount=order_line.get('ship_promotion_discount',0.0)
        ship_promotion_claim_code=order_line.get('ship_promotion_id',False)
        if float(ship_promotion_discount)<0.0:
            qty_price_dict.update({'order_qty':1,'amount_per_unit':ship_promotion_discount,'amazon_order_qty':1})
            ship_promotion_discount_description ='Ship Promotion Discount'         
            promotion_discount_product= instance.promotion_discount_product_id
            order_line_vals = self.create_sale_order_line_vals_by_flat_report(order_line,qty_price_dict,False,False,promotion_discount_product, amazon_order, instance,ship_promotion_discount_description)
            prod_order_line and prod_order_line.write({'promotion_discount':ship_promotion_discount,'promotion_claim_code':ship_promotion_claim_code})
            self.create(order_line_vals)

    def create_sale_order_line_vals_by_flat_report(self,order_line,qty_price_dict,tax_id,amazon_product=False,odoo_product=False,amazon_order=False,instance=False,title=False):
        order_qty=qty_price_dict.get('order_qty')
        
        """If In amazon Response we got 0.0 amazon in tax then search from the product if we got tax in product then we 
          set default tax based on instance configuration"""
          
        new_record=self.env['sale.order.line'].new({'order_id':amazon_order.sale_order_id.id,
                  'company_id':amazon_order.company_id.id,
                  'product_id':amazon_product and amazon_product.product_id.id or odoo_product and odoo_product.id or False,
                  'product_uom':amazon_product and amazon_product.product_tmpl_id.uom_id or odoo_product and odoo_product.product_tmpl_id.uom_id,
                  'name':title 
                  })
        new_record.product_id_change()
        order_vals=new_record._convert_to_write(new_record._cache)          
        order_vals.update({
            'amazon_order_id':amazon_order.id,
            'instance_id':instance.id,
            'product_uom_qty' : order_qty,
            'amazon_order_qty':order_line.get('qty',0.0),
            'price_unit' : qty_price_dict.get('amount_per_unit'),
            'customer_lead' :amazon_product and amazon_product.sale_delay or False,
            'invoice_status' : False,
            'state' : 'draft',
            'amazon_order_item_id':order_line.get('order_item_id'),
            'discount':0.0,
            'gift_wrap_type':order_line.get('gift_wrap_type'),
            'gift_message_text':order_line.get('gift_message_text'),
            'amazon_product_id':amazon_product and amazon_product.id or False,
            'product_uom':new_record.product_uom.id
            
        })                
        return order_vals
    
    @api.multi
    def search_or_create_or_update_product_by_flat_report(self,order_line,instance,fulfillment_by):
        amazon_product_obj=self.env['amazon.product.ept']
        seller_sku=order_line.get('sku',False)
#         domain = [('instance_id','=',instance.id)]
#         seller_sku and domain.append(('seller_sku','=',seller_sku))

        """Search Product Which we will deliver to the customer"""
        amazon_product = amazon_product_obj.search_amazon_product(instance.id,seller_sku)
                        
        if not amazon_product:
            odoo_product = amazon_product_obj.search_product(seller_sku)
            product_vals = self.create_product_vals(order_line,instance, odoo_product,fulfillment_by)
            sku = order_line.get('sku')
            if not odoo_product:
                product_vals.update({'default_code':sku})
            product_vals.update({'seller_sku':sku})
            amazon_product = amazon_product_obj.create(product_vals)
        return amazon_product and amazon_product[0]
    
    @api.multi
    def unlink(self):
        unlink_ids = None
        unlink_sale_order_ids = None
        for line in self:
            # Check if Amazon order line still exists, in case it has been unlinked by unlinking its Odoo Order
            if not line.exists():
                continue
            odoo_order_line = line.sale_order_line_id
            # Check if the Amazon order line is last order of this sale order line
            other_order_ids = self.search([('sale_order_line_id', '=', odoo_order_line.id), ('id', '!=', line.id)])
            if not other_order_ids:
                if not unlink_sale_order_ids:
                    unlink_sale_order_ids= odoo_order_line
                else:
                    unlink_sale_order_ids = unlink_sale_order_ids + odoo_order_line
            if not unlink_ids:
                unlink_ids = line
            else:
                unlink_ids = unlink_ids + line
        res = super(amazon_sale_order_line_ept, unlink_ids).unlink()        
        # delete sale order line after calling super, as deleting sale order line could lead to deleting
        # amazon sale order line due to ondelete='cascade'
        unlink_sale_order_ids.unlink()
        return res
    
    @api.model
    def create(self,vals):
        amazon_order_id=vals.get('amazon_order_id')        
        amazon_order=amazon_order_id and self.env['amazon.sale.order.ept'].browse(amazon_order_id)
        order_id=amazon_order and amazon_order.sale_order_id and amazon_order.sale_order_id.id or False
        order_id and vals.update({'order_id':order_id})
        return super(amazon_sale_order_line_ept,self).create(vals)

    @api.multi 
    def get_item_price(self,order_line):
        tax_amount=float(order_line.get('ItemTax',{}).get('Amount',{}).get('value',0.0))
        item_price=float(order_line.get('ItemPrice',{}).get('Amount',{}).get('value',0.0))
        return tax_amount+item_price
    @api.multi 
    def get_shipping_price(self,order_line):
        tax_amount=float(order_line.get('ShippingTax',{}).get('Amount',{}).get('value',0.0))
        item_price=float(order_line.get('ShippingPrice',{}).get('Amount',{}).get('value',0.0))
        return tax_amount+item_price

    @api.multi 
    def get_gift_wrapper_price(self,order_line):
        item_price=float(order_line.get('GiftWrapPrice',{}).get('Amount',{}).get('value',0.0))
        tax_amount=float(order_line.get('GiftWrapTax',{}).get('Amount',{}).get('value',0.0))
        return tax_amount+item_price

    @api.multi 
    def get_item_tax_amount(self,order_line,item_price):
        tax_amount=float(order_line.get('ItemTax',{}).get('Amount',{}).get('value',0.0))
        return tax_amount
    @api.multi 
    def get_shipping_tax_amount(self,order_line,shipping_charge):
        tax_amount=float(order_line.get('ShippingTax',{}).get('Amount',{}).get('value',0.0))
        return tax_amount
    @api.multi 
    def get_gift_wrapper_tax_amount(self,order_line,git_wrapper_charge):
        tax_amount=float(order_line.get('GiftWrapTax',{}).get('Amount',{}).get('value',0.0))
        return tax_amount
    
    @api.multi
    def create_sale_order_line(self,order_line,instance,amazon_order,create_service_line=True):
        fulfillment_by = amazon_order.fulfillment_by
        product_details=self.search_or_create_or_update_product(order_line,instance,fulfillment_by)
        prod_order_line=False
        """selling Product Line"""                            
        amazon_product=product_details.get('sale_product',False)  
        if amazon_product:                          
            item_price=self.get_item_price(order_line)
            order_qty=order_line.get('QuantityOrdered',{}).get('value',0.0)
            title=order_line.get('Title',{}).get('value',False)
            qty_price_dict=self.calculate_order_qty_and_price_based_on_asin_qty(amazon_product,float(item_price),float(order_qty))
            tax_amount=self.get_item_tax_amount(order_line,item_price)            
            tax_id=False
            order_line_vals=self.create_sale_order_line_vals(order_line, qty_price_dict, tax_id, amazon_product,amazon_product.product_id and amazon_product.product_id.id, amazon_order, instance,title)
            order_line_vals.update({'order_line_tax':tax_amount})
            prod_order_line=self.create(order_line_vals)
        
        if not create_service_line:
            return True
        """Shipment Charge Line"""
        shipment_product=amazon_order.carrier_id and amazon_order.carrier_id.product_id or product_details.get('shipment_charge',False)
        shipping_charge_description=product_details.get('shipping_charge_description',False)
        if shipment_product or shipping_charge_description:                            
            #shipping_discount=float(order_line.get('ShippingDiscount',{}).get('Amount',{}).get('value',0.0))
            shipping_charge=self.get_shipping_price(order_line)
            tax_amount=self.get_shipping_tax_amount(order_line,shipping_charge)
#             tax_amount=float(order_line.get('ShippingTax',{}).get('Amount',{}).get('value',0.0))/100
            #tax_id=self.calculate_tax_per_item(tax_amount,instance)
            #qty_price_dict.update({'order_qty':1,'amount_per_unit':shipping_charge-shipping_discount})
            tax_id=False
            qty_price_dict.update({'order_qty':1,'amount_per_unit':shipping_charge})
            order_line_vals=self.create_sale_order_line_vals(order_line, qty_price_dict, tax_id,False,shipment_product or False, amazon_order,instance,(shipping_charge_description and shipping_charge_description) or (shipment_product and shipment_product.name or 'Shipping Charge') )
            order_line_vals.update({'is_delivery':True})
            order_line_vals.update({'is_delivery':True,
                                    'order_product_id':amazon_product.id})
            prod_order_line and prod_order_line.write({'shipping_charge_ept':shipping_charge,'shipping_charge_tax':tax_amount})
            self.create(order_line_vals)
        
        """Shipment Discount Line"""
        shipment_discount_product = product_details.get('shipment_discount_product',False)
        shipping_discount_description = product_details.get('shipping_discount_description',False)
        if shipment_discount_product or shipping_discount_description:                            
            shipping_discount = float(order_line.get('ShippingDiscount',{}).get('Amount',{}).get('value',0.0))
            qty_price_dict.update({'order_qty':1,'amount_per_unit':shipping_discount})
            order_line_vals = self.create_sale_order_line_vals(order_line, qty_price_dict, False,False,shipment_discount_product or False, amazon_order,instance,(shipping_discount_description and shipping_discount_description) or (shipment_discount_product and shipment_discount_product.name or 'Shipping Discount'))
            prod_order_line and prod_order_line.write({'shipping_discount_ept':shipping_discount})
            self.create(order_line_vals)
            
        """Gift Wrapper Line"""
        gift_wrapper_product=product_details.get('gift_wrapper_charge',False)        
        gift_wrapper_description=product_details.get('gift_wrapper_description',False)
        if gift_wrapper_product or gift_wrapper_description:
            git_wrapper_charge=self.get_gift_wrapper_price(order_line)
            tax_amount=self.get_gift_wrapper_tax_amount(order_line,git_wrapper_charge)                    
            tax_id=False
            qty_price_dict.update({'order_qty':1,'amount_per_unit':git_wrapper_charge})
            order_line_vals=self.create_sale_order_line_vals(order_line, qty_price_dict, tax_id,False,gift_wrapper_product  or False, amazon_order, instance,(gift_wrapper_description and gift_wrapper_description) or (gift_wrapper_product and gift_wrapper_product.name or 'Gift Wrapper Fee') )
            prod_order_line and prod_order_line.write({'gift_wrapper_charge':git_wrapper_charge,'gift_wrapper_tax':tax_amount})
            self.create(order_line_vals)
        
        """Promotion Discount """
        promotion_discount_product=product_details.get('promotion_discount',False)
        promotion_discount_description=product_details.get('promotion_discount_description',False)
        if promotion_discount_product or promotion_discount_description:
            promotion_discount=float(order_line.get('PromotionDiscount',{}).get('Amount',{}).get('value',0.0))    
            if promotion_discount>0.0:
                promotion_discount=promotion_discount*-1  
            qty_price_dict.update({'order_qty':1,'amount_per_unit':promotion_discount})
            order_line_vals=self.create_sale_order_line_vals(order_line, qty_price_dict, tax_id,False,promotion_discount_product or False, amazon_order, instance,(promotion_discount_description and promotion_discount_description) or (promotion_discount_product and promotion_discount_product.name or 'Promotion Discount'))
            prod_order_line and prod_order_line.write({'promotion_discount':promotion_discount})
            self.create(order_line_vals)                            
        return True
    
    """
        This Method Search  Or Create Product into ERP ,If In shipment,gift wrapper,promotion product,Cod product Configured in the instance 
        then we will take set product in the sale order line or we will set only description in the sale order line
        we have not create this type of product from  the code
    """
    @api.multi
    def search_or_create_or_update_product(self,order_line,instance,fulfillment_by):
        amazon_product_obj=self.env['amazon.product.ept']
        asin_number=order_line.get('ASIN',{}).get('value',False)
        seller_sku=order_line.get('SellerSKU',{}).get('value',False)
        domain = [('instance_id','=',instance.id)]
        
        shipment_charge_product,gift_wrapper_product,promotion_discount_product,cod_charge_product_id=False,False,False,False
        shipment_discount_product,shipping_discount_description=False,False
        shipping_charge_description,gift_wrapper_description,promotion_discount_description,cod_charge_description=False,False,False,False
        #asin_number and domain.append(('product_asin','=',asin_number))
        seller_sku and domain.append(('seller_sku','=',seller_sku))


        """Search Product Which we will deliver to the customer"""
        odoo_product = amazon_product_obj.search_product(seller_sku)
        amazon_product = amazon_product_obj.search_amazon_product(instance.id,seller_sku,fulfillment_by)
        if not amazon_product:
            product_vals = self.create_product_vals(order_line,instance, odoo_product,fulfillment_by)
            amazon_product = amazon_product_obj.create(product_vals)
        
        if not amazon_product.product_asin:
            amazon_product.write({'product_asin':asin_number})
                
        """Create Or Search Shipment Charge Product"""
        if float(order_line.get('ShippingPrice',{}).get('Amount',{}).get('value',0.0))>0.0:        
            if instance.shipment_charge_product_id:
                shipment_charge_product=instance.shipment_charge_product_id
            else:
                shipping_charge_description = "Shipping and Handling"

        """Create Or Search Shipment Discount Product"""
        if float(order_line.get('ShippingDiscount',{}).get('Amount',{}).get('value',0.0))>0.0:
            if instance.ship_discount_product_id:
                shipment_discount_product = instance.ship_discount_product_id
            else:
                shipping_discount_description = "Shipping Discount"
                        
        """Create Or Search GiftWrapper Product"""
        if float(order_line.get('GiftWrapPrice',{}).get('Amount',{}).get('value',0.0))>0.0:
            if instance.gift_wrapper_product_id:
                gift_wrapper_product= instance.gift_wrapper_product_id
            else:
                gift_wrapper_description = 'Gift Wrapping'
        
        """Create Or Search Promotion Discount Product"""
        if float(order_line.get('PromotionDiscount',{}).get('Amount',{}).get('value',0.0))>0.0:
            if instance.promotion_discount_product_id:
                promotion_discount_product= instance.promotion_discount_product_id
            else:
                promotion_discount_description ='Promotion Discount'         

        return {
                'sale_product':amazon_product,
                'shipment_charge':shipment_charge_product,
                'gift_wrapper_charge':gift_wrapper_product,
                'promotion_discount':promotion_discount_product,
                'cod_charge':cod_charge_product_id,
                'shipping_charge_description':shipping_charge_description,
                'gift_wrapper_description':gift_wrapper_description,
                'promotion_discount_description':promotion_discount_description,
                'cod_charge_description':cod_charge_description,
                'shipment_discount_product':shipment_discount_product,
                'shipping_discount_description':shipping_discount_description,
                }
    
    def create_sale_order_line_vals(self,order_line,qty_price_dict,tax_id,amazon_product=False,odoo_product=False,amazon_order=False,instance=False,title=False):

        """If In amazon Response we got 0.0 amazon in tax then search from the product if we got tax in product then we 
          set default tax based on instance configuration"""
           
        new_record=self.env['sale.order.line'].new({'order_id':amazon_order.sale_order_id.id,
                  'company_id':amazon_order.company_id.id,
                  'product_id':amazon_product and amazon_product.product_id.id or odoo_product and odoo_product.id or False,
                  'product_uom':amazon_product and amazon_product.product_tmpl_id.uom_id or odoo_product and odoo_product.product_tmpl_id.uom_id,
                  'name':title
                  })
        new_record.product_id_change()
        order_vals=new_record._convert_to_write({name: new_record[name] for name in new_record._cache})          

        order_qty=qty_price_dict.get('order_qty')
        order_vals.update({
            'amazon_order_id':amazon_order.id,
            'instance_id':instance.id,
            'product_uom_qty' : order_qty,
            'amazon_order_qty':order_line.get('QuantityOrdered',{}).get('value',0.0),
            'price_unit' : qty_price_dict.get('amount_per_unit'),
            'customer_lead' :amazon_product and amazon_product.sale_delay or False,
            'invoice_status' : False,
            'state' : 'draft',
            'amazon_order_item_id':order_line.get('OrderItemId',{}).get('value'),
            'discount':0.0,
            'amazon_product_id':amazon_product and amazon_product.id or False,
            'product_uom':new_record.product_uom.id
        })                
        return order_vals
    @api.model
    def createAccountTax(self,value,price_included,company):
        accounttax_obj = self.env['account.tax']
        if price_included:
            name='%s_(%s %s)_%s'%('Sales Tax Price Included',str(value*100),'%',company.name)
        else:
            name='%s_(%s %s)_%s'%('Sales Tax Price Excluded',str(value*100),'%',company.name)            
        accounttax_id = accounttax_obj.create({'name':name,'amount':float(value),'type_tax_use':'sale','price_include':price_included,'company_id':company.id})
        return accounttax_id

    @api.model
    def calculate_tax_per_item(self,amount,instance):
        tax_id=[]
        if instance.price_tax_included:
            if amount!=0.0:
                acctax_id = self.env['account.tax'].search([('price_include','=',True),('type_tax_use', '=', 'sale'), ('amount', '=', amount),('company_id','=',instance.warehouse_id.company_id.id)])
                if not acctax_id:
                    acctax_id = self.createAccountTax(amount,True,instance.warehouse_id.company_id)
                if acctax_id:
                    tax_id = [(6, 0, acctax_id.ids)]
            else:
                tax_id=[]
        else:
            if amount!=0.0:
                acctax_id = self.env['account.tax'].search([('price_include','=',False),('type_tax_use', '=', 'sale'), ('amount', '=', amount),('company_id','=',instance.warehouse_id.company_id.id)])
                if not acctax_id:
                    acctax_id = self.createAccountTax(amount,False,instance.warehouse_id.company_id)
                if acctax_id:
                    tax_id=[(6,0,acctax_id.ids)]
            else:
                tax_id=[]
        return tax_id        
    @api.multi
    def calculate_order_qty_and_price_based_on_asin_qty(self,amazon_product,item_price,order_qty):
        if amazon_product and (not amazon_product.allow_package_qty): 
            if order_qty>0:
                item_price=float(item_price)/float(order_qty)
            return {'order_qty':order_qty,'amount_per_unit':item_price}        
        if amazon_product and order_qty > 0.0:
            asin_qty=amazon_product.asin_qty * order_qty
            amount_per_unit = item_price/asin_qty
            order_qty = asin_qty                                                                                                                        
        elif order_qty and order_qty > 0.0:
            amount_per_unit = item_price / order_qty
        else:
            amount_per_unit = 0.0
        return {'order_qty':order_qty,'amount_per_unit':amount_per_unit}
    
    @api.multi
    def create_product_vals(self,order_line,instance,odoo_product,fulfillment_by):
        sku = order_line.get('SellerSKU',{}).get('value',False) or ( odoo_product and odoo_product[0].default_code) or False
        vals={
              'instance_id':instance.id,
              'product_asin':order_line.get('ASIN',{}).get('value',False),
              'seller_sku':sku,
              'type':odoo_product and odoo_product[0].type or 'product', 
              'product_id':odoo_product and odoo_product[0].id or False,             
              'purchase_ok' :True,
              'sale_ok' :True,    
              'exported_to_amazon':True,
              'fulfillment_by' : fulfillment_by,          
              }
        if not odoo_product:
            vals.update({'name':order_line.get('Title',{}).get('value'),'default_code':sku})

        return vals    

class sale_order_line(models.Model):
    _inherit="sale.order.line"
    
    line_tax_amount = fields.Float("Order Line Tax",default=0.0,digits=dp.get_precision("Product Price"))
