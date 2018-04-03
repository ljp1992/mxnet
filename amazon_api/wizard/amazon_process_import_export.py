# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import xlrd, base64, time
from datetime import datetime, timedelta
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports, Orders, Feeds, Products
from collections import defaultdict

class AmazonProcessImportExport(models.TransientModel):
    _inherit = 'amazon.process.import.export'

    # import_sale_order = fields.Boolean(default=True)

    start_date = fields.Datetime(string=u'起始日期', default=lambda self: self.get_start_date())
    end_date = fields.Datetime(string=u'终止日期', default=lambda self: self.get_end_date())

    @api.model
    def get_start_date(self):
        return datetime.now() - timedelta(days=1)

    @api.model
    def get_end_date(self):
        return datetime.now()

    @api.onchange('end_date')
    def onchange_end_date(self):
        end_date = datetime.strptime(self.end_date, "%Y-%m-%d %H:%M:%S")
        if end_date > datetime.now():
            raise UserError('终止日期不能大于当前日期！')

    # @api.multi
    # def download_amazon_sale_order(self):
    #     print 'download_amazon_sale_order'
    #     return

    @api.multi
    def import_export_processes(self):
        '''download sale_order new'''
        print 'download sale_order new'
        self.ensure_one()
        partner_obj = self.env['res.partner']
        country_obj = self.env['res.country']
        state_obj = self.env['res.country.state']
        currency_obj = self.env['res.currency']
        sale_order_obj = self.env['sale.order']
        product_obj = self.env['product.product']
        log_book_obj = self.env['amazon.process.log.book']
        orderstatus = ('Unshipped', 'PartiallyShipped', 'Shipped')
        created_after = datetime.strptime(self.start_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%SZ")
        created_before = datetime.strptime(self.end_date, "%Y-%m-%d %H:%M:%S") - timedelta(minutes=3)
        created_before = created_before.strftime("%Y-%m-%dT%H:%M:%SZ")
        for instance in self.instance_ids:
            seller = instance.seller_id
            marketplaceids = [instance.market_place_id]
            shop = self.env['res.partner'].search([('amazon_instance_id', '=', instance.id)], limit=1)
            proxy_data = seller.get_proxy_server()
            mws_obj = Orders(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                             account_id=str(seller.merchant_id),
                             region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                             proxies=proxy_data)
            try:
                result = mws_obj.list_orders(marketplaceids=marketplaceids, created_after=created_after,
                                             created_before=created_before, orderstatus=orderstatus,
                                             fulfillment_channels=('MFN',))
            except Exception, e:
                raise Warning(str(e))
            orders = result.parsed.get('Orders', {}).get('Order', {})
            if type(orders) is not list:
                orders = [orders]
            for order in orders:
                # print order
                origin_doc = order.get('AmazonOrderId', {}).get('value', '')
                sale_order_record = sale_order_obj.search([('origin_doc', '=', origin_doc)])
                if sale_order_record:
                    continue
                ShippingAddress = order.get('ShippingAddress', {})
                receiver = ShippingAddress.get('Name', {}).get('value', '')
                partner_shipping_id = partner_obj.search([('name', '=', receiver)])
                if not partner_shipping_id:
                    country_code = ShippingAddress.get('CountryCode', {}).get('value', '')
                    country = country_obj.search([('code', '=', country_code)])
                    if not country:
                        country = country_obj.create({'name': country_code, 'code': country_code})
                    state_code = ShippingAddress.get('StateOrRegion', {}).get('value', '')
                    state = state_obj.search([('code', '=', state_code), ('country_id', '=', country.id)])
                    if not state:
                        state = state_obj.create({'name': state_code, 'code': state_code, 'country_id': country.id})
                    city = ShippingAddress.get('City', {}).get('value', '')
                    phone = ShippingAddress.get('Phone', {}).get('value', '')
                    street = ShippingAddress.get('AddressLine1', {}).get('value', '')
                    zip = ShippingAddress.get('PostalCode', {}).get('value', '')
                    email = order.get('BuyerEmail', {}).get('value', '')
                    AddressType = ShippingAddress.get('AddressType', {}).get('value', '')
                    partner_shipping_val ={
                        'name': receiver,
                        'company_type': 'person',
                        'parent_id': False,
                        'country_id': country.id,
                        'state_id': state.id,
                        'city': city,
                        'phone': phone,
                        'street': street,
                        'zip': zip,
                        'email': email,
                    }
                    # print partner_shipping_val
                    partner_shipping_id = partner_obj.create(partner_shipping_val)
                date_order = order.get('PurchaseDate', {}).get('value', '')
                if date_order:
                    date_order = datetime.strptime(date_order, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
                else:
                    date_order = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                delivery_mode = order.get('FulfillmentChannel', {}).get('value', '')
                if delivery_mode not in ['MFN', 'FBA']:
                    delivery_mode = ''
                shipment_service_level_category = order.get('ShipmentServiceLevelCategory', {}).get('value', '')
                CurrencyCode = order.get('OrderTotal', {}).get('CurrencyCode', {}).get('value', '')
                currency_id_amazon = self.env['res.currency'].search([('name', '=', CurrencyCode)])
                if not currency_id_amazon:
                    raise UserError(u'币种%s系统不存在' % CurrencyCode)
                e_order_amount = float(order.get('OrderTotal', {}).get('Amount', {}).get('value', 0))
                order_val = {
                    'e_order_from': 'amazon',
                    'shop_id': shop.id,
                    'origin_doc': origin_doc,
                    'delivery_mode': delivery_mode,
                    'shipment_service_level_category': shipment_service_level_category,
                    'amazon_state': order.get('OrderStatus', {}).get('value', ''),
                    'currency_id_amazon': currency_id_amazon.id,
                    'e_order_amount': e_order_amount,
                    'partner_id': shop.parent_id.id,
                    'partner_shipping_id': partner_shipping_id.id,
                    'date_order': date_order,
                    'partner_invoice_id': shop.parent_id.id,
                    'company_id': instance.company_id.id,
                }
                # order_record = sale_order_obj.create(order_val)
                try:
                    result = mws_obj.list_order_items(origin_doc)
                except Exception, e:
                    raise Warning(str(e))
                OrderItem = result.parsed.get('OrderItems', {}).get('OrderItem', [])
                if type(OrderItem) is not list:
                    OrderItem = [OrderItem]
                order_lines = []
                exist_products = True
                for order_item in OrderItem:
                    seller_sku = order_item.get('SellerSKU', {}).get('value', '')
                    shop_product = product_obj.search([('default_code', '=', seller_sku)])
                    if not shop_product:
                        exist_products = False
                        break
                    CurrencyCode = order_item.get('ItemPrice', {}).get('CurrencyCode', {}).get('value', '')
                    shop_currency = currency_obj.search([('name', '=', CurrencyCode)])
                    if not shop_currency:
                        raise UserError(u'not found currency %s' % CurrencyCode)
                    shop_unit_price = float(order_item.get('ItemPrice', {}).get('Amount', {}).get('value', 0))
                    amazon_shipping_price = float(order_item.get('ShippingPrice', {}).get('Amount', {}).get('value', 0))
                    product_uom_qty = float(order_item.get('ProductInfo', {}).get('NumberOfItems', {}).get('value', 0))
                    need_procure = True
                    if shop_product.master_product.product_owner == (self.env.user.partner_id.parent_id or
                                                                         self.env.user.partner_id):
                        need_procure = False
                    order_line = {
                        'shop_product': shop_product.id,
                        'shop_currency': shop_currency.id,
                        'shop_unit_price': shop_unit_price,
                        'amazon_shipping_price': amazon_shipping_price,
                        'order_item_id': order_item.get('OrderItemId', {}).get('value', ''),
                        'product_id': shop_product.master_product.id or shop_product.id,
                        'product_uom_qty': product_uom_qty,
                        'price_unit': shop_product.master_product.lst_price,
                        'need_procure': need_procure,
                    }
                    order_lines.append([0, False, order_line])
                order_val.update({'order_line': order_lines})
                if exist_products:
                    sale_order_obj.create(order_val)
                else:
                    model = self.env['ir.model'].search([('model', '=', 'product.product')])
                    log_line = {
                        'amazon_order_reference': origin_doc,
                        'model_id': model.id,
                        'log_type': 'not_found',
                        'action_type': 'skip_line',
                        'user_id': self.env.user.id,
                        'skip_record': True,
                        'message': u'在店铺%s里没有找到产品%s' % (shop.name, seller_sku),
                    }
                    log_book_obj.create({
                        'skip_process': True,
                        'application': 'sales',
                        'operation_type': 'import',
                        'instance_id': instance.id,
                        'message': u'由于缺少产品%s，导致创建订单失败！' % seller_sku,
                        'transaction_log_ids': [(0, False, log_line)],
                    })

    def get_currency_symbol(self, order):
        '''返回币种'''
        CurrencyCode = order.get('OrderTotal', {}).get('CurrencyCode', {}).get('value', '')
        currency = self.env['res.currency'].search([('name', '=', CurrencyCode)])
        if not currency:
            raise UserError(u'币种%s系统不存在' % CurrencyCode)
        return currency

    # @api.multi
    # def import_export_processes(self):
    #     '''download sale_order old'''
    #     print 'download sale_order'
    #     amazon_product_obj = self.env['amazon.product.ept']
    #     sale_order_obj = self.env['amazon.sale.order.ept']
    #     saleorder_report_obj = self.env['sale.order.report.ept']
    #     seller_import_order_marketplaces = defaultdict(list)
    #     seller_export_order_marketplaces = defaultdict(list)
    #     result = True
    #     for instance in self.instance_ids:
    #         seller_import_order_marketplaces[instance.seller_id].append(instance.market_place_id)
    #
    #     created_after = datetime.strptime(self.start_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%SZ")
    #     created_before = datetime.strptime(self.end_date, "%Y-%m-%d %H:%M:%S") - timedelta(minutes=3)
    #     created_before = created_before.strftime("%Y-%m-%dT%H:%M:%SZ")
    #
    #     if seller_import_order_marketplaces:
    #         for seller, marketplaces in seller_import_order_marketplaces.iteritems():
    #             flag = False
    #             if seller.create_sale_order_from_flat_or_xml_report == 'api':
    #                 flag = True
    #                 if seller and marketplaces:
    #                     sale_order_obj.import_sales_order(seller, marketplaces, created_before, created_after)
    #
    #             flag and seller.write({'order_last_sync_on': datetime.now()})
    #
    #             action = self.env.ref('amazon_ept_v10.action_amazon_sale_order_report_ept')
    #             result = action and action.read()[0] or {}
    #             saleorder_report_obj = self.env['sale.order.report.ept']
    #             odoo_report_ids = saleorder_report_obj.search(
    #                 [('seller_id', '=', seller.id), ('state', 'in', ('_SUBMITTED_', '_IN_PROGRESS_'))])
    #             if odoo_report_ids and seller.create_sale_order_from_flat_or_xml_report != 'api':
    #                 if len(odoo_report_ids) > 1:
    #                     result['domain'] = "[('id','in',[" + ','.join(map(str, odoo_report_ids.ids)) + "])]"
    #                 else:
    #                     res = self.env.ref('amazon_ept_v10.amazon_sale_order_report_form_view_ept', False)
    #                     result['views'] = [(res and res.id or False, 'form')]
    #                     result['res_id'] = odoo_report_ids and odoo_report_ids[0].id or False
    #
    #     if seller_export_order_marketplaces:
    #         for seller, marketplaces in seller_export_order_marketplaces.iteritems():
    #             sale_order_obj.update_order_status(seller, marketplaces)
    #     return result

    @api.multi
    def download_sale_order(self):
        '''下载订单 test'''
        if self.start_date:
            db_import_time = time.strptime(self.start_date, "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S", db_import_time)
            start_date = time.strftime("%Y-%m-%dT%H:%M:%S",
                                       time.gmtime(time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
            start_date = str(start_date) + 'Z'
        else:
            start_date = False
        if self.end_date:
            db_import_time = datetime.strptime(self.end_date, "%Y-%m-%d %H:%M:%S") - timedelta(hours=5)
            db_import_time = db_import_time.strftime("%Y-%m-%dT%H:%M:%S")
            end_date = time.strftime("%Y-%m-%dT%H:%M:%S",
                                     time.gmtime(time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
            end_date = str(end_date) + 'Z'
        else:
            end_date = False

        vals = {}
        for instance in self.instance_ids:
            seller = instance.seller_id
            if vals.has_key(seller):
                vals[seller].append(instance.market_place_id)
            else:
                vals[seller] = [instance.market_place_id]
        for seller, marketplaces in vals.items():
            # print seller,marketplaces
            # data = self.get_sale_order_from_amazon(seller, marketplaces, end_date, start_date)
            with open('/Users/king/Desktop/sale_order.txt', 'r') as f:
                content = f.read()
                data = eval(content)
            #找出odoo中不存在的asin
            sku_info = {}
            for val in data:
                order = val['order']
                MarketplaceId = order.get('MarketplaceId', {}).get('value', '')
                if not sku_info.has_key(MarketplaceId):
                    sku_info[MarketplaceId] = []
                for line in val['order_line']:
                    OrderItem = line.get('OrderItems', {}).get('OrderItem', [])
                    if type(OrderItem) is dict:
                        OrderItem = [OrderItem]
                    for order_item in OrderItem:
                        SellerSKU = order_item.get('SellerSKU', {}).get('value', '')
                        asin = order_item.get('ASIN', {}).get('value', '')
                        product = self.env['amazon.product.ept'].search([
                            '|', ('product_asin', '=', asin),
                            ('default_code', '=', SellerSKU)
                        ])
                        if not product:
                            sku_info[MarketplaceId].append(SellerSKU)
            # print 'odoo中不存在的产品sku:',sku_info
            #根据sku获取产品信息
            proxy_data = seller.get_proxy_server()
            mws_obj = Products(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                               account_id=str(seller.merchant_id),
                               region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                               proxies=proxy_data)
            for (marketplaceid, skus) in sku_info.items():
                all_product_info = {}
                product_info = []
                sku_list = []
                for i in range(len(skus)):
                    print i
                    sku_list.append(skus[i])
                    if len(sku_list) == 5:
                        data = self.get_product_data_by_sku(mws_obj, marketplaceid, 'SellerSKU', sku_list)
                        product_info.extend(data)
                        sku_list = []
                    if i + 1 == len(skus) and sku_list:
                        data = self.get_product_data_by_sku(mws_obj, marketplaceid, 'SellerSKU', sku_list)
                        product_info.extend(data)
                # print 'product_info：',product_info
                # 找出母体
                parent_asins = []
                product_tmpls = []
                for pro_info in product_info:
                    Product = pro_info.get('Products', {}).get('Product', {})
                    Identifiers = Product.get('Identifiers', {})
                    asin = Identifiers.get('MarketplaceASIN', {}).get('ASIN', {}).get('value', '')
                    all_product_info.update({asin: pro_info})
                    Relationships = Product.get('Relationships', {})
                    if Relationships == {}:
                        product_tmpls.append(pro_info)
                    elif Relationships.has_key('VariationChild'):
                        product_tmpls.append(pro_info)
                    elif Relationships.has_key('VariationParent'):
                        parent_asin = Relationships.get('VariationParent', {}).get('Identifiers', {})\
                            .get('MarketplaceASIN', {}).get('ASIN', {}).get('value', '')
                        if parent_asin not in parent_asins:
                            parent_asins.append(parent_asin)
                # print 'product_tmpls,parent_asins：',product_tmpls,parent_asins
                #获取母体信息
                asin_list = []
                for i in range(len(parent_asins)):
                    asin = parent_asins[i]
                    asin_list.append(asin)
                    if len(asin_list) == 5:
                        data = self.get_product_data_by_sku(mws_obj, marketplaceid, 'ASIN', asin_list)
                        product_tmpls.extend(data)
                        asin_list = []
                    if i + 1 == len(parent_asins) and asin_list:
                        data = self.get_product_data_by_sku(mws_obj, marketplaceid, 'ASIN', asin_list)
                        product_tmpls.extend(data)
                # print 'product_tmpls：', product_tmpls
                # #获取子产品asin list
                # child_asin_list = []
                # for product_tmpl in product_tmpls:
                #     VariationChild = product_tmpl.get('Products', {}).get('Product', {}).get('Relationships', {})\
                #         .get('VariationChild', [])
                #     for child in VariationChild:
                #         child_asin = child.get('Identifiers', {}).get('MarketplaceASIN', {}).get('ASIN', {})\
                #             .get('value', '')
                #         if child_asin not in child_asin_list and not all_product_info.has_key(child_asin):
                #             child_asin_list.append(child_asin)
                # # print 'child_asin_list:',child_asin_list
                # #获取子产品信息
                # asin_list = []
                # for i in range(len(child_asin_list)):
                #     data = []
                #     asin = child_asin_list[i]
                #     asin_list.append(asin)
                #     if len(asin_list) == 5:
                #         data = self.get_product_data_by_sku(mws_obj, marketplaceid, 'ASIN', asin_list)
                #         asin_list = []
                #     if i + 1 == len(child_asin_list) and asin_list:
                #         data = self.get_product_data_by_sku(mws_obj, marketplaceid, 'ASIN', asin_list)
                #     if data:
                #         for child_pro_info in data:
                #             asin = child_pro_info.get('Products', {}).get('Product', {}).get('Identifiers', {})\
                #                 .get('MarketplaceASIN', {}).get('ASIN', {}).get('value', '')
                #             all_product_info.update({asin: child_pro_info})
                # print 'all_product_info:',all_product_info
                #创建产品
                self.create_product(product_tmpls, all_product_info)
        return

    def create_product(self, product_tmpls, all_product_info):
        '''创建产品'''
        attr_obj = self.env['product.attribute']
        attr_val_obj = self.env['product.attribute.value']
        # amazon_att_obj = self.env['amazon.attribute.ept']
        for template in product_tmpls:
            Products = template.get('Products', {})
            Product = Products.get('Product', {})
            Identifiers = Product.get('Identifiers', {})
            SalesRankings = Product.get('SalesRankings', {})
            AttributeSets = Product.get('AttributeSets', {})
            ItemAttributes = AttributeSets.get('ItemAttributes', {})
            Title = unicode(ItemAttributes.get('Title', {}).get('value', ''))
            Brand = ItemAttributes.get('Brand', {}).get('value', '')
            Manufacturer = ItemAttributes.get('Manufacturer', {}).get('value', '')
            SmallImage = ItemAttributes.get('URL', {}).get('value', '')
            Relationships = Product.get('Relationships', {})
            VariationChild = Relationships.get('VariationChild', [])
            product_variant_ids = []
            for child in VariationChild:
                child.pop('Identifiers')
                child.pop('MarketplaceId')
                for (attr_name, attr_val) in child.items():
                    attr_record = attr_obj.search([('name', '=', attr_name)], limit=1)
                    if not attr_record:
                        attr_record = attr_obj.create({'name': attr_name})
                    attr_val_record = attr_val_obj.search([('name', '=', attr_name)], limit=1)
                    if not attr_val_record:
                        attr_val_record = attr_val_obj.create({
                            'attribute_id': attr_val_record.id,
                            'name': attr_val.get('value', ''),
                        })

            val = {
                'name': Title,
                'type': 'product',
                'product_variant_ids': product_variant_ids,
            }

    @api.multi
    def get_product_data_by_sku(self, mws_obj, marketplaceid, id_type, ids):
        '''通过亚马逊接口获取产品数据 每秒可以处理五个产品，若没有获取到，等待1s再获取'''
        # print '获取产品信息中。。。',ids
        wait_time = 1
        max_wait_time = 600
        i = 0
        while True:
            i += 1
            # print '循环%d次' % i
            try:
                result = mws_obj.get_matching_product_for_id(marketplaceid, id_type, ids)
                break
            except Exception, e:
                if wait_time > max_wait_time:
                    return False
                else:
                    time.sleep(wait_time)
                    wait_time = wait_time * 2
                    continue
        data = result.parsed
        if type(data) is not list:
            data = [data]
        final_data = []
        for item in data:
            status = item.get('status', {}).get('value')
            if status == 'Success':
                final_data.append(item)
        # print '获取成功！'
        return final_data



    def get_sale_order_from_amazon(self, seller, marketplaceids=[], created_before='', created_after=''):
        '''从亚马逊获取订单数据'''
        data = []
        proxy_data = seller.get_proxy_server()
        orderstatus = ('Unshipped', 'PartiallyShipped', 'Shipped')
        mws_obj = Orders(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                         account_id=str(seller.merchant_id),
                         region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                         proxies=proxy_data)
        try:
            result = mws_obj.list_orders(marketplaceids=marketplaceids, created_after=created_after,
                                         created_before=created_before, orderstatus=orderstatus,
                                         fulfillment_channels=('MFN',))
        except Exception, e:
            raise Warning(str(e))
        data.append(result)
        next_token = result.parsed.get('NextToken', {}).get('value')
        # print 'next_token:', next_token
        while next_token:
            try:
                result = mws_obj.list_orders_by_next_token(next_token)
            except Exception, e:
                raise Warning(str(e))
            data.append(result)
            next_token = result.parsed.get('NextToken', {}).get('value')
            # print 'next_token while:', next_token

        vals = self.get_sale_order_line_from_amazon(data, mws_obj)
        print 'over'
        return True

    def get_sale_order_line_from_amazon(self, data, mws_obj):
        '''从亚马逊获取订单明细数据'''
        vals = []
        for item in data:
            orders = item.parsed.get('Orders', {}).get('Order', [])
            for order in orders:
                AmazonOrderId = order.get('AmazonOrderId', {}).get('value', '')
                try:
                    result = mws_obj.list_order_items(AmazonOrderId)
                    print result.parsed
                except Exception, e:
                    raise Warning(str(e))
                order_line = []
                order_line.append(result.parsed)
                next_token = result.parsed.get('NextToken', {}).get('value')
                print 'line next_token:',next_token
                while next_token:
                    try:
                        result = mws_obj.list_order_items_by_next_token(next_token)
                    except Exception, e:
                        raise Warning(str(e))
                    next_token = result.parsed.get('NextToken', {}).get('value')
                    order_line.append(result.parsed)
                vals.append({
                    'order': order,
                    'order_line': order_line,
                })
                # break

        with open('/Users/king/Desktop/sale_order.txt', 'w') as f:
            f.write(str(vals))

        return vals

################################################ 测试 ###############################################################

    def cs_time(self):
        amazon_product_obj = self.env['amazon.product.ept']
        sale_order_obj = self.env['amazon.sale.order.ept']
        saleorder_report_obj = self.env['sale.order.report.ept']
        seller_import_order_marketplaces = defaultdict(list)
        seller_export_order_marketplaces = defaultdict(list)
        result = True
        for instance in self.instance_ids:
            seller_import_order_marketplaces[instance.seller_id].append(instance.market_place_id)

        created_after = datetime.strptime(self.start_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%SZ")

        created_before = datetime.strptime(self.end_date, "%Y-%m-%d %H:%M:%S") - timedelta(minutes=3)
        created_before = created_before.strftime("%Y-%m-%dT%H:%M:%SZ")

        if seller_import_order_marketplaces:
            for (seller, marketplaces) in seller_import_order_marketplaces.items():
                proxy_data = seller.get_proxy_server()
                orderstatus = ('Unshipped', 'PartiallyShipped', 'Shipped')
                mws_obj = Orders(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                                 account_id=str(seller.merchant_id),
                                 region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                                 proxies=proxy_data)
                try:
                    print created_after, created_before
                    result = mws_obj.list_orders(marketplaceids=marketplaces, created_after=created_after,
                                                 created_before=created_before, orderstatus=orderstatus,
                                                 fulfillment_channels=('MFN',))
                except Exception, e:
                    print 'error:', e
                print result.parsed
                print 'over'
