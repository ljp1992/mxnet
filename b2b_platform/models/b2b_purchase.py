# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError

class b2b_purchase_order(models.Model):
    _inherit = 'purchase.order'

    distributor = fields.Many2one('res.partner', u'经销商', domain="[('qdoo_func','=','distributor')]")
    origin_so = fields.Many2one('sale.order', u'销售订单', ondelete='restrict')
    ship_picking_count = fields.Integer(u'发货单数', compute='_get_b2b_delivery_shippings')
    user_is_distributor = fields.Boolean(u'用户为经销商', compute='_if_is_distributor')

    @api.one
    def _if_is_distributor(self):
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        if self.distributor == partner:
            self.user_is_distributor = True

    @api.multi
    def write(self, vals):
        for user in self:
            if user.user_is_distributor:
                raise UserError(u'经销商不允许修改采购单')
        # 以下为原码
        result = super(b2b_purchase_order, self).write(vals)
        if vals.get('requisition_id'):
            self.message_post_with_view('mail.message_origin_link',
                                values={'self': self, 'origin': self.requisition_id, 'edit': True},
                                subtype_id=self.env['ir.model.data'].xmlid_to_res_id('mail.mt_note'))
        return result

    @api.depends('order_line.invoice_lines.invoice_id.state')
    def _compute_invoice(self):
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        for order in self:
            if order.distributor == partner:
                order.invoice_ids = False
                order.invoice_count = 0
            else:
                invoices = self.env['account.invoice']
                for line in order.order_line:
                    invoices |= line.invoice_lines.mapped('invoice_id')
                order.invoice_ids = invoices
                order.invoice_count = len(invoices)

    @api.one
    def _get_b2b_delivery_shippings(self):
        self.ship_picking_count = len(self.env['stock.picking'].search([('origin', '=', self.origin),
                                                                        ('owner_id', '=', self.partner_id.id)]))

    @api.multi
    def action_view_pickings(self):

        '''
                This function returns an action that display existing picking orders of given purchase order ids.
                When only one found, show the picking immediately.
                '''
        action = self.env.ref('stock.action_picking_tree')
        result = action.read()[0]

        # override the context to get rid of the default filtering on picking type
        result.pop('id', None)
        result['context'] = {}
        pickings = self.env['stock.picking'].search([('origin', '=', self.origin),
                                                     ('owner_id', '=', self.partner_id.id)])
        pick_ids = sum([order.ids for order in pickings], [])
        # choose the view_mode accordingly
        if len(pick_ids) > 1:
            result['domain'] = "[('id','in',[" + ','.join(map(str, pick_ids)) + "])]"
        elif len(pick_ids) == 1:
            res = self.env.ref('stock.view_picking_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = pick_ids and pick_ids[0] or False
        return result

    # def btn_confirm_and_supplier_wh(self):

        # picking_type_obj = self.env['stock.picking.type'].sudo()
        # dr_ship = picking_type_obj.search([('name', '=', u'直运')])
        # if not dr_ship:
        #     raise UserError(u'未找到直运的捡货类型，请咨询平台管理人员')
        # self.picking_type_id = dr_ship
        #
        # self.sudo().button_confirm()
        #
        # picking_obj = self.env['stock.picking'].sudo()
        # picking = picking_obj.search([('origin','=',self.name)],limit=1)
        # if not picking:
        #     raise UserError(u'未找到直运发货单，请咨询平台管理人员')
        #
        # warehouse_obj = self.env['stock.warehouse'].sudo()
        # warehouse = warehouse_obj.search([('partner_id','=',1)],limit=1)
        # if not warehouse:
        #     raise UserError(u'未找到平台仓库编码，请咨询平台管理人员')
        #
        # stock_loc_obj = self.env['stock.location'].sudo()
        # supp_loc_id = stock_loc_obj.search([('location_id.name','=',u'供应商库存'),
        #                                     ('partner_id','=',self.partner_id.id)],limit=1)
        # if not supp_loc_id:
        #     raise UserError(u'未找到供应商所属库位，请咨询平台管理人员')
        # cust_loc_id = stock_loc_obj.search([('usage', '=', 'customer')], limit=1)
        # if not cust_loc_id:
        #     raise UserError(u'未找到客户所属库位，请咨询平台管理人员')
        #
        # # picking_type_obj = self.env['stock.picking.type'].sudo()
        # # picking_type = picking_type_obj.search([('name', '=', u'发货'), ('warehouse_id', '=', warehouse.id)], limit=1)
        # # if not picking_type:
        # #     raise UserError(u'未找到捡货类型，请咨询平台管理人员')
        #
        # picking.write({'location_id':supp_loc_id.id,
        #                'picking_type_id':dr_ship.id,
        #                'location_dest_id':cust_loc_id.id,
        #                'ship_address':self.dest_address_id.id,
        #                'state':'draft',
        #                'move_type':'one',
        #                'carrier_id':self.origin_so.carrier_id.id,
        #               })
        # picking.pack_operation_product_ids.write({'location_id': supp_loc_id.id})
