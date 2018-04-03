from openerp import models, fields, api,_
from openerp.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,DictWrapper,Orders
import base64
from StringIO import StringIO
import time
import csv
from openerp.exceptions import Warning
from datetime import datetime,timedelta
import logging
import pytz
utc = pytz.utc
from dateutil import parser
_logger = logging.getLogger(__name__)

class sale_order_report_ept(models.Model):
    _name="sale.order.report.ept"
    _inherits={"report.request.history":'report_history_id'}
    _order = 'id desc'
    _inherit = ['mail.thread']
    _description = "Sales Order Report"
    
    @api.one
    def get_log_count(self):
        amazon_transaction_log_obj=self.env['amazon.transaction.log']
        model_id=amazon_transaction_log_obj.get_model_id('amazon.sale.order.report.ept')
        records=amazon_transaction_log_obj.search([('model_id','=',model_id),('res_id','=',self.id)])
        self.log_count=len(records.ids)
    @api.one
    def count_fbm_orders(self):
        self.fbm_order_count=len(self.amazon_fbm_sale_order_ids.ids)
    name = fields.Char(size=256, string='Name')
    report_history_id = fields.Many2one('report.request.history', string='Report',required=True,ondelete="cascade",index=True, auto_join=True)
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")
    auto_generated = fields.Boolean('Auto Genrated Record ?', default=False)       
    amazon_fbm_sale_order_ids=fields.One2many('amazon.sale.order.ept','sale_order_report_id',string="Fbm orders")
    fbm_order_count=fields.Integer("Count FBM Orders",compute="count_fbm_orders")
    state = fields.Selection([('draft','Draft'),('_SUBMITTED_','SUBMITTED'),('_IN_PROGRESS_','IN_PROGRESS'),
                                     ('_CANCELLED_','CANCELLED'),('_DONE_','DONE'),
                                     ('_DONE_NO_DATA_','DONE_NO_DATA'),('processed','PROCESSED'),('partially_processed','Partially Processed')
                                     ],
                                    string='Report Status', default='draft')    
    unshipped_orders=fields.Text("Unshipped Orders")
    instance_id=fields.Many2one('amazon.instance.ept',string="Instance")
    is_shipped_orders=fields.Boolean("Is Shipped Orders?")
    log_count=fields.Integer(compute="get_log_count",string="Log Count")
    @api.multi
    def list_of_fbm_sales_orders(self):        
        action = {
            'domain': "[('id', 'in', " + str(self.amazon_fbm_sale_order_ids.ids) + " )]",
            'name': 'Amazon Sales Orders',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'amazon.sale.order.ept',
            'type': 'ir.actions.act_window',
                  }
        return action

    @api.model
    def create(self,vals):    
        try:
            sequence=self.env.ref('amazon_ept_v10.seq_mfn_sales_report')
            if sequence:
                report_name=sequence.next_by_id()
            else:
                report_name='/'
        except:
            report_name='/'
        vals.update({'name':report_name})
        return super(sale_order_report_ept,self).create(vals)
    
    @api.multi
    def on_change_seller_id(self, seller_id,start_date,end_date):
        value = {}
        if seller_id:          
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            value.update({'start_date':seller.order_last_sync_on,'end_date':datetime.now()})
        return {'value': value }
    
    @api.multi
    def list_of_logs(self):
        amazon_transaction_log_obj=self.env['amazon.transaction.log']
        model_id=amazon_transaction_log_obj.get_model_id('shipping.report.request.history')
        records=amazon_transaction_log_obj.search([('model_id','=',model_id),('res_id','=',self.id)])
        action = {
            'domain': "[('id', 'in', " + str(records.ids) + " )]",
            'name': 'Feed Logs',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'amazon.transaction.log',
            'type': 'ir.actions.act_window',
                  }
        return action
    
    @api.multi
    def get_report(self):
        self.ensure_one()
        seller = self.seller_id
        if not seller:
            raise Warning('Please select seller')
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code)
        if not self.report_id:
            return True
        try:
            result = mws_obj.get_report(report_id=self.report_id)
        except Exception,e:
            if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error)!=type(None):
                error = mws_obj.parsed_response_error.parsed or {}
                error_value = error.get('Message',{}).get('value')
                error_value = error_value if error_value else str(mws_obj.response.content)  
            else:
                error_value = str(e)
            raise Warning(error_value)
        
        if hasattr(mws_obj,'response') and hasattr(mws_obj.response,'status_code') and mws_obj.response.status_code!=400:
            data = mws_obj.response.content
            if not data:
                raise Warning('There is no Data in the report %s'%(self.name))
            
            result = base64.b64encode(data)
            format_of_file='.xml'
            if self.seller_id.create_sale_order_from_flat_or_xml_report=='flat':
                format_of_file='.csv'
            file_name = "Sale_Order_report_" + time.strftime("%Y_%m_%d_%H%M%S") + format_of_file
            attachment = self.env['ir.attachment'].create({
                                               'name': file_name,
                                               'datas': result,
                                               'datas_fname': file_name,
                                               'res_model': 'sale.order.report.ept',
                                               'res_id': self.id,
                                               'type': 'binary'
                                             })
            self.write({'attachment_id':attachment.id})
            self.message_post(body=_("<b>Sales Order Downloaded</b>"),attachment_ids=attachment.ids)

        return True
    
    @api.multi
    def request_report(self):
        seller=self.seller_id
#         if seller.create_sale_order_from_flat_or_xml_report=='api':
#             raise Warning('Please Select Import Order By Xml Or Flat Report')
        self.report_type='_GET_ORDERS_DATA_'
        
        if seller.create_sale_order_from_flat_or_xml_report=='flat':
            self.report_type='_GET_FLAT_FILE_ORDERS_DATA_'
        report_type,start_date,end_date =self.report_type,self.start_date,self.end_date
        if not seller:
            raise Warning('Please select Seller')
        
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
            
        if end_date:
            db_import_time = time.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S",db_import_time)
            end_date = time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(time.mktime(time.strptime(db_import_time,"%Y-%m-%dT%H:%M:%S"))))
            end_date = str(end_date)+'Z'
        else:
            today = datetime.now()
            earlier_str = today.strftime("%Y-%m-%dT%H:%M:%S")
            end_date = earlier_str+'Z'
        proxy_data=seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)
        instances = self.env['amazon.instance.ept'].search([('seller_id','=',seller.id)])
        
        marketplaceids = tuple(map(lambda x: x.market_place_id,instances))
        try:
            result = mws_obj.request_report(report_type, start_date=start_date, end_date=end_date, marketplaceids=marketplaceids)
            self.update_report_history(result)
        except Exception,e:
            if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                error = mws_obj.parsed_response_error.parsed or {}
                error_value = error.get('Message',{}).get('value')
                error_value = error_value if error_value else str(mws_obj.response.content)  
            else:
                error_value = str(e)
            raise Warning(error_value)

        return True  
    
    @api.model
    def update_report_history(self,request_result):
        result = request_result.parsed
        report_info = result.get('ReportInfo',{})
        report_request_info = result.get('ReportRequestInfo',{})
        request_id = report_state = report_id = False
        if report_request_info:
            request_id = str(report_request_info.get('ReportRequestId',{}).get('value',''))
            report_state = report_request_info.get('ReportProcessingStatus',{}).get('value','_SUBMITTED_')
            report_id = report_request_info.get('GeneratedReportId',{}).get('value',False)
        elif report_info:
            report_id = report_info.get('ReportId',{}).get('value',False)
            request_id = report_info.get('ReportRequestId',{}).get('value',False)
        
        if report_state =='_DONE_' and not report_id:
            self.get_report_list()
        vals = {}
        if not self.report_request_id and request_id:
            vals.update({'report_request_id':request_id}) 
        if report_state:
            vals.update({'state':report_state})
        if report_id:
            vals.update({'report_id':report_id})
        self.write(vals)
        return True
    
    @api.multi
    def unlink(self):
        for report in self:
            if report.state == 'processed':
                raise Warning(_('You cannot delete processed report.'))
        return super(sale_order_report_ept, self).unlink()
        
    @api.multi
    def download_report(self):
        self.ensure_one()
        if self.attachment_id:
            return {
                    'type' : 'ir.actions.act_url',
                    'url':   '/web/content/%s?download=true' % ( self.attachment_id.id ),
                    'target': 'self',
                    }
        return True
    
    @api.multi
    def get_report_request_list(self):
        self.ensure_one()
        seller = self.seller_id
        if not seller:
            raise Warning('Please select Seller')
        
        proxy_data=seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)
        if not self.report_request_id:
            return True
        try:
            result = mws_obj.get_report_request_list(requestids = (self.report_request_id,))
            self.update_report_history(result)
            
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
        has_next = result.parsed.get('HasNext',{}).get('value','false')
        while has_next =='true':
            next_token = result.parsed.get('NextToken',{}).get('value')
            try:
                result=mws_obj.get_report_request_list_by_next_token(next_token)
                self.update_report_history(result)

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
        
        return True
    
    @api.model
    def product_rules_to_create_new(self, order_line, instance,amazon_reference_ref):
        erp_product_obj=self.env['product.product']
        amazon_product_obj=self.env['amazon.product.ept']
        seller = instance.seller_id
        message = ''
        log_message = ''
        res_id = False
        model_name = 'amazon.product.ept'
        log_line_vals = {}
        if seller.create_sale_order_from_flat_or_xml_report=='xml':
            seller_sku=order_line.get('SKU',{}).get('value',False)
        if seller.create_sale_order_from_flat_or_xml_report=='flat':
            seller_sku=order_line.get('sku',False)
#         domain = [('instance_id','=',instance.id)]
#         seller_sku and domain.append(('seller_sku','=',seller_sku))
        amazon_product = amazon_product_obj.search_amazon_product(instance.id,seller_sku,'MFN')
        skip_order=False
        if not amazon_product:
            erp_product = erp_product_obj.search([('default_code','=',seller_sku),'|',('active','=',False),('active','=',True)], limit=1)
            if erp_product and not erp_product.active:
                erp_product.write({'active':True})
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
                log_message = 'Product %s created in amazon for %s instance'%(seller_sku, instance.name )
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
                product_asin=False
                if seller.create_sale_order_from_flat_or_xml_report=='xml':
                    product_asin= order_line.get('ASIN',{}).get('value',False)               
                    
                prod_vals={
                      'instance_id': instance.id,
                      'seller_sku': sku,
                      'product_asin':product_asin,
                      'type': erp_product and erp_product[0].type or 'product', 
                      'product_id': product_id,             
                      'purchase_ok' : True,
                      'sale_ok' : True,    
                      'exported_to_amazon': True,
                      'fulfillment_by' : "MFN",          
                      }
                if not erp_product:
                    if seller.create_sale_order_from_flat_or_xml_report=='xml':
                        name=order_line.get('Title',{}).get('value')
                    if seller.create_sale_order_from_flat_or_xml_report=='flat':
                        name=order_line.get('product_name',False)
                    prod_vals.update({'name':name,'default_code':sku})
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
                             'amazon_order_reference':amazon_reference_ref
                             }
        return log_line_vals, message
    
    @api.model
    def get_order_instance(self,seller,orders):
        marketplace_obj = self.env['amazon.marketplace.ept']
        mws_obj=Orders(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code)
        channel_instance_dict = {}
        shipped_orders_dict={}
        unshipped_orders_dict={}
        cancel_orders_list=[]
        try:
            result = mws_obj.get_order(amazon_order_ids=orders)
        except Exception as e:
            if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                error = mws_obj.parsed_response_error.parsed or {}
                error_value = error.get('Message',{}).get('value')
            else:
                error_value = str(e)
            raise Warning(error_value)                
        amz_orders = []
        if not isinstance(result.parsed.get('Orders',{}).get('Order',[]),list):
            amz_orders.append(result.parsed.get('Orders',{}).get('Order',{})) 
        else:
            amz_orders=result.parsed.get('Orders',{}).get('Order',[])
    
        for order in amz_orders:
            orderstatus=order.get('OrderStatus',{}).get('value',False)                 
            amazon_order_ref = order.get('AmazonOrderId',{}).get('value',False)
            sales_channel = order.get('SalesChannel',{}).get('value',False)
            if sales_channel not in channel_instance_dict:
                instance = marketplace_obj.find_instance(seller,sales_channel)
                channel_instance_dict.update({sales_channel:instance})
            instance = channel_instance_dict.get(sales_channel)
            if orderstatus=='Canceled':
                cancel_orders_list.append(amazon_order_ref)
            elif orderstatus=='Shipped':   
                shipped_orders_dict.update({amazon_order_ref:instance}) 
            else:
                unshipped_orders_dict.update({amazon_order_ref:instance})                                                                                                   
        return cancel_orders_list,shipped_orders_dict,unshipped_orders_dict
    
    @api.multi   
    def button_process_sale_order_report(self): 
        if self.seller_id.create_sale_order_from_flat_or_xml_report=="flat":
            self.button_process_sale_order_by_flat_report()
        if self.seller_id.create_sale_order_from_flat_or_xml_report=="xml":
            self.button_process_sale_order_by_xml_report()
    @api.multi
    def button_process_sale_order_by_flat_report(self):
        self.ensure_one()
        if not self.attachment_id:
            raise Warning("There is no any report are attached with this record.")   
        seller=self.seller_id
        amazon_order_obj=self.env['amazon.sale.order.ept']
        instances=self.env['amazon.instance.ept'].search([('seller_id','=',seller.id)])        
        imp_file = StringIO(base64.decodestring(self.attachment_id.datas).decode(instances[0].amazon_encodings))
        order_detail={}
        amazon_orders_reference=[]
        reader = csv.DictReader(imp_file,delimiter='\t')
        instance_ids=instances.ids
        for line in reader:
            order_id=line.get('order-id',False)
            if not line.get('sku'):
                continue
            amazon_order=amazon_order_obj.search([('instance_id','in',instance_ids),('amazon_reference','=',order_id)])
            if amazon_order:
                continue
            if order_id not in amazon_orders_reference:
                amazon_orders_reference.append(order_id)
            order_item_id=line.get('order-item-id',False)
            sku=line.get('sku',False)
            product_name=line.get('product-name',False)
            qty=line.get('quantity-purchased',0.0)
            item_price=line.get('item-price',0.0)
            item_tax=line.get('item-tax',0.0)
            shipping_price=line.get('shipping-price',0.0)
            shipping_tax=line.get('shipping-tax',0.0)
            gift_wrap_price=line.get('gift-wrap-price',0.0) and line.get('gift-wrap-price',0.0) or 0.0
            gift_wrap_tax=line.get('gift-wrap-tax',0.0) and line.get('gift-wrap-tax',0.0) or 0.0
            item_promotion_discount=line.get('item-promotion-discount',0.0) and line.get('item-promotion-discount',0.0) or 0.0  
            item_promotion_id=line.get('item-promotion-id',False)
            gift_wrap_type=line.get('gift-wrap-type',False)  
            gift_message_text=line.get('gift-message-text',False)    
            ship_promotion_discount=line.get('ship-promotion-discount',0.0) and line.get('ship-promotion-discount',0.0) or 0.0   
            ship_promotion_id=line.get('ship-promotion-id',False)        
            purchase_date=line.get('purchase-date',False)            
            ship_service_level=line.get('ship-service-level',False)
            receipt_name=line.get('recipient-name',False)
            buyer_email=line.get('buyer-email',False)
            buyer_name=line.get('buyer-name',False)
            buyer_phone_number=line.get('buyer-phone-number',False)
            ship_address_1=line.get('ship-address-1',False)
            ship_address_2=line.get('ship-address-2',False)
            ship_address_3=line.get('ship-address-3',False)
            ship_city=line.get('ship-city',False)
            ship_state=line.get('ship-state',False)
            ship_postal_code=line.get('ship-postal-code',False)
            ship_country=line.get('ship-country',False)
            ship_phone_number=line.get('ship-phone-number',False)
            sales_channel=line.get('sales-channel',False)

            if order_detail.has_key(order_id):
                order = order_detail.get(order_id)                
                lines = order.get('order_lines',[])
                lines.append({  
                              'order_item_id':order_item_id,
                              'sku':sku,                              
                              'product_name':product_name,
                              'qty':qty,
                              'item_price':item_price,
                              'item_tax':item_tax,
                              'shipping_price':shipping_price,
                              'shipping_tax':shipping_tax,
                              'gift_wrap_price':gift_wrap_price,
                              'gift_wrap_tax':gift_wrap_tax,
                              'item_promotion_discount':item_promotion_discount,
                              'item_promotion_id':item_promotion_id,
                              'gift_wrap_type':gift_wrap_type,
                              'gift_message_text':gift_message_text,
                              'ship_promotion_discount':ship_promotion_discount,
                              'ship_promotion_id':ship_promotion_id
                              })                            
                order.update({'order_lines':lines})
                order_detail.update({order_id:order})
                continue

            buyers_data={'buyer_name':buyer_name,'buyer_email':buyer_email,'receipt_name':receipt_name,'buyer_phone_number':buyer_phone_number}
            
            shipping_data={'ship_address_1':ship_address_1,
                              'ship_address_2':ship_address_2,
                              'ship_address_3':ship_address_3,
                              'ship_city':ship_city,
                              'ship_state':ship_state,
                              'ship_postal_code':ship_postal_code,
                              'ship_country':ship_country,
                              'ship_phone_number':ship_phone_number}
            order_detail.update({order_id:{'order_lines':[{'order_item_id':order_item_id,
                                                           'sku':sku,
                                                           'product_name':product_name,
                                                           'qty':qty,
                                                           'item_price':item_price,
                                                           'item_tax':item_tax,
                                                           'shipping_price':shipping_price,
                                                           'shipping_tax':shipping_tax,
                                                           'gift_wrap_price':gift_wrap_price,
                                                           'gift_wrap_tax':gift_wrap_tax,
                                                           'item_promotion_discount':item_promotion_discount,
                                                           'item_promotion_id':item_promotion_id,
                                                           'gift_wrap_type':gift_wrap_type,
                                                           'gift_message_text':gift_message_text,
                                                           'ship_promotion_discount':ship_promotion_discount,
                                                           'ship_promotion_id':ship_promotion_id}],
                                           'purchase_date':purchase_date,
                                           'ship_service_level':ship_service_level,
                                           'buyers_data':buyers_data,
                                           'shipping_data':shipping_data,
                                           'sales_channel':sales_channel,
                                                            }})
        self.process_sale_order_by_flat_report_file(order_detail,amazon_orders_reference)
        self.write({'state':'processed'})
        self._cr.commit()
        return True
        
    @api.multi
    def process_sale_order_by_flat_report_file(self,order_details={},amazon_orders_reference=[]):
        self.ensure_one()
        auto_work_flow_obj=self.env['sale.workflow.process.ept']
        stock_immediate_transfer_obj=self.env['stock.immediate.transfer']
        seller=self.seller_id
        for x in xrange(0, len(amazon_orders_reference),50):
            odoo_order_ids = []
            auto_process_orders=[]
            cancel_orders_list=[]
            shipped_orders_dict={}
            unshipped_orders_dict={}
            unshipped_orders_list=[]
            shipped_orders_list=[]
            orders=amazon_orders_reference[x:x + 50]
            cancel_orders_list,shipped_orders_dict,unshipped_orders_dict=self.get_order_instance(seller, orders)
            for amazon_order_ref in orders:
                order_detail=order_details.get(amazon_order_ref)
                if not order_detail:
                    continue
                unshipped_orders_list=unshipped_orders_dict.keys()
                shipped_orders_list=shipped_orders_dict.keys()
                if amazon_order_ref in cancel_orders_list:
                    continue
                instance=False
                if amazon_order_ref in unshipped_orders_list:
                    instance=unshipped_orders_dict.get(amazon_order_ref)
                elif amazon_order_ref in shipped_orders_list and seller.import_shipped_fbm_orders:
                    instance=shipped_orders_dict.get(amazon_order_ref)
                if not instance:
                    continue 
                amazon_order = self.create_sale_order_by_flat_report(amazon_order_ref,order_detail,instance)
                if amazon_order and amazon_order.sale_order_id:
                    odoo_order_ids.append(amazon_order.sale_order_id.id)
                if amazon_order and amazon_order_ref in shipped_orders_list:
                    auto_process_orders.append(amazon_order.sale_order_id.id)
    
            if odoo_order_ids:
                auto_work_flow_obj.auto_workflow_process(ids=odoo_order_ids)   
            if auto_process_orders:
                odoo_orders=self.env['sale.order'].search([('id','in',auto_process_orders)])
                for odoo_order in odoo_orders:
                    if odoo_order.state=='draft':
                        odoo_order.action_confirm()
                    for picking in odoo_order.picking_ids:
                        if picking.state in ['waiting','confirmed']:
                            picking.action_assign()
                        if picking.state in ['confirmed','partially_available']:
                            picking.force_assign()
                        if picking.state=='assigned':      
                            stock_immediate_transfer_obj.create({'pick_id':picking.id}).process()
            self._cr.commit()      
        self.write({'state':'processed'})
        return True    
   
    @api.model
    def create_sale_order_by_flat_report(self,amazon_order_ref,order_data,instance):
        amazon_sale_line_obj = self.env['amazon.sale.order.line.ept']
        amazon_order_obj=self.env['amazon.sale.order.ept']
        order_lines=order_data.get('order_lines',{})
        transaction_log_lines = []
        skip_order = False
        skip_line = False 
        action_type = ''
        message= ''
        for order_line in order_lines:
            log_line_vals, message = self.product_rules_to_create_new(order_line, instance,amazon_order_ref)
            log_action_type = log_line_vals.get('action_type', '')
            if log_action_type:
                action_type = log_action_type
                         
            skip_line = log_line_vals.get('skip_record', False)
            if skip_line :
                skip_order = True
                 
            if log_line_vals:
                transaction_log_lines.append((0,0,log_line_vals))
             
        if skip_order or action_type == 'create':   
            job_log_vals = {
                            'transaction_log_ids' : transaction_log_lines,
                            'skip_process' : skip_order,
                            'application' : 'sales',
                            'operation_type' : 'import',
                            'message' : message,
                            'instance_id':instance.id
                            }
            self.env['amazon.process.log.book'].create(job_log_vals) 
        if skip_order :
            return False
        
        partner_dict=self.create_or_update_partner_by_flat_report(order_data,instance)
                
        order_vals = self.create_sales_order_vals_by_flat_report(partner_dict,order_data,instance,amazon_order_ref)
        amazon_order = amazon_order_obj.create(order_vals)
        
        for order_line in order_lines:
            amazon_sale_line_obj.create_sale_order_line_by_flat_report(order_line,instance,amazon_order)
        
        return amazon_order
                                        
    @api.model
    def create_sales_order_vals_by_flat_report(self,partner_dict,order,instance,amazon_order_ref):
        delivery_carrier_obj=self.env['delivery.carrier']
        sale_order_obj=self.env['sale.order']
        fpos = instance.fiscal_position_id and instance.fiscal_position_id.id or False
        shipping_category=order.get('ship_service_level',False)
        if order.get('purchase_date',False):
            order_date=order.get('purchase_date',False)
            date_order=parser.parse(order_date).astimezone(utc).strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_order=time.strftime('%Y-%m-%d %H:%M:%S')        
            date_order=str(date_order) 
        ordervals = {
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
            'client_order_ref':amazon_order_ref or False,
            'invoice_policy':instance.invoice_policy or False,
        }
        if not instance.is_default_odoo_sequence_in_sales_order:
            ordervals.update({'name':"%s%s" %(instance.order_prefix and instance.order_prefix+'_' or '',amazon_order_ref)})
        carrier=delivery_carrier_obj.search(['|',('amazon_code','=',shipping_category),('name','=',shipping_category)],limit=1)
        ordervals.update({'carrier_id':carrier.id})
        new_record = sale_order_obj.new(ordervals)
        new_record.onchange_partner_shipping_id()
        ordervals = sale_order_obj._convert_to_write(new_record._cache)
        ordervals.update({
                          'instance_id':instance and instance.id or False,
                          'amazon_reference': amazon_order_ref,
                          'shipment_service_level_category':shipping_category,
                          'sale_order_report_id':self.id,      
                          })
        return ordervals                

    @api.model
    def create_or_update_partner_by_flat_report(self,order,instance):
        return_partner={}
        state_id,partner= False,False
        partner_obj = self.env['res.partner']
        state_obj = self.env['res.country.state']     
        billing_info = order.get('buyers_data',{})
        buyer_email = billing_info.get('buyer_email',False)
        buyer_name = billing_info.get('buyer_name',False)
        buyer_phone = billing_info.get('buyer_phone_number',False)
        receipt_name=billing_info.get('receipt_name',False)
        shipping_info = order.get('shipping_data',{})
        ship_add1 = shipping_info.get('ship_address_1',False)
        ship_add2 = shipping_info.get('ship_address_2',False)
        ship_add3 = shipping_info.get('ship_address_3',False)
        ship_city = shipping_info.get('ship_city',False)
        ship_state = shipping_info.get('ship_state',False)
        ship_postal_code=shipping_info.get('ship_postal_code',False)
        ship_country = shipping_info.get('ship_country',False)
        ship_phone = shipping_info.get('ship_phone_number',False)   
        
     
        invoice_partner=False
        partner_id = instance.partner_id and instance.partner_id.id or False
        if buyer_name.lower()!=receipt_name.lower():
                    
            domain = [('name','=',buyer_name),('phone','=',buyer_phone),('email','=',buyer_email)]
            partnervals = {
                    'opt_out':True,'is_company':False,'customer' : True,'phone' :buyer_phone,'email':buyer_email,'parent_id':partner_id,
                    'lang':instance.lang_id and instance.lang_id.code,'company_id':instance.company_id.id
                }
            if instance.customer_is_company and not partner_id:
                partnervals.update({'is_company':True})
                                     
            if instance.pricelist_id:
                partnervals.update({'property_product_pricelist':instance.pricelist_id.id})
            invoice_partner = partner_obj.search(domain)                
            if invoice_partner:
                invoice_partner = invoice_partner[0]
                return_partner.update({'invoice_address':invoice_partner.id,'pricelist_id':invoice_partner.property_product_pricelist.id,'delivery_address':invoice_partner.id})
            else:
                partnervals.update({'name':buyer_name})   
                invoice_partner = partner_obj.create(partnervals)
                invoice_partner and return_partner.update({'invoice_address':invoice_partner.id,'pricelist_id':invoice_partner.property_product_pricelist.id,'delivery_address':invoice_partner.id})
            
            if not instance.customer_is_company and not partner_id:
                invoice_partner.write({'is_company':True})           
                
        country = self.env['res.country'].search([('code','=',ship_country)])   
        country = country and country[0]   
        if country:
            state_id = state_obj.search(['|',('name','=',ship_state),('code','=',ship_state),('country_id','=',country.id)],limit=1)   
        else:
            state_id = state_obj.search(['|',('name','=',ship_state),('code','=',ship_state)],limit=1) 
        
                          
#        if not result_state:
#            state = country and state_obj.create({'country_id':country.id, 'name':ship_state,'code':ship_state[:3]})
#            state_id=state and state.id or False
#         else:
                                 
        domain = [('name','=',receipt_name)]
        ship_add1 and domain.append(('street','=',ship_add1))
        if ship_add2 and ship_add3:
            ship_add2 = ship_add2+' '+ship_add3
            domain.append(('street2','=',ship_add2))
        elif ship_add2:
            domain.append(('street2','=',ship_add2))
        elif ship_add3:
            ship_add2 = ship_add3
            domain.append(('street2','=',ship_add3))   
        buyer_email and domain.append(('email','=',buyer_email))
        ship_phone and domain.append(('phone','=',ship_phone))
        ship_city and domain.append(('city','=',ship_city))
        ship_postal_code and domain.append(('zip','=',ship_postal_code))
        state_id and domain.append(('state_id','=',state_id.id))
        country and domain.append(('country_id','=',country.id))

        partnervals = {
               'opt_out':True,'is_company':False,'customer' : False,'name':receipt_name,'street' : ship_add1,'street2' : ship_add2,'city' : ship_city,'zip' : ship_postal_code,
               'country_id' : country and country.id,'phone' :ship_phone,'state_id' : state_id.id,'email':buyer_email,'parent_id': partner_id or invoice_partner and invoice_partner.id,
               'lang':instance.lang_id and instance.lang_id.code,'company_id':instance.company_id.id
           }
        if instance.pricelist_id:
            partnervals.update({'property_product_pricelist':instance.pricelist_id.id})
            
        exist_partner=partner_obj.search(domain)                
        if exist_partner:
            return_partner.update({'delivery_address':exist_partner[0].id})
        else:
            partnervals.update({'type':'delivery'})               
            partner = partner_obj.create(partnervals)
            return_partner.update({'delivery_address':partner.id,'pricelist_id':partner.property_product_pricelist.id})
            
        if not return_partner.has_key('invoice_address'):
            return_partner.update({'invoice_address':exist_partner and exist_partner[0].id or partner and partner.id})
        return return_partner  
            
    @api.multi
    def button_process_sale_order_by_xml_report(self):
        self.ensure_one()
        instances=self.env['amazon.instance.ept'].search([('seller_id','=',self.seller_id.id)])
        imp_file = StringIO(base64.decodestring(self.attachment_id.datas).decode(instances[0].amazon_encodings or 'utf-8'))
        content = imp_file.read()
        response = DictWrapper( content, "Message")
        result = response.parsed
        orders = []
        if not isinstance(result,list):
            orders.append(result) 
        else:
            orders = result         
        self.process_sale_order_xml_report_file(orders)
        self._cr.commit()
        return True
    
    @api.multi
    def process_sale_order_xml_report_file(self,orders_data):
        self.ensure_one()
        auto_work_flow_obj=self.env['sale.workflow.process.ept']
        sale_order_obj=self.env['sale.order']
        stock_immediate_transfer_obj=self.env['stock.immediate.transfer']
        if not self.attachment_id:
            raise Warning("There is no any report are attached with this record.")      
        odoo_order_ids = []
        amazon_orders_reference=[]
        auto_process_orders=[]
        amazon_order_obj=self.env['amazon.sale.order.ept']
        seller=self.seller_id
        instances=self.env['amazon.instance.ept'].search([('seller_id','=',self.seller_id.id)])
        instance_ids=instances and instances.ids
        for x in xrange(0, len(orders_data), 50):
            orders=orders_data[x:x + 50]
            amazon_orders_reference=[]
            cancel_orders_list=[]
            shipped_orders_dict={}
            unshipped_orders_dict={}
            unshipped_orders_list=[]
            shipped_orders_list=[]
            for order in orders:
                order_data = order.get('OrderReport',{})
                amazon_order_ref = order_data.get('AmazonOrderID',{}).get('value',False)
                amazon_order=amazon_order_obj.search([('instance_id','in',instance_ids),('amazon_reference','=',amazon_order_ref)])
                if amazon_order:
                    continue
                if amazon_order_ref not in amazon_orders_reference:
                    amazon_orders_reference.append(amazon_order_ref)
            if amazon_orders_reference:
                cancel_orders_list,shipped_orders_dict,unshipped_orders_dict=self.get_order_instance(seller, amazon_orders_reference)
                unshipped_orders_list=unshipped_orders_dict.keys()
                shipped_orders_list=shipped_orders_dict.keys()
            for order in orders:
                order_data = order.get('OrderReport',{})
                amazon_order_ref = order_data.get('AmazonOrderID',{}).get('value',False)                
                if amazon_order_ref in cancel_orders_list:
                    continue
                instance=False
                if amazon_order_ref in unshipped_orders_list:
                    instance=unshipped_orders_dict.get(amazon_order_ref)
                elif amazon_order_ref in shipped_orders_list and seller.import_shipped_fbm_orders:
                    instance=shipped_orders_dict.get(amazon_order_ref)
                if not instance:
                    continue 
                amazon_order = self.create_sale_order_by_xml_report(order_data,instance)
                if amazon_order and amazon_order.sale_order_id:
                    odoo_order_ids.append(amazon_order.sale_order_id.id)
                if amazon_order_ref in shipped_orders_list:
                    auto_process_orders.append(amazon_order.id)                               
            if odoo_order_ids:
                auto_work_flow_obj.auto_workflow_process(ids=odoo_order_ids)                 
                odoo_orders=sale_order_obj.search([('id','in',auto_process_orders)])
                for odoo_order in odoo_orders:                
                    for picking in odoo_order.picking_ids:
                        if picking.state in ['waiting','confirmed']:
                            picking.action_assign()
                        if picking.state in ['confirmed','partially_available']:
                            picking.force_assign()
                        if picking.state=='assigned':      
                            stock_immediate_transfer_obj.create({'pick_id':picking.id}).process()
                self._cr.commit()
        self.write({'state':'processed'})
        
        return True
    
    @api.model
    def create_sale_order_by_xml_report(self,order_data,instance):
        amazon_sale_line_obj = self.env['amazon.sale.order.line.ept']

        order_lines = []
        if not isinstance(order_data.get('Item',[]),list):
            order_lines.append(order_data.get('Item',[])) 
        else:
            order_lines=order_data.get('Item',[])
        
        transaction_log_lines = []
        skip_order = False
        skip_line = False 
        action_type = ''
        message= ''
        amazon_order_ref=order_data.get('AmazonOrderID',{}).get('value')
        for order_line in order_lines:
            log_line_vals, message = self.product_rules_to_create_new(order_line, instance,amazon_order_ref)
            log_action_type = log_line_vals.get('action_type', '')
            if log_action_type:
                action_type = log_action_type
                        
            skip_line = log_line_vals.get('skip_record', False)
            if skip_line :
                skip_order = True
                
            if log_line_vals:
                transaction_log_lines.append((0,0,log_line_vals))
            
        if skip_order or action_type == 'create':   
            job_log_vals = {
                            'transaction_log_ids' : transaction_log_lines,
                            'skip_process' : skip_order,
                            'application' : 'sales',
                            'operation_type' : 'import',
                            'message' : message,
                            'instance_id':instance.id
                            }
            self.env['amazon.process.log.book'].create(job_log_vals) 
        
        if skip_order :
            return False
        
        partner_dict=self.create_or_update_partner_by_xml_report(order_data,instance)        
        order_vals = self.create_sales_order_vals_by_xml_report(partner_dict,order_data,instance)
        amazon_order = self.env['amazon.sale.order.ept'].create(order_vals)
        
        for order_line in order_lines:
            amazon_sale_line_obj.create_sale_order_line_by_xml_report(order_line,instance,amazon_order)
        
        return amazon_order
    
    @api.model
    def create_sales_order_vals_by_xml_report(self,partner_dict,order,instance):
        delivery_carrier_obj=self.env['delivery.carrier']
        sale_order_obj=self.env['sale.order']
        fpos = instance.fiscal_position_id and instance.fiscal_position_id.id or False
        shipping_category=order.get('FulfillmentData').get('FulfillmentServiceLevel',{}).get('value',False)            
        date_order=False
        if order.get('OrderDate',{}).get('value',False):
            date_order=parser.parse(order.get('OrderDate',False).get('value',False)).astimezone(utc).strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_order=time.strftime('%Y-%m-%d %H:%M:%S')        
        ordervals = {
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
            'client_order_ref':order.get('AmazonOrderID',{}).get('value',False),
            'invoice_policy':instance.invoice_policy or False,            
        }
        if not instance.is_default_odoo_sequence_in_sales_order:
            ordervals.update({'name':"%s%s" %(instance.order_prefix and instance.order_prefix+'_' or '', order.get('AmazonOrderID',{}).get('value'))})
        carrier=delivery_carrier_obj.search(['|',('amazon_code','=',shipping_category),('name','=',shipping_category)],limit=1)
        ordervals.update({'carrier_id':carrier.id})
        new_record = sale_order_obj.new(ordervals)
        new_record.onchange_partner_shipping_id()
        ordervals = sale_order_obj._convert_to_write(new_record._cache)
        ordervals.update({
                          'instance_id':instance and instance.id or False,
                          'amazon_reference': order.get('AmazonOrderID',{}).get('value',False),
                          'shipment_service_level_category':shipping_category,
                          'sale_order_report_id':self.id,  
                                    
                          })
        return ordervals 
    
    @api.model
    def create_or_update_partner_by_xml_report(self,order,instance):
        return_partner={}
        state_id,partner= False, False
        partner_obj = self.env['res.partner']
        billing_info = order.get('BillingData',{})
        email = billing_info.get('BuyerEmailAddress',{}).get('value')
        name = billing_info.get('BuyerName',{}).get('value')
        phone = billing_info.get('BuyerPhoneNumber',{}).get('value')
        address = billing_info.get('Address',{})
        bill_add1 = address.get('AddressFieldOne',{}).get('value','')
        bill_add2 = address.get('AddressFieldTwo',{}).get('value','')
        bill_add3 = address.get('AddressFieldThree',{}).get('value','')
        bill_city = address.get('City',{}).get('value')
        bill_state = address.get('StateOrRegion',{}).get('value')
        bill_postal_code = address.get('PostalCode',{}).get('value')
        bill_country = address.get('CountryCode',{}).get('value')
        
        shipping_info = order.get('FulfillmentData',{})
        ship_address = shipping_info.get('Address',{})
        ship_name = ship_address.get('Name',{}).get('value','')
        ship_add1 = ship_address.get('AddressFieldOne',{}).get('value','')
        ship_add2 = ship_address.get('AddressFieldTwo',{}).get('value','')
        ship_add3 = ship_address.get('AddressFieldThree',{}).get('value','')
        ship_city = ship_address.get('City',{}).get('value')
        ship_state = ship_address.get('StateOrRegion',{}).get('value')
        ship_country = ship_address.get('CountryCode',{}).get('value')
        ship_postal_code = ship_address.get('PostalCode',{}).get('value')
        ship_phone = ship_address.get('PhoneNumber',{}).get('value')        
        
        ship_address_same = False
        if ship_name==name and ship_add1 == bill_add1 and ship_add2 == bill_add2 and ship_add3 == bill_add3 and ship_city==bill_city and \
        ship_state == bill_state and ship_postal_code == bill_postal_code and ship_country==bill_country:
            ship_address_same = True
        state_obj = self.env['res.country.state']
        
        partner_id = instance.partner_id and instance.partner_id.id or False
        
        country = self.env['res.country'].search([('code','=',bill_country)])   
        country = country and country[0]            
        if bill_state:
            if country:
                state_id = state_obj.search(['|',('name','=',bill_state),('code','=',bill_state),('country_id','=',country.id)],limit=1)    
            else:
                state_id = state_obj.search(['|',('name','=',bill_state),('code','=',bill_state)],limit=1)                    
#             if not result_state:
#                 state = country and state_obj.create({'country_id':country.id, 'name':bill_state,'code':bill_state[:3]})
#                 state_id=state and state.id or False
#             else:

        domain = [('name','=',name)]
        bill_add1 and domain.append(('street','=',bill_add1))
        if bill_add2 and bill_add3:
            bill_add2 = bill_add2+' '+bill_add3
            domain.append(('street2','=',bill_add2))
        elif bill_add2:
            domain.append(('street2','=',bill_add2))
        elif bill_add3:
            bill_add2 = bill_add3
            domain.append(('street2','=',bill_add3))   
        email and domain.append(('email','=',email))
        phone and domain.append(('phone','=',phone))
        bill_city and domain.append(('city','=',bill_city))
        bill_postal_code and domain.append(('zip','=',bill_postal_code))
        state_id and domain.append(('state_id','=',state_id.id))
        country and domain.append(('country_id','=',country.id))

        partnervals = {
                'opt_out':True,'is_company':False,'customer' : True,'street' : bill_add1,'street2' : bill_add2,'city' : bill_city,
                'country_id' : country and country.id,'phone' :phone,'zip' : bill_postal_code,'state_id' : state_id.id,'email':email,'parent_id':partner_id,
                'lang':instance.lang_id and instance.lang_id.code,'company_id':instance.company_id.id
            }
        if instance.customer_is_company and not partner_id:
            partnervals.update({'is_company':True})
                    
        if instance.pricelist_id:
            partnervals.update({'property_product_pricelist':instance.pricelist_id.id})

        invoice_partner = partner_obj.search(domain)                
        if invoice_partner:
            invoice_partner = invoice_partner[0]
            return_partner.update({'invoice_address':invoice_partner.id,'pricelist_id':invoice_partner.property_product_pricelist.id,'delivery_address':invoice_partner.id})
        else:
            partnervals.update({'name':name})    #'type':'default',            
            invoice_partner = partner_obj.create(partnervals)
            invoice_partner and return_partner.update({'invoice_address':invoice_partner.id,'pricelist_id':invoice_partner.property_product_pricelist.id,'delivery_address':invoice_partner.id})
        
        if not ship_address_same:
            if ship_country!=bill_country:
                country = self.env['res.country'].search([('code','=',ship_country)])   
                country = country and country[0]                        
            if ship_state and ship_state!=bill_state:
                if country:
                    state_id = state_obj.search(['|',('name','=',ship_state),('code','=',ship_state),('country_id','=',country.id)],limit=1)    
                else:
                    state_id = state_obj.search(['|',('name','=',ship_state),('code','=',ship_state)],limit=1)                    
#                 if not result_state:
#                     state = country and state_obj.create({'country_id':country.id, 'name':ship_state,'code':ship_state[:3]})
#                     state_id=state and state.id or False
#                 else:
#                     state_id=result_state.id

            elif not ship_state:
                state_id = False
                                
            domain = [('name','=',ship_name)]
            ship_add1 and domain.append(('street','=',ship_add1))
            if ship_add2 and ship_add3:
                ship_add2 = ship_add2+' '+ship_add3
                domain.append(('street2','=',ship_add2))
            elif ship_add2:
                domain.append(('street2','=',ship_add2))
            elif ship_add3:
                ship_add2 = ship_add3
                domain.append(('street2','=',ship_add3))   
            email and domain.append(('email','=',email))
            ship_phone and domain.append(('phone','=',ship_phone))
            ship_city and domain.append(('city','=',ship_city))
            ship_postal_code and domain.append(('zip','=',ship_postal_code))
            state_id and domain.append(('state_id','=',state_id.id))
            country and domain.append(('country_id','=',country.id))

            partnervals = {
                    'opt_out':True,'is_company':False,'customer' : False,'street' : ship_add1,'street2' : ship_add2,'city' : ship_city,
                    'country_id' : country and country.id,'phone' :ship_phone,'zip' : ship_postal_code,'state_id' : state_id.id,'email':email,'parent_id': partner_id or invoice_partner.id,
                    'lang':instance.lang_id and instance.lang_id.code,'company_id':instance.company_id.id
                }
            if instance.pricelist_id:
                partnervals.update({'property_product_pricelist':instance.pricelist_id.id})
                
            exist_partner=partner_obj.search(domain)                
            if exist_partner:
                return_partner.update({'delivery_address':exist_partner[0].id})
            else:
                partnervals.update({'type':'delivery','name':ship_name})                
                partner = partner_obj.create(partnervals)
                return_partner.update({'delivery_address':partner.id,'pricelist_id':partner.property_product_pricelist.id})
            
            if not instance.customer_is_company and not partner_id:
                invoice_partner.write({'is_company':True})
                
        return return_partner                

    
    @api.model
    def auto_process_fbm_flat_report(self,args={}):
        seller_id = args.get('seller_id',False) or self._context.get('seller_id')
        if seller_id:
            seller = self.env['amazon.seller.ept'].search([('id','=',seller_id)])
            sales_reports = self.search([('seller_id','=',seller.id),
                                            ('state','in',['_DONE_']),
                                            ])            
            for report in sales_reports:
                try:
                    report.get_report()
                except:                 
                    time.sleep(120)  
                    report.get_report()
                report.button_process_sale_order_by_flat_report()   
                self._cr.commit()
                        
        return True       
    
    @api.model
    def auto_process_fbm_xml_report(self,args={}):
        seller_id = args.get('seller_id',False) or self._context.get('seller_id')
        if seller_id:
            seller = self.env['amazon.seller.ept'].search([('id','=',seller_id)])            
            sales_reports = self.search([('seller_id','=',seller.id),
                                            ('state','in',['_DONE_']),
                                            ])      
                          
            for report in sales_reports:
                try:
                    report.get_report()
                except:
                    time.sleep(120)                        
                    report.get_report()                
                report.button_process_sale_order_by_xml_report()   
                self._cr.commit()       
        return True