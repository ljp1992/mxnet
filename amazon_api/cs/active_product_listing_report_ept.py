# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products
from odoo.exceptions import UserError
import time, datetime, base64, csv, threading, sys, xlrd, xlwt
from StringIO import StringIO
from requests import request

marketplaceid = 'ATVPDKIKX0DER'

skus = ['18012626DAAB']
asins = ['B07921KSW5']
upc_list = ['6417207488069']

class active_product_listing_report_ept(models.Model):
    _inherit = "active.product.listing.report.ept"

    def print_product_info_by_asin(self):
        '''根据asin获取产品信息'''
        seller = self.instance_id.seller_id
        marketplaceid = self.instance_id.market_place_id
        mws_obj = Products(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                           account_id=str(seller.merchant_id),
                           region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                           proxies={})
        result = mws_obj.get_matching_product_for_id(marketplaceid=marketplaceid, type='ASIN', ids=asins)
        data = result.parsed
        if type(data) is not list:
            data = [data]
        for item in data:
            print item

    @api.multi
    def print_product_info_by_sku(self):
        '''根据sku获取产品信息'''
        seller = self.instance_id.seller_id
        marketplaceid = self.instance_id.market_place_id
        print seller.access_key, seller.secret_key, seller.merchant_id, seller.country_id.amazon_marketplace_code
        mws_obj = Products(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                           account_id=str(seller.merchant_id),
                           region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                           proxies={})
        # print seller.country_id.amazon_marketplace_code or seller.country_id.code,marketplaceid
        result = mws_obj.get_matching_product_for_id(marketplaceid=marketplaceid, type='SellerSKU', ids=skus)
        data = result.parsed
        if type(data) is not list:
            data = [data]
        for item in data:
            sku = item.get('Id', {}).get('value', '')
            asin = item.get('Products', {}).get('Product', {}).get('Identifiers', {}).get('MarketplaceASIN', {}).get(
                'ASIN', {}).get('value', '')
            print sku, asin
            # print item

    def print_info_by_upc(self):
        '''根据upc获取产品信息'''
        seller = self.instance_id.seller_id
        marketplaceid = self.instance_id.market_place_id
        mws_obj = Products(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                           account_id=str(seller.merchant_id),
                           region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                           proxies={})
        for upc in upc_list:
            result = mws_obj.list_matching_products(marketplaceid=marketplaceid, query=upc, contextid=None)
            data = result.parsed
            print data

    def get_active_upc(self):
        '''获取没有被占用的upc'''
        seller = self.instance_id.seller_id
        marketplaceid = self.instance_id.market_place_id
        mws_obj = Products(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                           account_id=str(seller.merchant_id),
                           region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                           proxies={})
        data = xlrd.open_workbook('/Users/king/Desktop/upc.xls')
        table = data.sheets()[0]
        workbook = xlwt.Workbook(encoding='utf8')
        valid_sheet = workbook.add_sheet('valid upc')
        invalid_sheet = workbook.add_sheet('invalid upc')
        max_time = 20
        wait_time = 1
        i = 0
        j = 0
        upcs = set()
        for row in range(table.nrows):
            upc = table.cell(row, 0).value
            if upc not in upcs:
                upcs.add(upc)
            else:
                continue
            if type(upc) is not unicode:
                raise UserError(u'type(upc) is not unicode!')
            upc = upc.replace(' ', '')
            while True:
                try:
                    result = mws_obj.list_matching_products(marketplaceid=marketplaceid, query=upc, contextid=None)
                    break
                except Exception, e:
                    if wait_time > max_time:
                        result = False
                        break
                    time.sleep(wait_time)
                    wait_time = wait_time * 2
            if result:
                data = result.parsed
                if data.get('Products') == {}:
                    print upc,' valid ',row
                    valid_sheet.write(i, 0, upc)
                    i += 1
                else:
                    print upc,' invalid ', row
                    invalid_sheet.write(j, 0, upc)
                    j += 1
        workbook.save('/Users/king/Desktop/valid_invalid_upc.xls')
        print 'over'

    # @api.multi
    # def print_product_price(self):
    #     '''获取产品价格'''
    #     seller = self.instance_id.seller_id
    #     marketplaceid = self.instance_id.market_place_id
    #     mws_obj = Products(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
    #                        account_id=str(seller.merchant_id),
    #                        region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
    #                        proxies={})
    #     result = mws_obj.get_my_price_for_asin(marketplaceid=marketplaceid, asins=asins, condition=None)
    #     data = result.parsed
    #     BuyingPrice = data.get('Product', {}).get('Offers', {}).get('Offer', {}).get('BuyingPrice', {})
    #     RegularPrice = data.get('Product', {}).get('Offers', {}).get('Offer', {}).get('RegularPrice', {})
    #     for (key, val) in BuyingPrice.items():
    #         print key, ':', val.get('Amount', {}).get('value', ''), val.get('CurrencyCode', {}).get('value', '')
    #     print 'RegularPrice:', RegularPrice.get('Amount', {}).get('value', ''), RegularPrice.get('CurrencyCode',
    #                                                                                              {}).get('value', '')

        # '''根据sku获取产品价格'''
        # seller = self.instance_id.seller_id
        # marketplaceid = self.instance_id.market_place_id
        # mws_obj = Products(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
        #                    account_id=str(seller.merchant_id),
        #                    region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
        #                    proxies={})
        # result = mws_obj.get_my_price_for_sku(marketplaceid=marketplaceid, skus=skus, condition=None)
        # data = result.parsed
        # BuyingPrice = data.get('Product', {}).get('Offers', {}).get('Offer', {}).get('BuyingPrice', {})
        # RegularPrice = data.get('Product', {}).get('Offers', {}).get('Offer', {}).get('RegularPrice', {})
        # for (key, val) in BuyingPrice.items():
        #     print key, ':', val.get('Amount', {}).get('value', ''), val.get('CurrencyCode', {}).get('value', '')
        # print 'RegularPrice:', RegularPrice.get('Amount', {}).get('value', ''), RegularPrice.get('CurrencyCode',
        #                                                                                          {}).get('value', '')




