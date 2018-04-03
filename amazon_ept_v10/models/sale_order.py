from openerp import models, fields,api,_
import time
from datetime import timedelta,datetime
from dateutil import parser
from openerp.exceptions import Warning
from openerp.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Orders,Feeds
import pytz
utc = pytz.utc
class sale_order(models.Model):
    _inherit="sale.order"
 
    @api.multi
    def _prepare_invoice(self):
        """We need to Inherit this method to set Amazon instance id in Invoice"""
        res = super(sale_order,self)._prepare_invoice()
        amazon_order=self.env['amazon.sale.order.ept'].search([('sale_order_id','=',self.id),('amazon_reference','!=',False)])
        amazon_order and res.update({'amazon_instance_id' : amazon_order.instance_id and amazon_order.instance_id.id or False})
        return res
    
    
    @api.multi
    @api.onchange('partner_shipping_id','partner_id')
    def onchange_partner_shipping_id(self):
        res = super(sale_order,self).onchange_partner_shipping_id()
        fiscal_position = False        
        if self.warehouse_id:
            warehouse = self.warehouse_id
            origin_country_id = warehouse.partner_id and warehouse.partner_id.country_id and warehouse.partner_id.country_id.id or False
            origin_country_id = origin_country_id or (warehouse.company_id.partner_id.country_id and warehouse.company_id.partner_id.country_id.id or False)
            fiscal_position = self.env['account.fiscal.position'].with_context({'origin_country_ept':origin_country_id}).get_fiscal_position(self.partner_id.id, self.partner_shipping_id.id)
            self.fiscal_position_id = fiscal_position
        return res

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        print "test"
        warehouse=self.warehouse_id
        if warehouse and self.partner_id:
            origin_country_id = warehouse.partner_id and warehouse.partner_id.country_id and warehouse.partner_id.country_id.id or False
            origin_country_id = origin_country_id or (warehouse.company_id.partner_id.country_id and warehouse.company_id.partner_id.country_id.id or False)
            company_id = warehouse.company_id.id
            if not company_id:
                company_id = self._get_default_company()
            fiscal_position_id = self.env['account.fiscal.position'].with_context({'origin_country_ept':origin_country_id}).get_fiscal_position(self.partner_id.id,self.partner_shipping_id.id)
            self.fiscal_position_id=fiscal_position_id

    
class amazon_sale_order_ept(models.Model):
    _name="amazon.sale.order.ept"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _inherits={"sale.order":'sale_order_id'}
    _order = 'id desc'
     

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        warehouse=self.warehouse_id
        if warehouse and self.partner_id:
            origin_country_id = warehouse.partner_id and warehouse.partner_id.country_id and warehouse.partner_id.country_id.id or False
            origin_country_id = origin_country_id or (warehouse.company_id.partner_id.country_id and warehouse.company_id.partner_id.country_id.id or False)
            company_id = warehouse.company_id.id
            if not company_id:
                company_id = self._get_default_company()
            fiscal_position_id = self.env['account.fiscal.position'].with_context({'origin_country_ept':origin_country_id}).get_fiscal_position(self.partner_id.id,self.partner_shipping_id.id)
            self.fiscal_position_id=fiscal_position_id

    @api.multi
    def action_draft(self):
        for amazon_order in self:
            amazon_order.sale_order_id.action_draft()
        return True
    @api.multi
    def action_done(self):
        for amazon_order in self:
            amazon_order.sale_order_id.write({'state': 'done'})
        return True

    @api.multi
    def action_confirm(self):
        for amazon_order in self:
            order=amazon_order.sale_order_id
            order.action_confirm()
        return True
    @api.multi
    def get_header(self,instnace):
        return """<?xml version="1.0"?>
            <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
            <Header>
                <DocumentVersion>1.01</DocumentVersion>
                <MerchantIdentifier>%s</MerchantIdentifier>
            </Header>
            <MessageType>OrderAcknowledgement</MessageType>
         """%(instnace.merchant_id)
    @api.multi
    def get_message(self,lines,instance,order):
        message_id=1
        message_str=''
        message_order_line=''
        message=""" 
            <Message>
            <MessageID>%s</MessageID>
            <OrderAcknowledgement>
                 <AmazonOrderID>%s</AmazonOrderID>
                 <StatusCode>Failure</StatusCode>  
        """%(message_id,order.amazon_reference)
        for line in lines:
            message_order_line=""" 
                <Item> 
                <AmazonOrderItemCode>%s</AmazonOrderItemCode>
                <CancelReason>%s</CancelReason>         
                </Item> 
            """%(line.sale_line_id.amazon_order_item_id,line.message)
            message="%s %s"%(message,message_order_line)
            line.sale_line_id.write({'return_reason':line.message})
        message="%s </OrderAcknowledgement></Message>"%(message)
            
        message_str="%s %s"%(message,message_str)
        header=self.get_header(instance)
        message_str="%s %s </AmazonEnvelope>"%(header,message_str)
        return message_str
    @api.multi    
    def send_cancel_request_to_amazon(self,lines,instance,order):
        data=self.get_message(lines,instance,order)
        proxy_data=instance.seller_id.get_proxy_server()
        mws_obj=Feeds(access_key=str(instance.access_key),secret_key=str(instance.secret_key),account_id=str(instance.merchant_id),region=instance.country_id.amazon_marketplace_code or instance.country_id.code,proxies=proxy_data)
        try:
            results=mws_obj.submit_feed(data,'_POST_ORDER_ACKNOWLEDGEMENT_DATA_',marketplaceids=[instance.market_place_id],instance_id=instance.id)
        except Exception,e: 
            raise Warning(str(e))
        results=results.parsed
        if results.get('FeedSubmissionInfo',{}).get('FeedSubmissionId',{}).get('value',False):
            last_feed_submission_id=results.get('FeedSubmissionInfo',{}).get('FeedSubmissionId',{}).get('value',False)
            vals = {'message':data,'feed_result_id':last_feed_submission_id,
                'feed_submit_date':time.strftime("%Y-%m-%d %H:%M:%S"),
                'instance_id':instance.id,'user_id':self._uid}
            self.env['feed.submission.history'].create(vals)

        return True
         
    @api.multi
    def cancel_in_amazon(self):
        view=self.env.ref('amazon_ept_v10.view_amazon_cancel_order_wizard')
        context=dict(self._context)
        return {
            'name': _('Cancel Order In Amazon'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'amazon.cancel.order.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context
        }        
    @api.one
    def _get_amazon_staus(self):
        for order in self:
            if order.picking_ids:
                order.updated_in_amazon=True
            else:
                order.updated_in_amazon=False
            for picking in order.picking_ids:
                if picking.state =='cancel':
                    continue
                if picking.picking_type_id.code!='outgoing':
                    continue
                if not picking.updated_in_amazon:
                    order.updated_in_amazon=False
                    break
    def _search_order_ids(self,operator,value):
        query="""
                select amazon_sale_order_ept.id from stock_picking
                inner join sale_order on sale_order.procurement_group_id=stock_picking.group_id
                inner join amazon_sale_order_ept on sale_order_id=sale_order.id
                inner join stock_location on stock_location.id=stock_picking.location_dest_id and stock_location.usage='customer'
                where stock_picking.updated_in_amazon=False and stock_picking.state='done'    
              """
        self._cr.execute(query)
        results = self._cr.fetchall()
        order_ids=[]
        for result_tuple in results:
            order_ids.append(result_tuple[0])
        return [('id','in',order_ids)]


    amazon_reference = fields.Char(size=350, string='Amazon Order Ref', required=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order Ref',required=True,ondelete="cascade")
    ept_order_line = fields.One2many('amazon.sale.order.line.ept', 'amazon_order_id', string='Ecommerce Order',readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},)    
    send_order_acknowledgment=fields.Boolean("Acknowledgment required ?")
    allow_adjustment=fields.Boolean("Allow Adjustment ?")
    instance_id = fields.Many2one("amazon.instance.ept","Instance")
    updated_in_amazon = fields.Boolean("Updated In Amazon",compute=_get_amazon_staus,search='_search_order_ids')

    shipment_service_level_category=fields.Selection([('Expedited','Expedited'),('NextDay','NextDay'),('SecondDay','SecondDay'),('Standard','Standard'),('FreeEconomy','FreeEconomy')],"Shipment Service Level Category",default='Standard')
    fulfillment_by = fields.Selection([('MFN','Manufacturer Fulfillment Network')],string="Fulfillment By",default='MFN')
    is_amazon_canceled=fields.Boolean("Canceled In amazon ?",default=False)
    fulfillment_instance_id=fields.Many2one('amazon.instance.ept' ,string="fulfillment instance")
    sale_order_report_id=fields.Many2one("sale.order.report.ept",string="Sale Order Report")  

    """Import Sales Order From Amazon"""
    
    @api.multi
    def unlink(self):
        unlink_ids = None
        unlink_sale_order_ids = None
        for order in self:
            # Check if order still exists, in case it has been unlinked by unlinking its Odoo Order
            if not order.exists():
                continue
            odoo_order = order.sale_order_id
            # Check if the Amazon order is last order  of this sale order
            other_order_ids = self.search([('sale_order_id', '=', odoo_order.id), ('id', '!=', order.id)])
            if not other_order_ids:
                if not unlink_sale_order_ids:
                    unlink_sale_order_ids= odoo_order
                else:
                    unlink_sale_order_ids = unlink_sale_order_ids + odoo_order
            if not unlink_ids:
                unlink_ids = order
            else:
                unlink_ids = unlink_ids + order
        res = super(amazon_sale_order_ept, unlink_ids).unlink()        
        # delete sale order after calling super, as deleting sale order could lead to deleting
        # amazon sale order due to ondelete='cascade'
        unlink_sale_order_ids.unlink()
        return res
            
    @api.multi
    def action_button_confirm(self):
        for order in self:
            order.sale_order_id.action_button_confirm()
        return True

    @api.multi    
    def action_cancel(self):
        for order in self:
            order.sale_order_id.action_cancel()            
        return True    
    @api.multi
    def copy_quotation(self):
        sequence=self.env.ref('sale.seq_sale_order')
        name=sequence and sequence.next_by_id() or '/'
        new_order = self.copy(default={'name':name,'state':'draft'})
        view_ref=self.env.ref('amazon_ept_v10.amazon_sales_order_form_view_ept')
        view_id = view_ref and view_ref.id or False,
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order'),
            'res_model': 'amazon.sale.order.ept',
            'res_id': new_order.ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'nodestroy': True,
        }
    
    @api.multi
    def action_view_delivery(self):
        return self.sale_order_id.action_view_delivery()
    @api.multi
    def action_view_invoice(self):
        return self.sale_order_id.action_view_invoice()            

    @api.multi
    def action_quotation_send(self):
        return self.sale_order_id.action_quotation_send()

    @api.multi
    def print_quotation(self):
        return self.sale_order_id.print_quotation()
        
    """Import Sales Order From Amazon"""
    @api.multi
    def import_sales_order(self,seller,marketplaceids=[],created_before='',created_after=''):
        """Create Object for the integrate with amazon"""
        proxy_data=seller.get_proxy_server()
        orderstatus=('Unshipped','PartiallyShipped')
        mws_obj=Orders(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)        
        """If Last Sync Time is definds then system will take those orders which are created after last import time 
          Otherwise System will take last 30 days orders
        """              
        if not created_after:
            if seller.order_last_sync_on:
                earlier_str=datetime.strptime(seller.order_last_sync_on,'%Y-%m-%d %H:%M:%S')-timedelta(days=3)
                earlier_str = earlier_str.strftime("%Y-%m-%dT%H:%M:%S")
                created_after = earlier_str+'Z'
            else:
                today = datetime.now()
                earlier = today - timedelta(days=30)
                earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
                created_after = earlier_str+'Z'            
        if not marketplaceids:
            instances = self.env['amazon.instance.ept'].search([('seller_id','=',seller.id)])
            marketplaceids = map(lambda x:x.market_place_id,instances)
        if not marketplaceids:
            raise Warning("There is no any instance is configured of seller %s"%(seller.name))
        
        """Call List Order Method Of Amazon Api for the Read Orders and API give response in DictWrapper"""
        try:            
            if seller.import_shipped_fbm_orders:
                orderstatus=orderstatus+('Shipped',)
            result=mws_obj.list_orders(marketplaceids=marketplaceids,created_after=created_after,created_before=created_before,orderstatus=orderstatus,fulfillment_channels=('MFN',))
        except Exception,e:
            raise Warning(str(e))
        self.create_sales_order(seller,[result],mws_obj)
        self._cr.commit()
        next_token=result.parsed.get('NextToken',{}).get('value')
        time.sleep(10)
        while next_token:
            try:
                result=mws_obj.list_orders_by_next_token(next_token)
            except Exception,e:
                raise Warning(str(e))
            next_token=result.parsed.get('NextToken',{}).get('value')
            self.create_sales_order(seller,[result],mws_obj)
            self._cr.commit()
            time.sleep(10)
        """We have create list of Dictwrapper now we create orders into system"""                     
        return True
    """This Function Create Orders into ERP System"""
    @api.multi
    def create_sales_order(self,seller,list_of_wrapper,mws_obj):
        amazon_sale_line_obj=self.env['amazon.sale.order.line.ept']
        instance_obj = self.env['amazon.instance.ept']
        auto_work_flow_obj=self.env['sale.workflow.process.ept']       
        amazon_product_obj=self.env['amazon.product.ept']
        stock_immediate_transfer_obj=self.env['stock.immediate.transfer']
        odoo_order_ids,shipped_orders,shipped_orders_ids=[],[],[]
        for wrapper_obj in list_of_wrapper:
            orders=[]
            if not isinstance(wrapper_obj.parsed.get('Orders',{}).get('Order',[]),list):
                orders.append(wrapper_obj.parsed.get('Orders',{}).get('Order',{})) 
            else:
                orders=wrapper_obj.parsed.get('Orders',{}).get('Order',[])               
            for order in orders:
                amazon_order_ref=order.get('AmazonOrderId',{}).get('value',False)
                        
                if not amazon_order_ref:
                    continue
                
                existing_order=self.search([('amazon_reference','=',amazon_order_ref)])
                if existing_order:
                    continue
                marketplace_id = order.get('MarketplaceId',{}).get('value',False)
                instance = instance_obj.search([('marketplace_id.market_place_id','=',marketplace_id),('seller_id','=',seller.id)])
                if not instance:
                    continue
                instance = instance[0]
                
                fulfillment_channel = order.get('FulfillmentChannel',{}).get('value',False)
                if fulfillment_channel and fulfillment_channel=='AFN' and not hasattr(instance, 'fba_warehouse_id'):
                    continue
                order_status=order.get('OrderStatus',{}).get('value','')        
                if order_status=='Shipped':
                    shipped_orders.append(amazon_order_ref)                
                partner_dict=self.create_or_update_partner(order,instance)

                try:
                    result=mws_obj.list_order_items(amazon_order_ref)
                except Exception,e:
                    raise Warning(str(e))
                list_of_orderlines_wrapper=[]
                list_of_orderlines_wrapper.append(result)
                next_token=result.parsed.get('NextToken',{}).get('value')
                while next_token:
                    try:
                        result=mws_obj.list_order_items_by_next_token(next_token)
                    except Exception,e:
                        raise Warning(str(e))
                    next_token=result.parsed.get('NextToken',{}).get('value')
                    list_of_orderlines_wrapper.append(result)         
                
                amazon_order = False
                skip_order = False 
                message = ''
                log_message = ''
                log_action_type = 'skip_line'
                for order_line_wrapper_obj in list_of_orderlines_wrapper:
                    order_lines=[]
                    skip_order = False
                    if not isinstance(order_line_wrapper_obj.parsed.get('OrderItems',{}).get('OrderItem',[]),list):
                        order_lines.append(order_line_wrapper_obj.parsed.get('OrderItems',{}).get('OrderItem',{}))
                    else:
                        order_lines=order_line_wrapper_obj.parsed.get('OrderItems',{}).get('OrderItem',[])
                    
                    message = ''
                    log_message = ''
                    res_id = False
                    model_name = 'amazon.product.ept'
                    transaction_log_lines = []
                    for order_line in order_lines:
                        seller_sku=order_line.get('SellerSKU',{}).get('value',False)
                        domain = [('instance_id','=',instance.id)]
                        seller_sku and domain.append(('seller_sku','=',seller_sku))
                        amazon_product = amazon_product_obj.search_amazon_product(instance.id,seller_sku,'MFN')

                        if not amazon_product:
                            erp_product=amazon_product_obj.search_product(seller_sku)
                            """
                                If odoo product founds and amazon product not found then no need to check anything 
                                and create new amazon product and create log for that, if odoo product not found then 
                                go to check configuration which action has to be taken for that.
                                
                                There are following situations managed by code. 
                                In any situation log that event and action.
                                
                                1). Amazon product and odoo product not found
                                    => Check seller configuration if allow to create new product then create product.
                                    => Enter log details with action.
                                2). Amazon product not found but odoo product is there.
                                    => Created amazon product with log and action.
                            """
                            product_id = False            
                            if erp_product:
                                product_id = erp_product.id
                                log_action_type = 'create'
                                message = 'Order is imported with creating new amazon product.'
                                log_message = 'Product %s created in amazon->Products->Products for %s instance. Product already exist in Odoo and Amazon.'%(seller_sku, instance.name )
                            elif not seller.create_new_product:
                                skip_order = True
                                message = 'Order is not imported due to product not found issue.'
                                log_action_type = 'skip_line'
                                log_message = 'Product %s not found for %s instance'%(seller_sku, instance.name )
                            else:
                                log_action_type = 'create'
                                message = 'Order is imported with creating new odoo product.'
                                log_message = 'Product %s created in odoo for %s instance'%(seller_sku, instance.name )
                            
                            if not skip_order:
                                sku = seller_sku or ( erp_product and erp_product[0].default_code) or False
                                prod_vals={
                                      'instance_id': instance.id,
                                      'product_asin': order_line.get('ASIN',{}).get('value',False),
                                      'seller_sku': sku,
                                      'type': erp_product and erp_product[0].type or 'product', 
                                      'product_id': product_id,             
                                      'purchase_ok' : True,
                                      'sale_ok' : True,    
                                      'exported_to_amazon': True,
                                      'fulfillment_by' : fulfillment_channel,          
                                      }
                                if not erp_product:
                                    prod_vals.update({'name':order_line.get('Title',{}).get('value'),'default_code':sku})
                            
                                amazon_product = amazon_product_obj.create(prod_vals)
                                if not erp_product:
                                    res_id = amazon_product and amazon_product.product_id.id or False
                                    model_name = 'product.product'
                                else:
                                    res_id = amazon_product and amazon_product.id or False
                                
                            log_line_vals = {
                                             'model_id' : self.env['amazon.transaction.log'].get_model_id(model_name),
                                             'res_id' : res_id or 0,
                                             'log_type' : 'not_found',
                                             'action_type' : log_action_type,
                                             'not_found_value' : seller_sku,
                                             'user_id' : self.env.uid,
                                             'skip_record' : skip_order,
                                             'message' : log_message,
                                             'amazon_order_reference':amazon_order_ref,
                                             }
                            transaction_log_lines.append((0,0,log_line_vals))  

                    if not skip_order:
                        if not amazon_order:
                            order_vals=self.create_sales_order_vals(partner_dict,order,instance)
                            amazon_order = self.create(order_vals)
                            if amazon_order and amazon_order.sale_order_id:
                                odoo_order_ids.append(amazon_order.sale_order_id.id)
                                if amazon_order.amazon_reference in shipped_orders:
                                    shipped_orders_ids.append(amazon_order.sale_order_id.id)
                        for order_line in order_lines:                        
                            amazon_sale_line_obj.create_sale_order_line(order_line,instance, amazon_order)
                            
                    if skip_order or log_action_type == 'create':   
                        job_log_vals = {
                                        'transaction_log_ids' : transaction_log_lines,
                                        'skip_process' : skip_order,
                                        'application' : 'sales',
                                        'operation_type' : 'import',
                                        'message' : message,
                                        'instance_id':instance.id
                                        }
                        self.env['amazon.process.log.book'].create(job_log_vals) 
        if odoo_order_ids:
            auto_work_flow_obj.auto_workflow_process(instance.auto_workflow_id.id,odoo_order_ids) 
            odoo_orders=self.env['sale.order'].browse(odoo_order_ids)
            shipped_orders_record=self.env['sale.order'].browse(shipped_orders_ids)
            for order in odoo_orders:
                order.invoice_shipping_on_delivery=False
            for shipped_order in shipped_orders_record:
                for picking in shipped_order.picking_ids:
                    if picking.state in ['waiting','confirmed']:
                        picking.action_assign()
                    if picking.state in ['confirmed','partially_available']:
                        picking.force_assign()
                    if picking.state=='assigned':      
                        stock_immediate_transfer_obj.create({'pick_id':picking.id}).process()
        return True
    
    @api.multi
    def create_sales_order_vals(self,partner_dict,order,instance):
        delivery_carrier_obj=self.env['delivery.carrier']
        sale_order_obj=self.env['sale.order']
        fpos = instance.fiscal_position_id and instance.fiscal_position_id.id or False
        shipping_category=order.get('ShipmentServiceLevelCategory',{}).get('value',False)             
        date_order=False
        if order.get('PurchaseDate',{}).get('value',False):
            date_order=parser.parse(order.get('PurchaseDate',False).get('value',False)).astimezone(utc).strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_order=time.strftime('%Y-%m-%d %H:%M:%S')
        ordervals={
                   'company_id':instance.company_id.id,                   
                   'partner_id' :partner_dict.get('invoice_address'),
                   'partner_invoice_id' : partner_dict.get('invoice_address'),
                   'partner_shipping_id' : partner_dict.get('delivery_address'),
                   }
        new_record = sale_order_obj.new(ordervals)
        new_record.onchange_partner_id()
        ordervals = sale_order_obj._convert_to_write({name: new_record[name] for name in new_record._cache})
        new_record = sale_order_obj.new(ordervals)
        new_record.onchange_partner_shipping_id()
        ordervals = sale_order_obj._convert_to_write({name: new_record[name] for name in new_record._cache})
        ordervals.update(
            {
            'company_id':instance.company_id.id,
            'picking_policy' : instance.picking_policy,
            'partner_invoice_id' : partner_dict.get('invoice_address'),
            'date_order' : str(date_order),
            'warehouse_id' : instance.warehouse_id.id,
            'partner_id' :partner_dict.get('invoice_address'),
            'partner_shipping_id' : partner_dict.get('delivery_address'),
            'state' : 'draft',            
            'team_id':instance.team_id and instance.team_id.id or False,
            'pricelist_id' :instance.pricelist_id.id,
            'fiscal_position_id': fpos,
            'payment_term_id':instance.payment_term_id.id or False,    
            'auto_workflow_process_id':instance.auto_workflow_id.id,
            'client_order_ref':order.get('AmazonOrderId',{}).get('value',False),
            'invoice_policy':instance.invoice_policy or False,
            'instance_id':instance and instance.id or False,
            'amazon_reference': order.get('AmazonOrderId',{}).get('value',False),
            'shipment_service_level_category':shipping_category            
        })
        if not instance.is_default_odoo_sequence_in_sales_order:
            ordervals.update({'name':"%s%s" %(instance.order_prefix and instance.order_prefix+'_' or '', order.get('AmazonOrderId',{}).get('value'))})
        carrier=delivery_carrier_obj.search(['|',('amazon_code','=',shipping_category),('name','=',shipping_category)],limit=1)
        ordervals.update({'carrier_id':carrier.id})
        return ordervals
        

    @api.multi
    def create_or_update_partner(self,order,instance):
        address_info=order.get('ShippingAddress')
        partner_obj = self.env['res.partner']
        country_obj = self.env['res.country']
        state_obj = self.env['res.country.state']
        return_partner={}
        state_id,name,result_state,partner= False, False,False,False
        
        if instance.partner_id and instance.partner_id.property_product_pricelist.id!=instance.pricelist_id.id:
            instance.partner_id.write({'property_product_pricelist':instance.pricelist_id.id})
        
        partner_id = instance.partner_id and instance.partner_id.id or False
        country_code=address_info.get('CountryCode',{}).get('value',instance.country_id.code)
        country = country_obj.search([('amazon_marketplace_code','=',country_code)],limit=1)               
        if not country:               
            country = country_obj.search([('code','=',country_code)],limit=1)        
        state=address_info.get('StateOrRegion',{}).get('value',False) 
        if state:
            if country:
                result_state = state_obj.search(['|',('name','=',state),('code','=',state),('country_id','=',country.id)],limit=1)    
                if not result_state:
                    result_state = state_obj.search([('code','=',state[:3]),('country_id','=',country.id)],limit=1)    
            else:
                result_state = state_obj.search(['|',('name','=',state),('code','=',state)],limit=1)                    
            if not result_state:
                state = country and state_obj.create({'country_id':country.id, 'name':state,'code':state[:3]})
                state_id=state and state.id or False
            else:
                state_id=result_state.id
        street=address_info.get('AddressLine1',{}).get('value',False)
        street2=address_info.get('AddressLine2',{}).get('value',False)
        email_id=order.get('BuyerEmail',{}).get('value',False)
        postalcode=address_info.get('PostalCode',{}).get('value',False)
        inv_cust_name=order.get('BuyerName',{}).get('value',False)
        deliv_cust_name=address_info.get('Name',{}).get('value',False)
        
        phone=address_info.get('Phone',{}).get('value',False)
        city=address_info.get('City',{}).get('value',False)
        if street and street == order.get('BuyerName',{}).get('value') or street == address_info.get('Name',{}).get('value'):
            street = False
        domain=[]
        street and domain.append(('street','=',street))
        street2 and domain.append(('street2','=',street2))
        email_id and domain.append(('email','=',email_id))
        phone and domain.append(('phone','=',phone))
        city and domain.append(('city','=',city))
        postalcode and domain.append(('zip','=',postalcode))
        state_id and domain.append(('state_id','=',state_id))
        country and domain.append(('country_id','=',country.id))
        deliv_cust_name and domain.append(('name','=',deliv_cust_name))
        
        partnervals = {
                'opt_out':True,'is_company':False,'customer' : not bool(partner_id),'street' : street,'street2' : street2,'city' : city,
                'country_id' : country.id,'phone' :phone,'zip' : postalcode,'state_id' : state_id,'email':email_id,'parent_id':partner_id,
                'lang':instance.lang_id.code,'company_id':instance.company_id.id
            }
        if instance.customer_is_company and not partner_id:
            partnervals.update({'is_company':True})
        
        if instance.pricelist_id:
            partnervals.update({'property_product_pricelist':instance.pricelist_id.id})
        
        add_name_same = False
        if deliv_cust_name == inv_cust_name:
            add_name_same = True
                    
        exist_partner = partner_obj.search(domain)                
        if exist_partner:
            exist_partner = exist_partner[0]
            return_partner.update({'invoice_address':exist_partner.id,'property_product_pricelist':exist_partner.property_product_pricelist.id,
                                   'delivery_address':exist_partner.id,'type':'delivery'})
        else:
            partnervals.update({'type':'delivery','name':deliv_cust_name})                
            if partnervals.has_key('message_follower_ids'):
                del partnervals['message_follower_ids']
            exist_partner = partner_obj.create(partnervals)
            exist_partner and return_partner.update({'invoice_address':exist_partner.id,'property_product_pricelist':exist_partner.property_product_pricelist.id,'delivery_address':exist_partner.id})

        if not add_name_same:
            domain.remove(('name','=',deliv_cust_name))
            domain.append(('name','=',inv_cust_name))
            exist_invoice_partner = partner_obj.search(domain)
            if exist_invoice_partner:
                exist_invoice_partner = exist_invoice_partner[0]
                exist_invoice_partner.write({'type':'invoice'})
                return_partner.update({'invoice_address':exist_invoice_partner.id})
            else:
                partnervals.update({'type':'invoice','name':inv_cust_name})                
                if partnervals.has_key('message_follower_ids'):
                    del partnervals['message_follower_ids']
                exist_invoice_partner = partner_obj.create(partnervals)
                exist_invoice_partner and return_partner.update({'invoice_address':exist_invoice_partner.id})
            if not instance.customer_is_company and not partner_id:
                exist_invoice_partner.write({'is_company':True})            
            exist_partner.write({'is_company':False,'parent_id':exist_invoice_partner.id})                    
        
        return return_partner

    
    @api.multi
    def get_amazon_sale_line(self,move):
        if move.procurement_id and move.procurement_id.sale_line_id:
            amazon_order_line=self.env['amazon.sale.order.line.ept'].search([('sale_order_line_id','=',move.procurement_id.sale_line_id.id)])
        else:
            amazon_order_line=False
        amazon_order_item_id=amazon_order_line and amazon_order_line.amazon_order_item_id or False

        return amazon_order_line,amazon_order_item_id

    @api.multi
    def get_qty_for_phantom_type_products(self,order,picking,order_ref,carrier_name,shipping_level_category,message_id,fulfillment_date_concat):
        message_information=''
        move_obj=self.env['stock.move']
        update_move_ids=[]
        picking_ids=order.picking_ids.ids
        moves=move_obj.search([('picking_id','in',picking_ids),('picking_type_id.code','!=','incoming'),('state','not in',['draft','cancel']),('updated_in_amazon','=',False)])
        phantom_product_dict={}
        for move in moves:
            if move.procurement_id.product_id.id!=move.product_id.id:
                if phantom_product_dict.has_key(move.procurement_id) and move.product_id.id not in phantom_product_dict.get(move.procurement_id):
                    phantom_product_dict.get(move.procurement_id).append(move.product_id.id)
                else:
                    phantom_product_dict.update({move.procurement_id:[move.product_id.id]})
        for procurement,product_ids in phantom_product_dict.iteritems():
            parcel={}
            moves=move_obj.search([('picking_id','in',picking_ids),('state','in',['draft','cancel']),('product_id','in',product_ids)])
            if not moves:
                moves=move_obj.search([('picking_id','in',picking_ids),('state','=','done'),('product_id','in',product_ids),('updated_in_amazon','=',False)])
                tracking_no=picking.carrier_tracking_ref
                for move in moves:
                    if not tracking_no:
                        for quant in move.quant_ids:
                            tracking_no=quant.package_id and quant.package_id.tracking_no or False
                update_move_ids+=moves.ids
                amazon_order_line,amazon_order_item_id=self.get_amazon_sale_line(moves[0])
                product_qty=procurement.product_qty
                if amazon_order_line and amazon_order_line.amazon_product_id and amazon_order_line.amazon_product_id.allow_package_qty:
                    asin_qty=amazon_order_line.amazon_product_id.asin_qty 
                    if asin_qty !=0:
                        product_qty=product_qty/asin_qty                                
                product_qty=int(product_qty)
                parcel.update({
                                    'tracking_no':tracking_no or '',
                                    'qty':product_qty,
                                    'amazon_order_item_id':amazon_order_item_id,
                                    'order_ref':order_ref,
                                    'carrier_name':carrier_name,    
                                    'shipping_level_category':shipping_level_category                                            
                                    })
                message_information+=self.create_parcel_for_multi_tracking_number(parcel,message_id,fulfillment_date_concat)
                message_id=message_id+1
        return message_information,message_id,update_move_ids
    """Update Order Status into Amazon
            Consider Cases....!!!!
            1.Partial shipment
            2.Same Carrier With More then one tracking no
            3.Same Carrier and Same Product with more then one tracking no    
    """
    @api.multi
    def update_order_status(self,seller,marketplaceids=[]):
        proxy_data=seller.get_proxy_server()
        mws_obj=Feeds(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)        
        carrier_name,order_ref=False,False
        picking_obj=self.env['stock.picking']
        move_obj=self.env['stock.move']
        if not marketplaceids:
            instances = self.env['amazon.instance.ept'].search([('seller_id','=',seller.id)])
            marketplaceids = map(lambda x:x.market_place_id,instances)
        if not marketplaceids:
            raise Warning("There is no any instance is configured of seller %s"%(seller.name))
        
        """Check If Order already shipped in the amazon then we will skip that all orders and set update_into_amazon=True 
        """
        amazon_orders=self.check_already_status_updated_in_amazon(seller,marketplaceids)
        if not amazon_orders:
            return []
        parcel={}
        shipment_pickings=[]
        message_information=""
        message_id=1
        updated_picking_wize_move_lines={}
        for amazon_order in amazon_orders:
            for picking in amazon_order.picking_ids:
                """Here We Take only done picking and  updated in amazon false"""
                if picking.updated_in_amazon or picking.state!='done' or picking.location_dest_id.usage!='customer':
                    continue                    
                if picking.date_done:
                    fulfillment_date = time.strptime(picking.date_done, "%Y-%m-%d %H:%M:%S")
                    fulfillment_date = time.strftime("%Y-%m-%dT%H:%M:%S",fulfillment_date)
                else:
                    fulfillment_date = time.strftime('%Y-%m-%dT%H:%M:%S')
                fulfillment_date_concat = str(fulfillment_date) + '-00:00'
                shipment_pickings.append(picking.id)
                order_ref=amazon_order.amazon_reference
                carrier_name=picking.carrier_id and picking.carrier_id.name or False   
                
                shipping_level_category=amazon_order.shipment_service_level_category                    

                if not shipping_level_category:
                    continue
                if not amazon_order.instance_id.manage_multi_tracking_number_in_delivery_order:
                    tracking_no=picking.carrier_tracking_ref
                    parcel.update({
                                    'tracking_no':tracking_no or '',
                                    'order_ref':order_ref,
                                    'carrier_name':carrier_name or '',    
                                    'shipping_level_category':shipping_level_category                                            
                                })
                    message_information+=self.create_parcel_for_single_tracking_number(parcel,message_id,fulfillment_date_concat)
                    message_id=message_id+1
                    updated_picking_wize_move_lines.update({picking.id:picking.move_lines.ids})
                else:
                    """Crate message for bom type products"""
                    phantom_msg_info,message_id,update_move_ids=self.get_qty_for_phantom_type_products(amazon_order, picking, order_ref, carrier_name, shipping_level_category, message_id, fulfillment_date_concat)
                    if phantom_msg_info:
                        message_information+=phantom_msg_info
                    update_move_ids and updated_picking_wize_move_lines.update({picking.id:update_move_ids})
                    """Create Message for each move"""
                    for move in picking.move_lines:
                        if move in update_move_ids or  move.procurement_id.product_id.id!=move.product_id.id:
                            continue
                        if updated_picking_wize_move_lines.has_key(picking.id):
                            updated_picking_wize_move_lines.get(picking.id).append(move.id)
                        else:
                            updated_picking_wize_move_lines.update({picking.id:move.ids})
                        amazon_order_line,amazon_order_item_id=self.get_amazon_sale_line(move)
                        """Create Package for the each parcel"""
                        tracking_no_with_qty={}
                        product_qty=0.0
                        for quant in move.quant_ids:
                            if quant.qty<0.0:
                                continue
                            tracking_no=quant.package_id and quant.package_id.tracking_no or 'UNKNOWN'
                            quantity=tracking_no_with_qty.get(tracking_no,0.0)
                            quantity=quantity+quant.qty
                            tracking_no_with_qty.update({tracking_no:quantity})
                        for tracking_no,product_qty in tracking_no_with_qty.items():
                            if tracking_no=='UNKNOWN':
                                tracking_no=''                              
                            if amazon_order_line and amazon_order_line.amazon_product_id and amazon_order_line.amazon_product_id.allow_package_qty:
                                asin_qty=amazon_order_line.amazon_product_id.asin_qty 
                                if asin_qty !=0:
                                    product_qty=product_qty/asin_qty                                
                            product_qty=int(product_qty)
                            parcel.update({
                                                'tracking_no':tracking_no or '',
                                                'qty':product_qty,
                                                'amazon_order_item_id':amazon_order_item_id,
                                                'order_ref':order_ref,
                                                'carrier_name':carrier_name,    
                                                'shipping_level_category':shipping_level_category                                            
                                                })
                            message_information+=self.create_parcel_for_multi_tracking_number(parcel,message_id,fulfillment_date_concat)
                            message_id=message_id+1
        if not message_information:
            return True
        data=self.create_data(message_information,str(seller.merchant_id))
        results = mws_obj.submit_feed(data,'_POST_ORDER_FULFILLMENT_DATA_',marketplaceids=marketplaceids)
        time.sleep(120)
        results=results.parsed
        if results.get('FeedSubmissionInfo',{}).get('FeedSubmissionId',{}).get('value',False):
            last_feed_submission_id=results.get('FeedSubmissionInfo',{}).get('FeedSubmissionId',{}).get('value',False)
            submission_results=mws_obj.get_feed_submission_result(last_feed_submission_id)
            error=submission_results._response_dict.get('Message',{}).get('ProcessingReport',{}).get('ProcessingSummary',{}).get('MessagesWithError',{}).get('value','1')
            if error == '0':
                pickings = picking_obj.search([('id','in',shipment_pickings)])
                for picking in pickings:
                    move_ids=updated_picking_wize_move_lines.get(picking.id)
                    move_obj.browse(move_ids).write({'updated_in_amazon':True})
                    moves=move_obj.search([('picking_id','=',picking.id),('updated_in_amazon','=',False)])
                    if not moves:
                        picking.write({'updated_in_amazon':True})
            else:
                self.check_already_status_updated_in_amazon(seller,marketplaceids)
        return True 

    @api.multi                    
    def create_parcel_for_multi_tracking_number(self,parcel,message_id,fulfillment_date_concat):
        message_information=''
        item_string='''<Item>
                            <AmazonOrderItemCode>%s</AmazonOrderItemCode>
                            <Quantity>%s</Quantity>
                      </Item>'''%(parcel.get('amazon_order_item_id'),parcel.get('qty',0))
        message_information += """<Message>
                                    <MessageID>%s</MessageID>
                                    <OperationType>Update</OperationType>
                                    <OrderFulfillment>
                                        <AmazonOrderID>%s</AmazonOrderID>
                                        <FulfillmentDate>%s</FulfillmentDate>
                                        <FulfillmentData>
                                            <CarrierName>%s</CarrierName>
                                            <ShippingMethod>%s</ShippingMethod>
                                            <ShipperTrackingNumber>%s</ShipperTrackingNumber>
                                        </FulfillmentData>
                                        %s
                                    </OrderFulfillment>
                                </Message>""" %(str(message_id),parcel.get('order_ref'),fulfillment_date_concat,parcel.get('carrier_name'),parcel.get('shipping_level_category'),parcel.get('tracking_no'),item_string.encode("utf-8"))
        return message_information
    @api.multi
    def create_parcel_for_single_tracking_number(self,parcel,message_id,fulfillment_date_concat):
        message_information=''
        message_information += """<Message>
                                    <MessageID>%s</MessageID>
                                    <OperationType>Update</OperationType>
                                    <OrderFulfillment>
                                        <AmazonOrderID>%s</AmazonOrderID>
                                        <FulfillmentDate>%s</FulfillmentDate>
                                        <FulfillmentData>
                                            <CarrierName>%s</CarrierName>
                                            <ShippingMethod>%s</ShippingMethod>
                                            <ShipperTrackingNumber>%s</ShipperTrackingNumber>
                                        </FulfillmentData>
                                    </OrderFulfillment>
                                </Message>""" %(str(message_id),parcel.get('order_ref'),fulfillment_date_concat,parcel.get('carrier_name'),parcel.get('shipping_level_category'),parcel.get('tracking_no'))
        return message_information
    @api.multi
    def create_data(self,message_information,merchant_id):
        data = """<?xml version="1.0" encoding="utf-8"?>
                    <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
                        <Header>
                            <DocumentVersion>1.01</DocumentVersion>
                                <MerchantIdentifier>%s</MerchantIdentifier>
                        </Header>
                    <MessageType>OrderFulfillment</MessageType>"""%(merchant_id) + message_information.encode("utf-8") + """
                    </AmazonEnvelope>"""

        return data
    @api.model
    def check_already_status_updated_in_amazon(self,seller,marketplaceids):
        """Create Object for the integrate with amazon"""
        proxy_data=seller.get_proxy_server()
        mws_obj = Orders(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)        
        instances = self.env['amazon.instance.ept'].search([('seller_id','=',seller.id)])
        warehouse_ids = list(set(map(lambda x:x.warehouse_id.id,instances)))
        
        sales_orders = self.search([('warehouse_id','in',warehouse_ids),
                                                     ('amazon_reference','!=',False),
                                                     ('instance_id','in',instances.ids),                                                     
                                                     ('updated_in_amazon','=',False),
                                                     ('fulfillment_by','=','MFN'),
                                                     ],order='date_order')
        if not sales_orders:
            return []
        created_after = time.strptime(sales_orders[0].date_order, "%Y-%m-%d %H:%M:%S")
        created_after = time.strftime("%Y-%m-%dT%H:%M:%S",created_after)
        created_after = time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(time.mktime(time.strptime(created_after,"%Y-%m-%dT%H:%M:%S"))))
        created_after = str(created_after)+'Z'
        
        if len(sales_orders)>1:
            created_before = time.strptime(sales_orders[len(sales_orders)-1].date_order, "%Y-%m-%d %H:%M:%S")
            created_before = time.strftime("%Y-%m-%dT%H:%M:%S",created_before)
            created_before = time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(time.mktime(time.strptime(created_before,"%Y-%m-%dT%H:%M:%S"))))
            created_before = str(created_before)+'Z'
        else:
            created_before = datetime.strptime(sales_orders[0].date_order, "%Y-%m-%d %H:%M:%S")
            created_before = created_before + timedelta(seconds=500)
            #make_time = datetime.utcnow() - timedelta(seconds=240)
            make_time_str = created_before.strftime("%Y-%m-%dT%H:%M:%S")
            created_before = make_time_str+'Z'
        
        try:
            result=mws_obj.list_orders(marketplaceids=marketplaceids,created_after=created_after,created_before=created_before,orderstatus=('Shipped',),fulfillment_channels=('MFN',))
        except Exception,e:
            raise Warning(str(e))

        list_of_wrapper=[]
        list_of_wrapper.append(result)
        next_token=result.parsed.get('NextToken',{}).get('value')
        while next_token:
            try:
                result=mws_obj.list_orders_by_next_token(next_token)
            except Exception,e:
                raise Warning(str(e))
            next_token=result.parsed.get('NextToken',{}).get('value')
            list_of_wrapper.append(result)            
        
        list_of_amazon_order_ref=[]
        for wrapper_obj in list_of_wrapper:
            orders=[]
            if not isinstance(wrapper_obj.parsed.get('Orders',{}).get('Order',[]),list):
                orders.append(wrapper_obj.parsed.get('Orders',{}).get('Order',{})) 
            else:
                orders=wrapper_obj.parsed.get('Orders',{}).get('Order',[])               
            for order in orders:
                amazon_order_ref=order.get('AmazonOrderId',{}).get('value',False)
                list_of_amazon_order_ref.append(amazon_order_ref)
        unshipped_sales_orders=[]
        for order in sales_orders:
            if order.amazon_reference in list_of_amazon_order_ref:
                order.picking_ids.write({'updated_in_amazon':True})
            else:
                unshipped_sales_orders.append(order)
        return unshipped_sales_orders
    
    @api.multi
    def import_sales_order_by_flat_report(self,seller,marketplaceids=[],start_date=False,end_date=False,status=('Unshipped','PartiallyShipped')):
        """If Last Sync Time is define then system will take those orders which are created after last import time 
            Otherwise System will take last 30 days orders
        """
        orders_instance_dict={}
        saleorder_report_obj = self.env['sale.order.report.ept']  
        if not start_date and not end_date:
            if not seller.order_last_sync_on:
                today = datetime.now()
                earlier = today - timedelta(days=30)
                earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
                end_date = earlier_str+'Z'
                start_date , orders_instance_dict = self.env['sale.order.report.ept'].get_orders_by_flat_report(seller,start_date,end_date,marketplaceids,status)
                end_date=False
            else:
                earlier_str=datetime.strptime(seller.order_last_sync_on,'%Y-%m-%d %H:%M:%S')-timedelta(days=1)
                earlier_str = earlier_str.strftime("%Y-%m-%dT%H:%M:%S")
                start_date = earlier_str+'Z'
        if not start_date:
            start_date = seller.order_last_sync_on
            if start_date:
                db_import_time = time.strptime(start_date, "%Y-%m-%d %H:%M:%S")
                db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S",db_import_time)
                start_date = time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(time.mktime(time.strptime(db_import_time,"%Y-%m-%dT%H:%M:%S"))))
                start_date = str(start_date)+'Z'
            else:
                today = datetime.now()
                earlier = today - timedelta(days=30)
                earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
                start_date = earlier_str+'Z'
        
        if not end_date:
            to_date = datetime.now()
            seller.write({'order_last_sync_on':to_date})
            earlier_str = to_date.strftime("%Y-%m-%dT%H:%M:%S")
            end_date = earlier_str+'Z'
            
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code)
        if seller.is_another_soft_create_fbm_reports:
            try:
                result = mws_obj.get_report_list(types=('_GET_FLAT_FILE_ORDERS_DATA_',),fromdate=start_date,todate=end_date)
            except Exception,e:
                if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                    error = mws_obj.parsed_response_error.parsed or {}
                    error_value = error.get('Message',{}).get('value')
                    error_value = error_value if error_value else str(mws_obj.response.content)  
                else:
                    error_value = str(e)
                raise Warning(error_value)
            list_of_wrapper=[]
            list_of_wrapper.append(result)
            has_next = result.parsed.get('HasNext',{}).get('value',False)
            count=0
            while has_next =='true':
                next_token=result.parsed.get('NextToken',{}).get('value')
                try:
                    result = mws_obj.get_report_list_by_next_token(next_token)
                    if count ==3:
                        time.sleep(10)
                        count=0
                    count=count+1
                except Exception,e:
                    if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                        error = mws_obj.parsed_response_error.parsed or {}
                        error_value = error.get('Message',{}).get('value')
                        error_value = error_value if error_value else str(mws_obj.response.content)  
                    else:
                        error_value = str(e)
                    raise Warning(error_value)
                has_next = result.parsed.get('HasNext',{}).get('value','')
                list_of_wrapper.append(result)
                  
    
            for result in list_of_wrapper:
                reports=[]
                if not isinstance(result.parsed.get('ReportInfo',[]),list):
                    reports.append(result.parsed.get('ReportInfo',[])) 
                else:
                    reports=result.parsed.get('ReportInfo',[])               
                for report in reports:
                    request_id = report.get('ReportRequestId',{}).get('value','')
                    report_id = report.get('ReportId',{}).get('value','')
                    report_type = report.get('ReportType',{}).get('value','')
                    report_exist = saleorder_report_obj.search(['|',('report_request_id','=',request_id),('report_id','=',report_id),('report_type','=',report_type)])
                    if report_exist:
                        report_exist= report_exist[0]
                        vals = {}
                        if report_exist.report_id !=report_id:
                            vals.update({'report_id':report_id,'unshipped_orders':orders_instance_dict})
                        if vals:
                            report_exist.write(vals)
                        continue
                    vals = {
                            'report_type':report_type,
                            'report_request_id':request_id,
                            'report_id':report_id,
                            'start_date':start_date,                            
                            'end_date':end_date,
                            'state':'_DONE_',
                            'requested_date':datetime.now(),
                            'seller_id':seller.id,
                            'user_id':self._uid,
                            }
                    saleorder_report_obj.create(vals)        
        else:
            flat_order_report = saleorder_report_obj.create({'report_type' : '_GET_FLAT_FILE_ORDERS_DATA_',
                     'seller_id':seller.id,
                     'start_date' : start_date,
                     'end_date' : end_date,
                     'requested_date':datetime.now(),
                     'state' :'draft',
                     })
              
            try:              
                flat_order_report.request_report()    
            except:
                time.sleep(120)
                flat_order_report.request_report()
        return True
    
    @api.model
    def get_orders_instance_by_xml_report(self,seller,marketplaceids=[]):
        mws_obj=Orders(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code)
         
        today = datetime.now()
        earlier = today - timedelta(days=30)
        earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
        created_after = earlier_str+'Z'
        created_before =''
        orderstatus=('Unshipped','PartiallyShipped')
        if not marketplaceids:
            instances = self.env['amazon.instance.ept'].search([('seller_id','=',seller.id)])
            marketplaceids = map(lambda x:x.market_place_id,instances)
        if not marketplaceids:
            raise Warning("There is no any instance is configured of seller %s"%(seller.name))        
         
        """Call List Order Method Of Amazon Api for the Read Orders and API give response in DictWrapper"""
        try:
            result=mws_obj.list_orders(marketplaceids=marketplaceids,created_after=created_after,created_before=created_before,orderstatus=orderstatus,fulfillment_channels=('MFN',))
        except Exception,e:
            if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                error = mws_obj.parsed_response_error.parsed or {}
                error_value = error.get('Message',{}).get('value')
                error_value = error_value if error_value else str(mws_obj.response.content)  
            else:
                error_value = str(e)
            raise Warning(error_value)
                 
        list_of_wrapper=[]
        list_of_wrapper.append(result)
        next_token=result.parsed.get('NextToken',{}).get('value')
        while next_token:
            try:
                result=mws_obj.list_orders_by_next_token(next_token)
                time.sleep(2)
            except Exception,e:
                if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                    error = mws_obj.parsed_response_error.parsed or {}
                    error_value = error.get('Message',{}).get('value')
                    error_value = error_value if error_value else str(mws_obj.response.content)  
                else:
                    error_value = str(e)
                raise Warning(error_value)
            next_token=result.parsed.get('NextToken',{}).get('value')
            list_of_wrapper.append(result)            
         
        instance_obj = self.env['amazon.instance.ept']
        order_instance_dict = {}
        marketplace_instance_dict = {}
        smaller_date = datetime.now()
        start_date = False
        for wrapper_obj in list_of_wrapper:
            orders=[]
            if not isinstance(wrapper_obj.parsed.get('Orders',{}).get('Order',[]),list):
                orders.append(wrapper_obj.parsed.get('Orders',{}).get('Order',{})) 
            else:
                orders=wrapper_obj.parsed.get('Orders',{}).get('Order',[])               
            for order in orders:                 
                amazon_order_ref=order.get('AmazonOrderId',{}).get('value',False)
                purchase_date = order.get('PurchaseDate',{}).get('value',False)
                purchase_datetime = datetime.strptime(purchase_date,'%Y-%m-%dT%H:%M:%SZ')
                if purchase_datetime < smaller_date:
                    smaller_date = purchase_datetime
                    start_date = purchase_date
                marketplace_id = order.get('MarketplaceId',{}).get('value',False)
                if marketplace_id not in marketplace_instance_dict:
                    instance = instance_obj.search([('marketplace_id.market_place_id','=',marketplace_id),('seller_id','=',seller.id)])
                    if not instance:
                        continue
                    instance = instance[0]                    
                    marketplace_instance_dict.update({marketplace_id:instance.id})
                order_instance_dict.update({amazon_order_ref:marketplace_instance_dict.get(marketplace_id)})                                
        return start_date,order_instance_dict

    @api.multi
    def import_sales_order_by_xml_report(self,seller,marketplaceids=[],start_date=False,end_date=False):
        """If Last Sync Time is define then system will take those orders which are created after last import time 
          Otherwise System will take last 30 days orders
        """
        orders_instance_dict={}
        saleorder_report_obj = self.env['sale.order.report.ept']  
        if not start_date:
            start_date = seller.order_last_sync_on
            if start_date:
                db_import_time = time.strptime(start_date, "%Y-%m-%d %H:%M:%S")
                db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S",db_import_time)
                start_date = time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(time.mktime(time.strptime(db_import_time,"%Y-%m-%dT%H:%M:%S"))))
                start_date = str(start_date)+'Z'
            else:
                today = datetime.now()
                earlier = today - timedelta(days=30)
                earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
                start_date = earlier_str+'Z'
                
        if not end_date:
            to_date = datetime.now()
            earlier_str = to_date.strftime("%Y-%m-%dT%H:%M:%S")
            end_date = earlier_str+'Z'
                
        if not start_date and not end_date:
            start_date,orders_instance_dict = self.get_orders_instance_by_xml_report(seller,marketplaceids)      
            
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code)
        if seller.is_another_soft_create_fbm_reports:
            try:
                result = mws_obj.get_report_list(types=('_GET_ORDERS_DATA_',),fromdate=start_date,todate=end_date)
            except Exception,e:
                if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                    error = mws_obj.parsed_response_error.parsed or {}
                    error_value = error.get('Message',{}).get('value')
                    error_value = error_value if error_value else str(mws_obj.response.content)  
                else:
                    error_value = str(e)
                raise Warning(error_value)
            
            list_of_wrapper=[]
            list_of_wrapper.append(result)
            has_next = result.parsed.get('HasNext',{}).get('value',False)
            while has_next =='true':
                next_token=result.parsed.get('NextToken',{}).get('value')
                try:
                    result = mws_obj.get_report_list_by_next_token(next_token)
                except Exception,e:
                    if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                        error = mws_obj.parsed_response_error.parsed or {}
                        error_value = error.get('Message',{}).get('value')
                        error_value = error_value if error_value else str(mws_obj.response.content)  
                    else:
                        error_value = str(e)
                    raise Warning(error_value)
                has_next = result.parsed.get('HasNext',{}).get('value','')
                list_of_wrapper.append(result)
    
            for result in list_of_wrapper:
                reports=[]
                if not isinstance(result.parsed.get('ReportInfo',[]),list):
                    reports.append(result.parsed.get('ReportInfo',[])) 
                else:
                    reports=result.parsed.get('ReportInfo',[])               
                for report in reports:
                    request_id = report.get('ReportRequestId',{}).get('value','')
                    report_id = report.get('ReportId',{}).get('value','')
                    report_type = report.get('ReportType',{}).get('value','')
                    report_exist = saleorder_report_obj.search(['|',('report_request_id','=',request_id),('report_id','=',report_id),('report_type','=',report_type)])
                    if report_exist:
                        report_exist= report_exist[0]
                        vals = {}
                        if report_exist.report_id !=report_id:
                            vals.update({'report_id':report_id,'unshipped_orders':orders_instance_dict})
                        if vals:
                            report_exist.write(vals)
                        continue
                    vals = {
                            'report_type':report_type,
                            'report_request_id':request_id,
                            'report_id':report_id,
                            'start_date':start_date,
                            'end_date':end_date,
                            'state':'_DONE_',
                            'seller_id':seller.id,
                            'requested_date':datetime.now(),
                            'user_id':self._uid,                             
                            }
                    saleorder_report_obj.create(vals)
        else:
            xml_order_report = saleorder_report_obj.create({'report_type' : '_GET_ORDERS_DATA_',
                     'seller_id':seller.id,
                     'start_date' : start_date,
                     'end_date' : end_date,
                     'requested_date':datetime.now(),
                     'state' :'draft',
                     })
                            
            try:              
                xml_order_report.request_report()    
            except:
                time.sleep(120)
                xml_order_report.request_report()
        return True

