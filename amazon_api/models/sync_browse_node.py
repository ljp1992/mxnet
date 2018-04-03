# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products
from ..amazon_api.report import MyReports
from odoo.exceptions import UserError
import time, datetime, base64, csv, threading, sys, copy
from StringIO import StringIO

# class MyReports(Reports):
#
#     def get_xml_browse_tree_data(self, start_date=None, end_date=None, RootNodesOnly=False, BrowseNodeId=False,
#                                  marketplaceids=()):
#         if RootNodesOnly:
#             RootNodesOnly = 'true'
#         data = {
#             'Action': 'RequestReport',
#             'ReportType': '_GET_XML_BROWSE_TREE_DATA_',
#             'StartDate': start_date,
#             'EndDate': end_date,
#             'RootNodesOnly': RootNodesOnly,
#             'BrowseNodeId': BrowseNodeId,
#         }
#         data.update(self.enumerate_param('MarketplaceIdList.Id.', marketplaceids))
#         result = self.make_request(data)
#         return result


class SyncBrowseNode(models.Model):
    _name = "sync.browse.node"

    name = fields.Char(string=u'更新browse node')
    report_request_id = fields.Char(string=u'ReportRequestId')
    generated_report_id = fields.Char(string=u'GeneratedReportId')

    submit_request_return_data = fields.Text(string=u'发出请求后亚马逊返回的数据')
    request_handle_status = fields.Text(string=u'请求处理状态')

    time_done = fields.Datetime(string=u'完成时间')

    data = fields.Binary(string=u'数据')

    instance_id = fields.Many2one('amazon.instance.ept', string=u'店铺')
    marketplace_id = fields.Many2one('amazon.marketplace.ept', related='instance_id.marketplace_id', store=False,
                                      string=u'Marketplace')

    # market_place_id = fields.Many2one('amazon.marketplace.ept', string=u'Marketplace')
    user_id = fields.Many2one('res.users', string=u'更新人')

    state = fields.Selection([
        ('draft',u'草稿'),
        ('in_submit', u'正在提交请求'),
        ('submitted', u'已提交请求'),
        ('in_progress', u'亚马逊正在处理请求'),
        ('progress_done', u'请求已处理完成'),
        ('downloading', u'正在下载数据'),
        ('download_done', u'数据下载完成'),
        ('updating', u'正在更新数据'),
        ('update_done', u'数据更新完成'),
        ('done', u'完成'),
    ], default='draft', string=u'状态')

    def update_browse_node(self):
        data = base64.decodestring(self.data)
        data = eval(data)
        print type(data)
        print data

    def download_data(self):
        if not self.generated_report_id:
            raise UserError(u'GeneratedReportId为空！')
        instance = self.instance_id
        seller = instance.seller_id
        proxy_data = seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                          account_id=str(seller.merchant_id),
                          region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                          proxies=proxy_data)
        result = mws_obj.get_report(report_id=self.generated_report_id)
        data = result.parsed
        print type(data)
        print data
        self.data = base64.b64encode(str(data))

    def get_request_status(self):
        if not self.report_request_id:
            raise UserError(u'ReportRequestId为空！')
        instance = self.instance_id
        seller = instance.seller_id
        proxy_data = seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                          account_id=str(seller.merchant_id),
                          region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                          proxies=proxy_data)
        result = mws_obj.get_report_request_list(requestids=(self.report_request_id,))
        data = result.parsed
        self.request_handle_status = result.response.content
        GeneratedReportId = data.get('ReportRequestInfo', {}).get('GeneratedReportId', {}).get('value', '')
        if GeneratedReportId:
            self.generated_report_id = GeneratedReportId

    def submit_request(self):
        # if self.report_request_id:
        #     raise UserError(u'请求已提交，无需再次提交！')
        instance = self.instance_id
        seller = instance.seller_id
        proxy_data = seller.get_proxy_server()
        mws_obj = MyReports(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                            account_id=str(seller.merchant_id),
                            region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                            proxies=proxy_data)
        marketplace_ids = tuple([instance.market_place_id])
        result = mws_obj.get_xml_browse_tree_data(start_date=None, end_date=None, RootNodesOnly=False,
                                                  BrowseNodeId=False, marketplaceids=marketplace_ids)
        data = result.parsed
        self.submit_request_return_data = result.response.content
        self.report_request_id = data.get('ReportRequestInfo',{}).get('ReportRequestId', {}).get('value', '')
