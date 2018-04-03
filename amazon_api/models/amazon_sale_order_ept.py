# -*- encoding: utf-8 -*-

from odoo import models, fields,api,_
import time
from datetime import timedelta,datetime
from dateutil import parser
from odoo.exceptions import Warning
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Orders,Feeds
import pytz
from odoo.exceptions import ValidationError, UserError

utc = pytz.utc

class amazon_sale_order_ept(models.Model):
    _inherit = 'amazon.sale.order.ept'

    def get_currency_symbol(self, order):
        '''返回币种'''
        CurrencyCode = order.get('OrderTotal', {}).get('CurrencyCode', {}).get('value', '')
        currency = self.env['res.currency'].search([('name', '=', CurrencyCode)])
        if not currency:
            raise UserError(u'币种%s系统不存在' % CurrencyCode)
        return {'currency_id_amazon': currency.id}

    @api.multi
    def create_sales_order_vals(self, partner_dict, order, instance):
        # print 'create_sales_order_vals...'
        # print 'partner_dict:',partner_dict
        # print 'order:',order
        # print 'instance:',instance
        delivery_carrier_obj = self.env['delivery.carrier']
        sale_order_obj = self.env['sale.order']
        fpos = instance.fiscal_position_id and instance.fiscal_position_id.id or False
        shipping_category = order.get('ShipmentServiceLevelCategory', {}).get('value', False)
        date_order = False
        if order.get('PurchaseDate', {}).get('value', False):
            date_order = parser.parse(order.get('PurchaseDate', False).get('value', False)).astimezone(utc).strftime(
                '%Y-%m-%d %H:%M:%S')
        else:
            date_order = time.strftime('%Y-%m-%d %H:%M:%S')
        ########################## 修改 ########################################
        result = self.env['res.partner'].search([('amazon_instance_id', '=', instance.id)])
        if result and len(result) > 1:
            raise UserError(u'该店铺对应多个res.partner')
        if not result:
            raise UserError(u'该店铺没有对应的res.partner')
        shop = result[0]
        if not shop.parent_id:
            raise UserError(u'shop_id.parent_id为空！')
        e_order_amount = float(order.get('OrderTotal', {}).get('Amount', {}).get('value', 0))
        e_order_freight = 0
        e_order_commission = e_order_amount * 0.15
        ordervals = {
            'company_id': instance.company_id.id,
            'partner_id': shop.parent_id.id,
            'partner_invoice_id': shop.parent_id.id,
            'partner_shipping_id': partner_dict.get('delivery_address'),
            'shop_id': shop.id,
            'e_order_amount': e_order_amount,
            'e_order_freight': e_order_freight,
            'e_order_commission': e_order_commission,
            'amazon_state': order.get('OrderStatus', {}).get('value', ''),
        }
        currency_dic = self.get_currency_symbol(order)
        ordervals.update(currency_dic)
        new_record = sale_order_obj.new(ordervals)
        ##################################################################
        new_record.onchange_partner_id()
        ordervals = sale_order_obj._convert_to_write({name: new_record[name] for name in new_record._cache})
        new_record = sale_order_obj.new(ordervals)
        new_record.onchange_partner_shipping_id()
        ordervals = sale_order_obj._convert_to_write({name: new_record[name] for name in new_record._cache})
        pricelist_id = instance.pricelist_id.id
        if not pricelist_id:
            pricelist = self.env['product.pricelist'].search([], limit=1)
            pricelist_id = pricelist.id
        ordervals.update(
            {
                'company_id': instance.company_id.id,
                'picking_policy': instance.picking_policy or 'direct',
                'partner_invoice_id': shop.parent_id.id,
                'date_order': str(date_order),
                'warehouse_id': instance.warehouse_id.id,
                'partner_id': shop.parent_id.id,
                'partner_shipping_id': partner_dict.get('delivery_address'),
                'state': 'draft',
                'team_id': instance.team_id and instance.team_id.id or False,
                'pricelist_id': pricelist_id,
                'fiscal_position_id': fpos,
                'payment_term_id': instance.payment_term_id.id or False,
                'auto_workflow_process_id': instance.auto_workflow_id.id,
                'client_order_ref': order.get('AmazonOrderId', {}).get('value', False),
                'invoice_policy': instance.invoice_policy or False,
                'instance_id': instance and instance.id or False,
                'amazon_reference': order.get('AmazonOrderId', {}).get('value', False),
                'shipment_service_level_category': shipping_category
            })
        if not instance.is_default_odoo_sequence_in_sales_order:
            ordervals.update({'name': "%s%s" % (
            instance.order_prefix and instance.order_prefix + '_' or '', order.get('AmazonOrderId', {}).get('value'))})
        carrier = delivery_carrier_obj.search(
            ['|', ('amazon_code', '=', shipping_category), ('name', '=', shipping_category)], limit=1)
        ordervals.update({'carrier_id': carrier.id})
        return ordervals

    """Import Sales Order From Amazon"""

    @api.multi
    def import_sales_order(self, seller, marketplaceids=[], created_before='', created_after=''):
        """Create Object for the integrate with amazon"""
        print 'import_sales_order'
        proxy_data = seller.get_proxy_server()
        orderstatus = ('Unshipped', 'PartiallyShipped', 'Shipped')
        mws_obj = Orders(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                         account_id=str(seller.merchant_id),
                         region=seller.country_id.amazon_marketplace_code or seller.country_id.code, proxies=proxy_data)
        try:
            result = mws_obj.list_orders(marketplaceids=marketplaceids, created_after=created_after,
                                         created_before=created_before, orderstatus=orderstatus,
                                         fulfillment_channels=('MFN',))
        except Exception, e:
            raise Warning(str(e))
        self.create_sales_order(seller, [result], mws_obj)
        self._cr.commit()
        next_token = result.parsed.get('NextToken', {}).get('value')
        time.sleep(10)
        while next_token:
            try:
                result = mws_obj.list_orders_by_next_token(next_token)
            except Exception, e:
                raise Warning(str(e))
            next_token = result.parsed.get('NextToken', {}).get('value')
            self.create_sales_order(seller, [result], mws_obj)
            self._cr.commit()
            time.sleep(10)
        """We have create list of Dictwrapper now we create orders into system"""
        return True

    @api.multi
    def create_sales_order(self, seller, list_of_wrapper, mws_obj):
        # print 'create_sales_order。。。'
        # data = []
        # for result in list_of_wrapper:
        #     data.append(result.parsed)
        # with open('/Users/king/Desktop/sale_order.txt', 'w') as f:
        #     f.write(str(data))
        # return
        '''修改原方法，取消确认订单 Modified by ljp on 2017-12-27'''
        amazon_sale_line_obj = self.env['amazon.sale.order.line.ept']
        instance_obj = self.env['amazon.instance.ept']
        auto_work_flow_obj = self.env['sale.workflow.process.ept']
        amazon_product_obj = self.env['amazon.product.ept']
        stock_immediate_transfer_obj = self.env['stock.immediate.transfer']
        odoo_order_ids, shipped_orders, shipped_orders_ids = [], [], []
        for wrapper_obj in list_of_wrapper:
            orders = []
            if not isinstance(wrapper_obj.parsed.get('Orders', {}).get('Order', []), list):
                orders.append(wrapper_obj.parsed.get('Orders', {}).get('Order', {}))
            else:
                orders = wrapper_obj.parsed.get('Orders', {}).get('Order', [])
            for order in orders:
                state = order.get('OrderStatus', {}).get('value', '')
                print order.get('AmazonOrderId', {}).get('value', ''),state
                print order
                # if state == 'Unshipped':
                #     print order
                amazon_order_ref = order.get('AmazonOrderId', {}).get('value', False)

                if not amazon_order_ref:
                    continue

                existing_order = self.search([('amazon_reference', '=', amazon_order_ref)])
                if existing_order:
                    continue
                marketplace_id = order.get('MarketplaceId', {}).get('value', False)
                instance = instance_obj.search(
                    [('marketplace_id.market_place_id', '=', marketplace_id), ('seller_id', '=', seller.id)])
                if not instance:
                    continue
                instance = instance[0]

                fulfillment_channel = order.get('FulfillmentChannel', {}).get('value', False)
                if fulfillment_channel and fulfillment_channel == 'AFN' and not hasattr(instance, 'fba_warehouse_id'):
                    continue
                order_status = order.get('OrderStatus', {}).get('value', '')
                if order_status == 'Shipped':
                    shipped_orders.append(amazon_order_ref)
                partner_dict = self.create_or_update_partner(order, instance)
                # print 'partner_dict:',partner_dict

                try:
                    result = mws_obj.list_order_items(amazon_order_ref)
                    # print result.response.content
                    # print 'order line result.parsed:', result.parsed
                except Exception, e:
                    raise Warning(str(e))
                list_of_orderlines_wrapper = []
                list_of_orderlines_wrapper.append(result)
                next_token = result.parsed.get('NextToken', {}).get('value')
                while next_token:
                    try:
                        result = mws_obj.list_order_items_by_next_token(next_token)
                        # print 'order line result.parsed:', result.parsed
                    except Exception, e:
                        raise Warning(str(e))
                    next_token = result.parsed.get('NextToken', {}).get('value')
                    list_of_orderlines_wrapper.append(result)

                amazon_order = False
                skip_order = False
                message = ''
                log_message = ''
                log_action_type = 'skip_line'
                # print 'list_of_orderlines_wrapper',list_of_orderlines_wrapper
                for order_line_wrapper_obj in list_of_orderlines_wrapper:
                    order_lines = []
                    skip_order = False
                    if not isinstance(order_line_wrapper_obj.parsed.get('OrderItems', {}).get('OrderItem', []), list):
                        order_lines.append(order_line_wrapper_obj.parsed.get('OrderItems', {}).get('OrderItem', {}))
                    else:
                        order_lines = order_line_wrapper_obj.parsed.get('OrderItems', {}).get('OrderItem', [])

                    message = ''
                    log_message = ''
                    res_id = False
                    model_name = 'amazon.product.ept'
                    transaction_log_lines = []
                    for order_line in order_lines:
                        # print 'order_line:',order_line
                        seller_sku = order_line.get('SellerSKU', {}).get('value', False)
                        domain = [('instance_id', '=', instance.id)]
                        seller_sku and domain.append(('seller_sku', '=', seller_sku))
                        # print 'seller_sku',seller_sku
                        amazon_product = amazon_product_obj.search_amazon_product(instance.id, seller_sku, 'MFN')

                        # print 'amazon_product:',amazon_product
                        if not amazon_product:
                            erp_product = amazon_product_obj.search_product(seller_sku)
                            product_id = False
                            # print 'erp_product:',erp_product
                            # print 'seller.create_new_product:',seller.create_new_product
                            if erp_product:
                                product_id = erp_product.id
                                log_action_type = 'create'
                                message = 'Order is imported with creating new amazon product.'
                                log_message = 'Product %s created in amazon->Products->Products for %s instance. Product already exist in Odoo and Amazon.' % (
                                seller_sku, instance.name)
                            elif not seller.create_new_product:
                                skip_order = True
                                message = 'Order is not imported due to product not found issue.'
                                log_action_type = 'skip_line'
                                log_message = 'Product %s not found for %s instance' % (seller_sku, instance.name)
                            else:
                                log_action_type = 'create'
                                message = 'Order is imported with creating new odoo product.'
                                log_message = 'Product %s created in odoo for %s instance' % (seller_sku, instance.name)

                            if not skip_order:
                                sku = seller_sku or (erp_product and erp_product[0].default_code) or False
                                prod_vals = {
                                    'instance_id': instance.id,
                                    'product_asin': order_line.get('ASIN', {}).get('value', False),
                                    'seller_sku': sku,
                                    'type': erp_product and erp_product[0].type or 'product',
                                    'product_id': product_id,
                                    'purchase_ok': True,
                                    'sale_ok': True,
                                    'exported_to_amazon': True,
                                    'fulfillment_by': fulfillment_channel,
                                }
                                if not erp_product:
                                    prod_vals.update(
                                        {'name': order_line.get('Title', {}).get('value'), 'default_code': sku})

                                amazon_product = amazon_product_obj.create(prod_vals)
                                if not erp_product:
                                    res_id = amazon_product and amazon_product.product_id.id or False
                                    model_name = 'product.product'
                                else:
                                    res_id = amazon_product and amazon_product.id or False

                            log_line_vals = {
                                'model_id': self.env['amazon.transaction.log'].get_model_id(model_name),
                                'res_id': res_id or 0,
                                'log_type': 'not_found',
                                'action_type': log_action_type,
                                'not_found_value': seller_sku,
                                'user_id': self.env.uid,
                                'skip_record': skip_order,
                                'message': log_message,
                                'amazon_order_reference': amazon_order_ref,
                            }
                            transaction_log_lines.append((0, 0, log_line_vals))

                    # print 'skip_order,log_action_type:',skip_order,log_action_type
                    if not skip_order:
                        if not amazon_order:
                            order_vals = self.create_sales_order_vals(partner_dict, order, instance)
                            amazon_order = self.create(order_vals)
                            # print 'amazon_order',amazon_order.sale_order_id
                            if amazon_order and amazon_order.sale_order_id:
                                odoo_order_ids.append(amazon_order.sale_order_id.id)
                                if amazon_order.amazon_reference in shipped_orders:
                                    shipped_orders_ids.append(amazon_order.sale_order_id.id)
                        for order_line in order_lines:
                            amazon_sale_line_obj.create_sale_order_line(order_line, instance, amazon_order)
                        for line in amazon_order.sale_order_id.order_line:
                            line._onchange_shop_product()

                    if skip_order or log_action_type == 'create':
                        job_log_vals = {
                            'transaction_log_ids': transaction_log_lines,
                            'skip_process': skip_order,
                            'application': 'sales',
                            'operation_type': 'import',
                            'message': message,
                            'instance_id': instance.id
                        }
                        self.env['amazon.process.log.book'].create(job_log_vals)
