from openerp import models,fields,api,_
import openerp.addons.decimal_precision as dp
from openerp.exceptions import Warning
from ..amazon_emipro_api.mws import Feeds
from openerp.api import Environment 
from tempfile import NamedTemporaryFile
import time
import base64

TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale_refund',
    'in_refund': 'purchase_refund',
}

class amazon_refund_order_lines(models.Model):
    _name="amazon.refund.order.lines"

    @api.multi
    def get_total(self):
        for record in self:
            total=0.0
            total=total+(record.order_line_amount * record.product_qty)
            total=total+record.order_line_tax

            total=total+record.shipping_charge
            total=total+record.shipping_tax
            
                        
            total=total+record.gift_wrap_charge
            total=total+record.gift_wrap_tax
            
            total=total+record.item_promotion_adjust
            total=total+record.shipping_promotion_adjust
            record.total_refund=total
            
    @api.multi
    @api.depends("amazon_refund_id.state")
    def get_state(self):
        for record in self:
            record.state=record.amazon_refund_id.state
    amazon_order_line_id=fields.Many2one("amazon.sale.order.line.ept","Sale Order Line")
    message=fields.Selection([('NoInventory','NoInventory'),
                              ('CustomerReturn','CustomerReturn'),
                              ('GeneralAdjustment','GeneralAdjustment'),
                              ('CouldNotShip','CouldNotShip'),
                              ('DifferentItem','DifferentItem'),
                              ('Abandoned','Abandoned'),
                              ('CustomerCancel','CustomerCancel'),
                              ('PriceError','PriceError'),
                              ],string="Message",default="CustomerReturn")

    amazon_refund_id=fields.Many2one("amazon.order.refund.ept","Refund Id")
    
    amazon_product_id=fields.Many2one("amazon.product.ept","Amazon Product")
    product_id=fields.Many2one("product.product","Odoo Product")
    
    product_qty=fields.Float("Product Qty",digits=dp.get_precision("Product UoS"))
    qty_canceled=fields.Float("Cancel Qty",digits=dp.get_precision("Product UoS"))

    price_subtotal=fields.Float("Order Line SubTotal",digits=dp.get_precision("Price Subtotal"))
    
    order_line_amount=fields.Float("Product Amount (Per Unit)",digits=dp.get_precision("Product Price"))
    order_line_tax=fields.Float("Order Amount Tax",digits=dp.get_precision("Product Price"))
    
    shipping_charge=fields.Float("Shipping Charge",digits=dp.get_precision("Product Price"))
    shipping_tax=fields.Float("Shipping Tax",digits=dp.get_precision("Product Price"))
        
    gift_wrap_charge=fields.Float("Gift Wrap Charge",digits=dp.get_precision("Product Price"))
    gift_wrap_tax=fields.Float("Gift Wrap Tax",Digits=dp.get_precision("Product Price"))
    
    item_promotion_adjust=fields.Float("Item Promotion Adjust",digits=(16,2))
    item_promotion_id=fields.Char("Item Promotion ID")
    
    shipping_promotion_adjust=fields.Float("Shipping Promotion Adjust",digits=(16,2))
    shipping_promotion_id=fields.Char("Shipping Promotion Id")

    total_refund=fields.Float("Total Refund",digits=dp.get_precision("Product Price"),compute="get_total")
    state=fields.Selection([('draft','Draft'),('validate','Validate'),('cancel','Cancel')],string="State",compute="get_state")    
    
class amazon_order_refund_ept(models.Model):
    _name="amazon.order.refund.ept"
    _inherit = ['mail.thread']
    _rec_name = 'order_id'
    _order="id desc"
    @api.multi
    def create_return_picking(self):
        with Environment.manage():
            env_thread1 = Environment(self._cr,self._uid,self._context)
            #stock_move_obj=env_thread1['stock.move']
            
            for picking in self.order_id.picking_ids:
                if picking.picking_type_code!='outgoing':
                    continue
                moves=[]
                move_qty={}
                for line in self.amazon_refund_line_ids:
                    if line.amazon_order_line_id.sale_order_line_id:
                        move=env_thread1['stock.move'].search([('procurement_id.sale_line_id','=',line.amazon_order_line_id.sale_order_line_id.id),('product_id','=',line.product_id.id),('picking_id','=',picking.id)])
                        moves.append(move.id)
                        move_qty.update({move.id:line.qty_canceled})
                    result=env_thread1['stock.return.picking'].with_context({'active_id':picking.id}).default_get(fields=['product_return_moves','move_dest_exists','location_id'])
                    
                    move_dest_exists=[]
                    product_return_moves=[]
                    if result.get('move_dest_exists',[]):
                        for exist_line in result.get('move_dest_exists',[]):
                            if exist_line.get('move_id') in moves:
                                move_dest_exists.append([0,0,exist_line])
                    if result.get('product_return_moves',[]):
                        for move_line in result.get('product_return_moves',[]): 
                            if len(move_line)==3:
                                if move_line[2].get('move_id') in moves:
                                    if move_qty.get(move_line[2].get('move_id'),0.0)>0.0:
                                        move_line[2].update({'quantity':move_qty.get(move_line.get('move_id'),0.0)})
                                    product_return_moves.append(move_line)
                    record=env_thread1['stock.return.picking'].create({'move_dest_exists':move_dest_exists,'product_return_moves':product_return_moves,'location_id':result.get('location_id')})
                    result=record.with_context({'active_id':picking.id}).create_returns()
        return True
            
    @api.multi
    def get_picking(self):
        for record in self:
            pickings = self.order_id.picking_ids
            record.picking_ids=pickings.ids
            auto_create_picking=record.order_id.instance_id.auto_create_return_picking
            record.auto_create_picking=auto_create_picking
    
    @api.one
    @api.depends('order_id')
    def _get_instance(self):
        if self.order_id:
            self.instance_id = self.order_id.instance_id and self.order_id.instance_id.id or False   
                 
    @api.model
    def _default_journal(self):
        inv_type = self._context.get('type', 'out_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', filter(None, map(TYPE2JOURNAL.get, inv_types))),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)

    order_id=fields.Many2one("amazon.sale.order.ept","Order Ref")
    instance_id = fields.Many2one('amazon.instance.ept',compute='_get_instance',string='Instance',store=True)
    company_id=fields.Many2one("res.company","Company")
    amazon_refund_line_ids=fields.One2many("amazon.refund.order.lines","amazon_refund_id","Refund Ids")
    state=fields.Selection([('draft','Draft'),('validate','Validate'),('cancel','Cancel')],string="State",default='draft')    
    journal_id=fields.Many2one('account.journal', 'Journal', help='You can select here the journal to use for the credit note that will be created. If you leave that field empty, it will use the same journal as the current invoice.',default=_default_journal)
    invoice_id=fields.Many2one("account.invoice","Refund")
    picking_ids=fields.One2many("stock.picking",compute="get_picking")
    auto_create_picking=fields.Boolean("Create Picking",compute="get_picking",store=False)
    date_ept=fields.Date("Date")
    


    @api.multi
    def create_flat_file(self):
        file_order_ship = NamedTemporaryFile(delete=False)
        file_order_ship.write("order-id\torder-item-id\tadjustment-reason-code\tcurrency\titem-price-adj\t")
        file_order_ship.write("item-tax-adj\tshipping-price-adj\tshipping-tax-adj\tgift-wrap-price-adj\t")
        file_order_ship.write("gift-wrap-tax-adj\titem-promotion-adj\titem-promotion-id\tship-promotion-adj\t")
        file_order_ship.write("ship-promotion-id\tquantity-cancelled\n")
        order_ref=self.order_id.amazon_reference
        currency=self.invoice_id and self.invoice_id.currency_id.name 
        if not currency:
            currency=self.company_id.currency_id.name
        for line in self.amazon_refund_line_ids:
            order_amount=line.order_line_amount * line.product_qty
            order_amount='%.2f'%order_amount
            order_line_tax='%.2f'%line.order_line_tax
            shipping_charge='%.2f'%line.shipping_charge
            shipping_tax='%.2f'%line.shipping_tax
            gift_wrap_charge='%.2f'%line.gift_wrap_charge
            gift_wrap_tax='%.2f'%line.gift_wrap_tax
            item_promotion_adjust='%.2f'%line.item_promotion_adjust
            shipping_promotion_adjust='%.2f'%line.shipping_promotion_adjust
            qty_canceled=int(line.qty_canceled)
            file_order_ship.write("%s\t%s\t%s\t%s\t%s\t"%(order_ref,line.amazon_order_line_id.amazon_order_item_id,line.message,currency,order_amount))
            file_order_ship.write("%s\t%s\t%s\t%s\t"%(order_line_tax,shipping_charge,shipping_tax,gift_wrap_charge))
            file_order_ship.write("%s\t%s\t%s\t%s\t"%(gift_wrap_tax,item_promotion_adjust,line.item_promotion_id or '',shipping_promotion_adjust))
            file_order_ship.write("%s\t%s"%(line.shipping_promotion_id or '',qty_canceled))
        file_order_ship.close()
        fl = file(file_order_ship.name, 'rb')
        data=fl.read()
        return data
    @api.multi
    def update_refund_in_amazon(self):
        self.ensure_one()
        instance=self.instance_id
        data=self.create_flat_file()        
        proxy_data=instance.seller_id.get_proxy_server()
        mws_obj=Feeds(access_key=str(instance.access_key),secret_key=str(instance.secret_key),account_id=str(instance.merchant_id),region=instance.country_id.amazon_marketplace_code or instance.country_id.code,proxies=proxy_data)
        try:
            mws_obj.submit_feed(data,'_POST_FLAT_FILE_PAYMENT_ADJUSTMENT_DATA_',marketplaceids=[instance.market_place_id],instance_id=instance.id)
        except Exception,e: 
            raise Warning(str(e))

        file_name = "refund_request_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
        attachment = self.env['ir.attachment'].create({
                                           'name': file_name,
                                           'datas': base64.encodestring(data),
                                           'datas_fname': file_name,
                                           'res_model': 'mail.compose.message',
                                           'type': 'binary'
                                         })
        self.message_post(body=_("<b>Return Created</b>"),attachment_ids=attachment.ids)    
        return True


    @api.multi
    def cancel_refund(self):
        self.write({'state':'cancel'})
        return True
    
    @api.multi
    def reset_to_draft(self):
        self.write({'state':'draft'})
        return True
    
    @api.multi
    def validate(self):
        for record in self:
            for line in record.amazon_refund_line_ids:
                message=False
                if line.total_refund<=0.0:
                    message="Invalid line for %s product"%(line.product_id.name)
                elif line.product_qty<=0.0:
                    message="Invalid Qty for %s product"%(line.product_id.name)
                elif line.product_qty>line.amazon_order_line_id.product_uom_qty:
                    message="Refund Qty is more then order line qty for %s product"%(line.product_id.name)
                elif (line.product_qty+line.qty_canceled) > line.amazon_order_line_id.product_uom_qty:
                    message="Refund & cancel qty are mismatch for %s product"%(line.product_id.name)
                if message:
                    raise Warning(message)
                
            if self.auto_create_picking:
                self.create_return_picking()
            if record.order_id.instance_id.auto_create_refund:
                self.create_refund()
            return True
            self.update_refund_in_amazon()
            record.write({'state':'validate'})

    @api.multi
    def create_refund(self):
        with Environment.manage():
            env_thread1 = Environment(self._cr,self._uid,self._context)
            #sale_order_obj=env_thread1['sale.order']
            for record in self:
                account_invoice_line_obj=env_thread1['account.invoice.line']
                journal_id=record.journal_id and record.journal_id.id
                inv_date=record.date_ept or fields.Date.context_today(self)
                payment_term=record.order_id.payment_term_id or False
                invoice_vals = {
                    'name': record.order_id.name or '',
                    'origin': account_invoice_line_obj.name,
                    'type': 'out_refund',
                    'reference': record.order_id.client_order_ref or record.order_id.name,
                    'account_id': record.order_id.partner_id.property_account_receivable_id.id,
                    'partner_id': record.order_id.partner_invoice_id.id,
                    'journal_id': journal_id,
                    'currency_id': record.order_id.pricelist_id.currency_id.id,
                    'comment': record.order_id.note,
                    'payment_term_id': payment_term.id,
                    'fiscal_position_id': record.order_id.fiscal_position_id.id or record.order_id.partner_id.property_account_position_id.id,
                    'company_id': record.company_id.id,
                    'amazon_instance_id':self.instance_id.id,
                    'user_id': record._uid or False,
                    'date_invoice':inv_date,
                    'team_id' : record.order_id.team_id and record.order_id.team_id.id,
                }
                invoice=env_thread1['account.invoice'].create(invoice_vals)
                record.write({'invoice_id':invoice.id})
                for line in record.amazon_refund_line_ids:
                    name=line.amazon_order_line_id.name
                    invoice_id=invoice.id
                    account=env_thread1['account.invoice.line'].get_invoice_line_account('out_refund', line.product_id,record.order_id.fiscal_position_id,record.company_id)                    
                    quantity=line.product_qty
                    price_unit = round(line.total_refund/ quantity,self.env['decimal.precision'].precision_get('Product Price'))
                    uom_id=line.amazon_order_line_id.sale_order_line_id.product_uom.id
                    
                    vals={
                          'product_id':line.product_id.id,
                          'name':name,
                          'invoice_id':invoice_id,
                          'account_id':account.id,
                          'price_unit':price_unit,
                          'quantity':quantity,
                          'uom_id':uom_id,
                          }
                    new_record=account_invoice_line_obj.new(vals)
                    new_record._onchange_product_id()
                    retval=new_record._convert_to_write({name: new_record[name] for name in new_record._cache})
                    retval.update({
                          'price_unit':price_unit,
                          'quantity':quantity,
                          'uom_id':uom_id,
                          })

                    account_invoice_line_obj.create(retval)                    
                return True    
    @api.onchange('order_id')
    def on_change_lines(self):
        with Environment.manage():
            env_thread1 = Environment(self._cr,self._uid,self._context)
            amazon_refund_lines_obj=env_thread1['amazon.refund.order.lines']
            for record in self:
                order=record.order_id
                vals={}
                new_amazon_retrun_lines=[]
                for line in order.ept_order_line:
                    if line.amazon_product_id:
                        info={
                              'amazon_order_line_id':line.id,
                              'amazon_product_id':line.amazon_product_id.id,
                              'product_id':line.amazon_product_id.product_id.id ,
                              'product_qty':line.product_uom_qty,
                              'price_subtotal':line.price_subtotal,
                              'order_line_amount':line.price_unit,
                              'order_line_tax':line.order_line_tax,
                              'item_promotion_adjust':line.promotion_discount,
                              'shipping_charge':line.shipping_charge_ept,
                              'shipping_tax':line.shipping_charge_tax,
                              'gift_wrap_charge':line.gift_wrapper_charge,
                              'gift_wrap_tax':line.gift_wrapper_tax,
                              'message':'CustomerReturn'
                              }
                        vals.update(info)
                        temp_refund_lines=amazon_refund_lines_obj.new(vals)
                        retvals = amazon_refund_lines_obj._convert_to_write(temp_refund_lines._cache)
                        new_amazon_retrun_lines.append(amazon_refund_lines_obj.create(retvals).id)
                        self.company_id=order.warehouse_id.company_id.id
                self.amazon_refund_line_ids=amazon_refund_lines_obj.browse(new_amazon_retrun_lines)