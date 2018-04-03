# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import xlrd,base64,datetime


class ImportInventoryWizard(models.TransientModel):
    _name = 'import.inventory.wizard'

    name = fields.Char(default=u'导入excel', string=u'')
    data = fields.Binary(string=u'文件')

    # 数据导入
    @api.multi
    def import_excel(self):
        if self.data:
            excel_obj = xlrd.open_workbook(file_contents=base64.decodestring(self.data))
            sheets = excel_obj.sheets()
            result_obj = self.env['stock.inventory']
            result_line_obj = self.env['stock.inventory.line']
            prod_obj = self.env['product.product']
            quant_obj = self.env['stock.quant']

            supplier = False
            threepl = False
            owner_id = False

            if self.user_has_groups('b2b_platform.group_qdoo_supplier_warehouse,b2b_platform.group_qdoo_supplier_manager'):
                supplier = True
                partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
                location = self.env['stock.location'].search([('location_id','=',self.env.ref('b2b_platform.stock_location_wh_suppliers').id),
                                      ('partner_id','=',self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id)],limit=1)
            elif self.user_has_groups('b2b_platform.group_b2b_3pl_operator'):
                threepl = True

            for sh in sheets:
                for row in range(1, sh.nrows):
                    prod = int(sh.cell(row, 0).value)
                    product = prod_obj.browse(prod)
                    owner_id = product.owner
                    qty = sh.cell(row, 5).value
                    date = fields.Date.today()

                    if supplier:
                        if product.owner != partner:
                            raise UserError(u'ID %s 对应的产品不属于本公司，不允许调整库存' % prod)
                    elif threepl:
                        location = self.env['stock.location'].search(
                            [('location_id.location_id', '=', self.env.ref('b2b_platform.stock_location_wh_3pl').id),
                             ('partner_id', '=', owner_id.id)])
                        if not location or len(location) > 1:
                            raise UserError(u'找不到第三方仓库中对应该供应商的唯一库位，请咨询平台管理员')

                    inventory = result_obj.create({'location_id': location.id,
                                                   'company_id': 1,
                                                   'state': 'draft',
                                                   'product_id': prod,
                                                   'name':  product.name,
                                                   'filter': 'product',
                                                   'accounting_date': date,
                                                   })
                    res_line = result_line_obj.create({'inventory_id': inventory.id,
                                                'product_qty': qty,
                                                'location_name': location.name,
                                                'location_id': location.id,
                                                'company_id': 1,
                                                'product_id': prod,
                                                'product_name':  product.name,
                                                'product_uom_id': 1,
                                                })
                    quant_rec = self.env['stock.quant'].sudo().search([('location_id', '=', location.id),
                                                                       ('product_id', '=', prod)])
                    theoretical_qty = sum([x.qty for x in quant_rec])
                    res_line.write({'theoretical_qty': theoretical_qty})
                    inventory.action_done()
            quants = quant_obj.sudo().search([('location_id', '=', location.id), ('owner_id', '=', False)])
            if quants and owner_id:
                quants.write({'owner_id':owner_id.id})

        return {'name': u'产品清单',
                'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'view_type': 'form',
                'view_mode': 'tree',
                # 'view_id': 'view_tree_b2b_distributor_product_list',
                # 'search_view_id': 'search_b2b_distributor_product_list',
                'domain': [('my_products', '=', True)],
                'context': {'create': False},
                }


