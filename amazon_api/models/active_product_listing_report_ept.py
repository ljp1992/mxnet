# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products
from odoo.exceptions import UserError
import time, datetime, base64, csv, threading, sys, copy
from StringIO import StringIO



class active_product_listing_report_ept(models.Model):
    _inherit = "active.product.listing.report.ept"

    progress_message = fields.Text(string=u'进度')

    get_data_start_time = fields.Datetime(string=u'获取产品数据开始时间')
    create_update_start_time = fields.Datetime(string=u'创建/更新产品开始时间')

    report_data = fields.Binary()
    product_data = fields.Binary()

    order_line = fields.One2many('down.sync.product.line', 'order_id')

    state_ljp = fields.Selection([
        ('draft', u'草稿'),
        ('getting_product_data', u'正在获取产品数据'),
        ('getting_product_data_done', u'获取产品数据完成'),
        ('create_update_product', u'正在创建/更新产品信息'),
        ('done', u'完成'),
        ('error', u'异常')], default='draft', string=u'状态')

    @api.multi
    def get_product_data(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': u'获取产品数据',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'sync.product.wizard',
            'views': [(self.env.ref('amazon_api.get_product_data_wizard').id, 'form')],
            'target': 'new',
        }

    @api.multi
    def get_product_data_start(self):
        '''获取产品数据'''
        self.write({
            'state_ljp': 'getting_product_data',
            'get_data_start_time': datetime.datetime.now(),
            'progress_message': u'开始获取产品数据...'})
        self._cr.commit()
        if not self.report_request_id:
            if not self.submit_request(): #提交request
                return
        if not self.report_id:
            if not self.get_request_status(): #获取request的处理状态
                return
        if not self.report_data:
            if not self.download_report(): #下载报告
                return
        all_asin = self.check_report() #检查报告
        # all_asin = set(list(all_asin)[:10])
        if not all_asin:
            return
        if not self.product_data:
            if not self.get_asin_info_from_amazon(all_asin): #根据asin获取产品详细数据
                return
        if not self.check_product_data():
            return
        self.write({
            'progress_message': u'获取产品数据完成! 共%d个产品,用时%s。' %
                                (len(all_asin), self.get_del_time(self.get_data_start_time)),
            'state_ljp': 'getting_product_data_done',
        })
        self._cr.commit()
        print 'over'


    def get_del_time(self, start_time):
        '''计算所用时间'''
        if type(start_time) is not datetime:
            start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        del_time = datetime.datetime.now() - start_time
        seconds = del_time.seconds
        info = ''
        h = int(seconds / 3600)
        m = int((seconds - (h * 3600)) / 60)
        s = int(seconds - (h * 3600) - (m * 60))
        if h:
            info += '%d小时' % h
        if m:
            info += '%d分' % m
        if s:
            info += '%s秒' % s
        if not info:
            info = '0.1秒'
        return info

    @api.multi
    def get_asin_info_from_amazon(self, all_asin):
        asin_count = len(all_asin)
        self.progress_message = u'正在获取产品数据... 共%d个产品，已获取%d个产品' % (asin_count, 0)
        self._cr.commit()
        instance = self.instance_id
        seller = instance.seller_id
        proxy_data = seller.get_proxy_server()
        mws_obj = Products(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                          account_id=str(seller.merchant_id),
                          region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                          proxies=proxy_data)
        marketplace_id =instance.market_place_id
        asin_info = {}
        asins = []
        i = 1
        for asin in all_asin:
            print i
            asins.append(asin)
            if len(asins) == 5:
                self.get_data_from_amazon(mws_obj, marketplace_id, asins, asin_info)  # 获取亚马逊数据
                asins = []
                if i % 10 == 0:
                    self.progress_message = u'正在获取产品数据... 共%d个产品，已获取%d个产品' % (asin_count, i)
                    self._cr.commit()
            if i == asin_count:
                if asins:
                    self.get_data_from_amazon(mws_obj, marketplace_id, asins, asin_info)  # 获取亚马逊数据
                break
            i += 1
        self.product_data = base64.b64encode(str(asin_info))
        return True

    @api.multi
    def get_data_from_amazon(self, mws_obj, marketplaceid, asins, asin_info):
        '''通过亚马逊接口获取数据 每秒可以处理五个asin，若没有获取到，等待1s再获取'''
        wait_time = 1
        max_wait_time = 600
        while True:
            try:
                result = mws_obj.get_matching_product_for_id(marketplaceid=marketplaceid, type='ASIN', ids=asins)
                break
            except Exception, e:
                if wait_time > max_wait_time:
                    self.add_get_data_log(u'%s %s' % (str(asins), str(e)))
                    return False
                else:
                    time.sleep(wait_time)
                    wait_time = wait_time * 2
                    continue
        data = result.parsed
        if type(data) is not list:
            data = [data]
        for item in data:
            asin = item.get('Id', {}).get('value', '')
            if not asin:
                self.add_get_data_log(u'返回的数据中没有找到asin %s' % str(item))
            status = item.get('status', {}).get('value')
            if status == 'Success':
                asin_info.update({asin: item})
            elif status == 'ClientError':
                self.add_get_data_log(u'没有找到asin为%s的产品' % asin)
            else:
                self.add_get_data_log(u'status异常 %s' % str(item))

    @api.multi
    def check_report(self):
        '''检查获取的报告'''
        self.progress_message = u'正在检查获取的报告...'
        self._cr.commit()
        all_asin = set()
        if not self.report_data:
            self.write({
                'progress_message': u'没有找到报告',
                'state_ljp': 'error'})
            self._cr.commit()
            return False
        amazon_encoding = self.instance_id.amazon_encodings
        imp_file = StringIO(base64.decodestring((self.report_data).decode(amazon_encoding)))
        reader = csv.DictReader(imp_file, delimiter='\t')
        for row in reader:
            asin = row.get('asin1', '')
            if not asin:
                self.add_get_data_log(u'报告中字段asin1没有值 %s' % str(row))
                continue
            if asin in all_asin:
                self.add_get_data_log(u'报告中存在重复的asin %s' % asin)
            else:
                all_asin.add(asin)
        if len(all_asin) == 0:
            self.add_get_data_log(u'下载的报告中没有产品！')
        self.progress_message = u'报告检查完毕'
        self._cr.commit()
        return all_asin

    @api.multi
    def download_report(self):
        '''下载report'''
        self.progress_message = u'正在下载报告...'
        self._cr.commit()
        if not self.report_id:
            self.write({
                'progress_message': u'下载报告失败！错误原因：Report ID为空！',
                'state_ljp': 'error'})
            self._cr.commit()
            return False
        instance = self.instance_id
        seller = instance.seller_id
        proxy_data = seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                          account_id=str(seller.merchant_id),
                          region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                          proxies=proxy_data)
        try:
            result = mws_obj.get_report(report_id=self.report_id)
        except Exception, e:
            self.write({
                'progress_message': u'下载报告失败！错误原因：%s' % str(e),
                'state_ljp': 'error'})
            self._cr.commit()
            return False
        data = result.parsed
        data = base64.b64encode(data)
        self.write({
            'progress_message': u'下载报告完成！',
            'report_data': data})
        self._cr.commit()
        return True

    @api.multi
    def get_request_status(self):
        '''获取请求处理状态'''
        self.progress_message = u'正在获取请求的处理状态...'
        self._cr.commit()
        if not self.report_request_id:
            self.write({
                'progress_message': u'获取请求的处理状态失败！错误原因：Report Request Id为空。',
                'state_ljp': 'error'})
            self._cr.commit()
            return False
        instance = self.instance_id
        seller = instance.seller_id
        proxy_data = seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                          account_id=str(seller.merchant_id),
                          region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                          proxies=proxy_data)
        wait_time = 20 #第一次等待时间
        max_wait_time = 600 #最长等待时间
        i = 0
        time.sleep(wait_time)
        while True:
            i += 1
            print '第%d次获取请求的处理状态' % i
            try:
                result = mws_obj.get_report_request_list(requestids=(self.report_request_id,))
            except Exception, e:
                time.sleep(wait_time)
                wait_time = wait_time * 2
                continue
            data = result.parsed
            report_id = data.get('ReportRequestInfo', {}).get('GeneratedReportId', {}).get('value', '')
            if report_id:
                print '请求处理完成！'
                break
            else:
                if wait_time > max_wait_time:
                    self.write({
                        'progress_message': u'获取请求的处理状态失败！错误原因：没有获取到Report ID',
                        'state_ljp': 'error'})
                    self._cr.commit()
                    return False
                else: #一般情况下 请求没有处理完的话会执行这一步
                    time.sleep(wait_time)
                    wait_time = wait_time * 2
        self.write({
            'report_id': report_id,
            'progress_message': u'亚马逊已完成该请求！'})
        self._cr.commit()
        return True

    @api.multi
    def submit_request(self):
        '''提交请求'''
        self.progress_message = u'提交请求中...'
        self._cr.commit()
        report_type = '_GET_MERCHANT_LISTINGS_DATA_'
        instance = self.instance_id
        seller = instance.seller_id
        proxy_data = seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                          account_id=str(seller.merchant_id),
                          region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                          proxies=proxy_data)

        marketplace_ids = tuple([instance.market_place_id])
        wait_time = 60
        max_wait_time = 600
        i = 0
        while True:
            i += 1
            print '第%d次提交请求' % i
            try:
                result = mws_obj.request_report(report_type, start_date=None, end_date=None, marketplaceids=marketplace_ids)
            except Exception, e:
                if wait_time > max_wait_time:
                    self.write({
                        'progress_message': u'提交请求失败！错误原因：%s' % str(e),
                        'state_ljp': 'error',})
                    self._cr.commit()
                    return False
                else:
                    time.sleep(wait_time)
                    wait_time = wait_time * 2
                    continue
            data = result.parsed

            report_request_id = data.get('ReportRequestInfo', {}).get('ReportRequestId', {}).get('value', '')
            if report_request_id:
                print 'data:', data
                self.report_request_id = report_request_id
                self.write({
                    'progress_message': u'提交请求成功！',
                    'report_request_id': report_request_id,})
                self._cr.commit()
                return True
            else:
                if wait_time > max_wait_time:
                    self.write({
                        'progress_message': u'提交请求失败！错误原因：没有获取到report_request_id',
                        'state_ljp': 'error',})
                    self._cr.commit()
                    return False
                else:
                    time.sleep(wait_time)
                    wait_time = wait_time * 2
                    continue

    @api.multi
    def add_get_data_log(self, message):
        self.write({'order_line': [(0, 0, {'message': message, 'type': 'get_data'})]})
        self._cr.commit()

    @api.multi
    def check_product_data(self):
        '''检查获取的产品详细数据'''
        self.progress_message = u'正在检查获取的产品数据...'
        self._cr.commit()
        parent_products = {}
        child_products = {}
        no_variation_products = {}
        data = base64.decodestring(self.product_data)
        try:
            asin_info = eval(data)
        except Exception, e:
            self.add_get_data_log(str(e))
        for (asin, val) in asin_info.items():
            if val.get('IdType', {}).get('value', '') != 'ASIN':
                self.add_get_data_log(u'IdType异常 %s' % str(val))
            Relationships = val.get('Products', {}).get('Product', {}).get('Relationships', {})
            if Relationships == {}:
                no_variation_products.update({asin: val})
            elif Relationships.has_key('VariationChild'):
                parent_products.update({asin: val})
            elif Relationships.has_key('VariationParent'):
                child_products.update({asin: val})
            else:
                self.add_get_data_log(u'Relationships异常 %s' % str(val))
        print '母产品，子产品，无变体产品数量为：',len(parent_products),len(child_products),len(no_variation_products)
        #检查母asin的子asin是否都存在
        for(asin, val) in parent_products.items():
            VariationChild = val.get('Products', {}).get('Product', {}).get('Relationships', {}).get('VariationChild', {})
            if type(VariationChild) is not list:
                VariationChild = [VariationChild]
            for child_val in VariationChild:
                child_asin = child_val.get('Identifiers', {}).get('MarketplaceASIN', {}).get('ASIN', {}).get('value', '')
                if child_asin and not child_products.has_key(child_asin):
                    self.add_get_data_log(u'店铺有asin为%s的父产品，但是没有asin为%s的子产品' % (asin, child_asin))
        #检查子asin的父asin是否都在
        for (asin, val) in child_products.items():
            VariationParent = val.get('Products', {}).get('Product', {}).get('Relationships', {}).get(
                'VariationParent',{})
            parent_asin = VariationParent.get('Identifiers', {}).get('MarketplaceASIN', {}).get('ASIN', {}).get(
                'value', '')
            if parent_asin and not parent_products.has_key(parent_asin):
                self.add_get_data_log(u'店铺有asin为%s的子产品,但是没有asin为%s的父产品' % (asin, parent_asin))
        self.progress_message = u'获取的产品数据已完成检查'
        self._cr.commit()
        return True

    @api.model
    def check_get_product_data_status(self):
        '''检查各个店铺同步产品获取数据过程中有没有超时（重启服务会造成超时）'''
        print 'check_get_product_data_status...'
        max_time = 7200
        records = self.search([('state_ljp', '=', 'getting_product_data')])
        for record in records:
            start_time = record.get_data_start_time
            if not start_time:
                continue
            start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            del_time = (datetime.datetime.now() - start_time).seconds
            if del_time > max_time:
                print '超时。。。', record.name
                record.write({
                    'state_ljp': 'error',
                    'progress_message': record.progress_message + u' 发生异常！可能是由于重启服务造成的。'
                })






    @api.multi
    def create_update_product(self):
        '''创建／更新产品'''
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': u'创建/更新产品',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'sync.product.wizard',
            'views': [(self.env.ref('amazon_api.create_update_product_wizard').id, 'form')],
            'target': 'new',
        }

    @api.multi
    def create_update_product_start(self):
        '''创建／更新产品'''
        self.ensure_one()
        if not self.report_data:
            self.write({'order_line': [(0, 0, {'type': 'create_update', 'message': u'字段report_data没有数据！！'})]})
            return
        if not self.product_data:
            self.write({'order_line': [(0, 0, {'type': 'create_update', 'message': u'字段product_data没有数据！'})]})
            return
        report_data = self.get_report_data()
        parent_products = {}
        child_products = {}
        no_variation_products = {}
        data = base64.decodestring(self.product_data)
        asin_info = eval(data)
        for (asin, val) in asin_info.items():
            Relationships = val.get('Products', {}).get('Product', {}).get('Relationships', {})
            if Relationships == {}:
                no_variation_products.update({asin: val})
            elif Relationships.has_key('VariationChild'):
                parent_products.update({asin: val})
            elif Relationships.has_key('VariationParent'):
                child_products.update({asin: val})
        create_count = 2 #创建个数
        i = 0
        #创建／更新有变体产品
        for (asin, val) in parent_products.items():
            if i == create_count:
                break
            i += 1
            if not report_data.has_key(asin):
                continue
            tmpl_val = self.get_tmpl_val(asin, asin_info, report_data)
            if tmpl_val:
                self.create_update_product_by_val(tmpl_val)
        #创建／更新无变体产品
        # for (asin, val) in no_variation_products.items():
        #     if i == create_count:
        #         break
        #     i += 1
        #     if not report_data.has_key(asin):
        #         continue
        #     tmpl_val = self.get_tmpl_val(asin, asin_info, report_data)
        #     self.create_update_product_by_val(tmpl_val)
        #     break

    def create_update_product_by_val(self, tmpl_val):
        '''创建／更新产品'''
        amazon_product_obj = self.env['amazon.product.ept']
        found_one_amzon_product = False
        for i in range(len(tmpl_val['product_variant_ids'])):
            product = tmpl_val['product_variant_ids'][i]
            if len(product['amazon_product_ids']) != 1:
                return
            seller_sku = product['amazon_product_ids'][0]['seller_sku']
            amazon_product = amazon_product_obj.search([('seller_sku', '=', seller_sku)])
            if amazon_product and len(amazon_product) == 1 and amazon_product.product_id:
                found_one_amzon_product = amazon_product
                product['amazon_product_ids'] = [(1, amazon_product.id, product['amazon_product_ids'][0])]
                tmpl_val['product_variant_ids'][i] = [1, amazon_product.product_id.id, product]
            else:
                product['amazon_product_ids'] = [(0, 0, product['amazon_product_ids'][0])]
                tmpl_val['product_variant_ids'][i] = [0, 0, product]
        if found_one_amzon_product: #update
            shop_tmplate = found_one_amzon_product.product_id.product_tmpl_id
            if shop_tmplate:
                return
                shop_tmplate.write(tmpl_val)
        else: #create
            partner = self.env['res.partner'].search([('amazon_instance_id', '=', self.instance_id.id)])
            if partner and partner.parent_id.id:
                supplier_partner_id = seller_partner_id = partner.parent_id.id
            else:
                return
            supplier_val = copy.deepcopy(tmpl_val)
            if supplier_val.has_key('product_variant_ids'):
                for supplier_product in supplier_val['product_variant_ids']:
                    if supplier_product[2].has_key('amazon_product_ids'):
                        supplier_product[2]['amazon_product_ids'] = []
            seller_val = copy.deepcopy(supplier_val)
            shop_val = copy.deepcopy(tmpl_val)

            supplier_val.update({
                'platform_published': True,
                'product_owner': supplier_partner_id,
                'master_product': False,
            })
            supplier_template = self.env['product.template'].create(supplier_val)
            print supplier_template

            seller_val.update({
                'platform_published': False,
                'product_owner': seller_partner_id,
                'master_product': supplier_template.id,
            })
            seller_tmplate = self.env['product.template'].create(seller_val)
            print seller_tmplate

            shop_val.update({
                'platform_published': False,
                'product_owner': partner.id,
                'master_product': supplier_template.id,
            })
            shop_tmplate = self.env['product.template'].create(shop_val)
            print shop_tmplate

    def get_tmpl_val(self, asin, product_data, report_data):
        '''获取并组织数据'''
        if not product_data.has_key(asin) or not report_data.has_key(asin):
            return {}
        report_val = report_data[asin]
        asin_val = product_data[asin]
        title = unicode(report_val.get('item-name',''),"utf-8",errors='ignore')
        description = unicode(report_val.get('item-description',''),"utf-8",errors='ignore')
        product_id_type = report_val.get('product-id-type', '')
        product_id = report_val.get('product-id', '')
        fulfillment_channel = report_val.get('fulfillment-channel', '')
        seller_sku = report_val.get('seller-sku', '')
        # print 'asin:', asin,seller_sku,fulfillment_channel
        price = report_val.get('price', 0)
        image_url = report_val.get('image-url', '')  # 后续添加图片下载
        # images = self.env['product.image'].search([('url', '=', image_url)])
        # if images and len(images) == 1:
        #     image = images[0]
        # else:
        #     image = self.env['product.image'].create({
        #         'name': brand_name,
        #     })
        ItemAttributes = asin_val.get('Products', {}).get('Product', {}).get('AttributeSets', {}).get('ItemAttributes', {})
        small_image = ItemAttributes.get('SmallImage', {}).get('URL', {}).get('value', '')
        brand_name = ItemAttributes.get('Brand', {}).get('value', '')
        brands = self.env['product.brand'].search([('name', '=', brand_name)])
        if brands and len(brands) == 1:
            brand = brands[0]
        else:
            brand = self.env['product.brand'].create({
                'name': brand_name,
            })
            self._cr.commit()
        Relationships = asin_val.get('Products', {}).get('Product', {}).get('Relationships', {})
        if Relationships == {}:
            tmpl_val = {
                'name': title,
                'product_brand_id': brand.id,
                'message_follower_ids': [],
                'product_variant_ids': [{
                    'default_code': seller_sku,
                    'variation_data': '',
                    'message_follower_ids': [],
                    'amazon_product_ids': [{
                        'title': title,
                        'instance_id': self.instance_id.id,
                        'long_description': description,
                        'product_asin': asin,
                        'standard_product_id_type': 'ASIN',
                        'seller_sku': seller_sku,
                        'fulfillment_by': self.get_fulfillment_type(fulfillment_channel),
                        'exported_to_amazon': True,
                        'condition': self.instance_id.condition or 'New',
                        'tax_code_id': self.instance_id.default_amazon_tax_code_id and
                                       self.instance_id.default_amazon_tax_code_id.id or False,
                    }]
                }],
            }
            barcode = self.get_barcode(product_id_type, product_id)
            tmpl_val['product_variant_ids'][0]['amazon_product_ids'][0].update(barcode)
            return tmpl_val
        elif Relationships.has_key('VariationChild'):
            tmpl_val = {
                'name': title,
                'product_brand_id': brand.id,
                'message_follower_ids': [],
                'product_variant_ids': [{
                    'default_code': seller_sku,
                    'variation_data': 'parent',
                    'message_follower_ids': [],
                    'amazon_product_ids': [{
                        'title': title,
                        'instance_id': self.instance_id.id,
                        'long_description': description,
                        'product_asin': asin,
                        'standard_product_id_type': 'ASIN',
                        'seller_sku': seller_sku,
                        'fulfillment_by': self.get_fulfillment_type(fulfillment_channel),
                        'exported_to_amazon': True,
                        'condition': self.instance_id.condition or 'New',
                        'tax_code_id': self.instance_id.default_amazon_tax_code_id and
                                       self.instance_id.default_amazon_tax_code_id.id or False,
                    }]
                }],
            }
            barcode = self.get_barcode(product_id_type, product_id)
            tmpl_val['product_variant_ids'][0]['amazon_product_ids'][0].update(barcode)
            VariationChild = Relationships['VariationChild']
            if type(VariationChild) is not list:
                VariationChild = [VariationChild]
            for child in VariationChild:
                child_asin = child.get('Identifiers', {}).get('MarketplaceASIN', {}).get('ASIN', {}).get('value', '')
                product_val = self.get_tmpl_val(child_asin, product_data, report_data)
                if product_val and product_val.get('variation_data') == 'child':
                    tmpl_val['product_variant_ids'].append(product_val)
            return tmpl_val
        elif Relationships.has_key('VariationParent'):
            product_val = {
                'default_code': seller_sku,
                'variation_data': 'child',
                'message_follower_ids': [],
                'amazon_product_ids': [{
                    'title': title,
                    'instance_id': self.instance_id.id,
                    'long_description': description,
                    'product_asin': asin,
                    'seller_sku': seller_sku,
                    'fulfillment_by': self.get_fulfillment_type(fulfillment_channel),
                    'exported_to_amazon': True,
                    'condition': self.instance_id.condition or 'New',
                    'tax_code_id': self.instance_id.default_amazon_tax_code_id and
                                   self.instance_id.default_amazon_tax_code_id.id or False,
                }]
            }
            barcode = self.get_barcode(product_id_type, product_id)
            product_val['amazon_product_ids'][0].update(barcode)
            return product_val
        else:
            return {}

    def get_barcode(self, product_id_type, product_id):
        val = {}
        if product_id_type == '1':
            val.update({
                'standard_product_id_type': 'ASIN',
                'product_asin': product_id,
            })
        elif product_id_type == '4':
            val.update({
                'standard_product_id_type': 'UPC',
                'product_upc': product_id,
            })
        return val

    def get_report_data(self):
        '''读取report'''
        report_data = {}
        amazon_encoding = self.instance_id.amazon_encodings
        imp_file = StringIO(base64.decodestring((self.report_data).decode(amazon_encoding)))
        reader = csv.DictReader(imp_file, delimiter='\t')
        for row in reader:
            asin = row.get('asin1')
            report_data.update({asin: row})
        return report_data

########################################## 测试 start ##########################################################




########################################### 测试 end ###########################################################