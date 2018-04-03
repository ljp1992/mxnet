# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
import json


import logging

_logger = logging.getLogger(__name__)

class DataCollection(http.Controller):

    #订单合计金额
    @http.route('/dv/ordersummary',auth='public')
    def ordersummary(self, **kw):
        sql = "select sum(price_subtotal) as value from sale_order_line"
        request.env.cr.execute(sql)  # 执行SQL语句
        dicts = request.env.cr.dictfetchall()  # 获取SQL的查询结果
        data_json=json.dumps(dicts)
        return data_json

    #店铺排名
    @http.route('/dv/shoprank',auth='public')
    def shoprank(self, **kw):
        sql = "select sum(round(a.amount_untaxed,2)) \
                as value ,c.name||'-'||b.name as content \
                from sale_order a  inner join res_partner \
                b on a.shop_id=b.id \
                inner join res_partner c on b.parent_id=c.id \
                where not shop_id is null \
                group by content order by value desc limit 5"
        request.env.cr.execute(sql)  # 执行SQL语句
        dicts = request.env.cr.dictfetchall()  # 获取SQL的查询结果
        data_json=json.dumps(dicts)
        return data_json

    #产品排名
    @http.route('/dv/productrank',auth='public')
    def productrank(self, **kw):
        sql = "select sum(a.price_total) as value,c.name as content \
                from sale_order_line a inner join product_product b \
                on a.product_id=b.id \
                inner join product_template c on b.product_tmpl_id=c.id \
                where c.type<>'service' group by c.name order by value desc limit 5"
        request.env.cr.execute(sql)  # 执行SQL语句
        dicts = request.env.cr.dictfetchall()  # 获取SQL的查询结果
        data_json=json.dumps(dicts)
        return data_json

    #当日合计金额
    @http.route('/dv/todayordersummary',auth='public')
    def todayordersummary(self, **kw):
        sql = "select COALESCE(sum(amount_untaxed),0) as value \
            from sale_order where date_order=current_date"
        request.env.cr.execute(sql)  # 执行SQL语句
        dicts = request.env.cr.dictfetchall()  # 获取SQL的查询结果
        data_json=json.dumps(dicts)
        return data_json

    #前日合计金额
    @http.route('/dv/yestodayordersummary',auth='public')
    def yestodayordersummary(self, **kw):
        sql = "select COALESCE(sum(amount_untaxed),0) as value \
            from sale_order where date_order=current_date"
        request.env.cr.execute(sql)  # 执行SQL语句
        dicts = request.env.cr.dictfetchall()  # 获取SQL的查询结果
        data_json=json.dumps(dicts)
        return data_json