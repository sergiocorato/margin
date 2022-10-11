# -*- coding: utf-8 -*-
##############################################################################
#
#    Tech Plus l10n it Sale
#    Copyright (C) Tech Plus Project (<http://www.techplus.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import netsvc
import operator
import cgi
import openerp.addons.decimal_precision as dp
import openerp.exceptions

from openerp.osv import fields
from openerp.osv.orm import Model
from openerp.tools.translate import _
from datetime import date, datetime
from transport_document import TRANSPORTATION_REASONS, TRASPORTATION_REASONS_DICT
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from product_to_return import RETURN_TRANSPORTATION_REASONS
from .delivery import CARRIAGE_TYPES

import logging
logger = logging.getLogger(__name__)

PICKING_TYPES = [
    ('in', 'Getting Goods'),
    ('out', 'Sending Goods'),
    ('internal', 'Internal'),
]

MARGIN_SCHEME_MODES = [
    ('new', 'New item'),
    ('new_no_vat', 'Margin scheme'),
    ('used', 'Used item'),
]

MARGIN_SCHEME_MODES_USED = [
    'used',
]

MARGIN_SCHEME_MODES_NOT_NEW = [
    'new_no_vat',
] + MARGIN_SCHEME_MODES_USED

DATE_EXPECTATIONS = [
    ('before_today', 'Before Today'),
    ('today', 'Today'),
    ('after_today', 'After Today'),
]


class stock_warehouse(Model):
    _inherit = "stock.warehouse"

    _columns = {
        'lot_lock_location_id': fields.many2one('stock.location', string='Lot Lock Location',
            domain=[('usage','=','internal')], help="An internal location where to stock locked lots."),
    }

class stock_location(Model):
    _inherit = "stock.location"

    def _get_is_lot_lock_location(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = bool(o.lot_lock_location_warehouse_ids)
        return res

    _columns = {
        'lot_lock_location_warehouse_ids': fields.one2many('stock.warehouse', 'lot_lock_location_id',
            string='Warehouses Using This Location as Lot Lock Location'),
        'is_lot_lock_location': fields.function(_get_is_lot_lock_location, type='boolean',
            string='Is Lot Lock Location'),
    }


class stock_production_lot(Model):
    _inherit = 'stock.production.lot'

    def _get_product_to_return_info(self, cr, uid, ids, name, args,context=None):
        logger.debug('--------> techplus_l10n_it_sale stock.production.lot: _get_product_to_return_info')
        res = {}
        product_to_return_obj = self.pool.get('product.to.return')
        fields = self.fields_get(cr, uid, allfields=['product_to_return_last_reason'], context=context)
        sel_reasons = dict(fields['product_to_return_last_reason']['selection'])
        for o in self.browse(cr, uid, ids, context=context):
            ptr_ids = product_to_return_obj.search(cr, uid, [
                    ('lot_id', '=', o.id),
                    '|',
                    ('unknown_fate_quantity', '>', 0.0),
                    ('return_planned_quantity', '>', 0.0),
                ], order='date desc', context=context)
            total_product_to_return_qty = 0.0
            product_to_return_info = ''
            reasons = {}
            last_reason = ''
            html_parts = ''
            for p in product_to_return_obj.browse(cr, uid, ptr_ids, context):
                if not last_reason:
                    last_reason = p.reason
                total_product_to_return_qty += p.unknown_fate_quantity
                reasons.setdefault(p.reason, 0.0)
                reasons[p.reason] += p.unknown_fate_quantity
            if reasons.keys():
                html_parts = ['<ul class="picking_contents">']
                for k in reasons.keys():
                    reason_name = k
                    reason_qty = reasons[k]
                    reason_map = dict(
                        product_to_return_obj._columns['reason'].selection)
                    reason_label = self.pool['ir.translation']._get_source(
                        cr, uid,
                        None, ('reason','selection'), context.get('lang'),
                        reason_map.get(reason_name))
                    html_parts.append('<li>%d x %s</li>' % (reason_qty,
                        cgi.escape(reason_label)))
                html_parts.append('</ul>')
            res[o.id] = {
                'active_product_to_return_ids': ptr_ids,
                'product_to_return_qty': total_product_to_return_qty,
                'product_to_return_info': ''.join(html_parts),
                'product_to_return_last_reason': last_reason,
                'product_to_return_last_reason_label': sel_reasons.get(last_reason, '?')
            }
        return res

    def _get_goods_loading_register_active_line_id(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = {
                'goods_loading_register_active_line_id': o.loaded_goods_loading_register_line_ids[0].id \
                    if o.loaded_goods_loading_register_line_ids else None,
                'goods_loading_register_code': o.loaded_goods_loading_register_line_ids[0].code \
                    if o.loaded_goods_loading_register_line_ids else '',
            }
        return res

    def _get_locked_quantity_info(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            locked_quantity = sum([lock.quantity for lock in o.active_lock_ids])
            res[o.id] = {
                'locked_quantity': locked_quantity,
                'unlocked_quantity': o.stock_available - locked_quantity,
            }
        return res

    _columns = {
        'order_line_ids': fields.one2many('sale.order.line', 'lot_id', string='Order Lines'),
        'purchase_mode': fields.selection(MARGIN_SCHEME_MODES, string='Purchase Mode', required=True, readonly=True),
        'goods_loading_register_active_line_id': fields.function(_get_goods_loading_register_active_line_id,
            type='many2one', multi='_get_goods_loading_register_active_line_id',
            obj='goods.loading.register.line', string='Goods Register Active Line'),
        'goods_loading_register_code': fields.function(_get_goods_loading_register_active_line_id,
        type='char', multi='_get_goods_loading_register_active_line_id', string='Goods Loading Register Code'),
        'goods_loading_register_line_ids': fields.one2many('goods.loading.register.line', 'lot_id',
            string='Goods Loading Register Lines'),
        'loaded_goods_loading_register_line_ids': fields.one2many('goods.loading.register.line', 'lot_id',
            string='Goods Loading Register Lines', domain=[('state', '=', 'loaded')]),
        'active_product_to_return_ids': fields.function(_get_product_to_return_info, arg=None,
            type='one2many', obj='product.to.return', multi='_get_product_to_return_info',
            string='Acrive Products To Return'),
        'product_to_return_qty': fields.function(_get_product_to_return_info, type='float',
            multi='_get_product_to_return_info', string='Product To Return Quantity'),
        'product_to_return_info': fields.function(_get_product_to_return_info, type='text',
            multi='_get_product_to_return_info', string='Product To Return Description'),
        'product_to_return_last_reason': fields.function(_get_product_to_return_info, type='selection',
            multi='_get_product_to_return_info', selection=TRANSPORTATION_REASONS,
            string='Product To Return Last Reason'),
        'product_to_return_last_reason_label': fields.function(_get_product_to_return_info, type='char',
            multi='_get_product_to_return_info', string='Product To Return Last Reason Label'),
        'active_lock_ids': fields.one2many('stock.production.lot.lock', 'lot_id', string='Locks',
            domain=[('state','=','active')], readonly=True),
        'locked_quantity': fields.function(_get_locked_quantity_info, type='float', multi="_get_locked_quantity_info",
            digits_compute=dp.get_precision('Product Unit of Measure'), string='Locked Quantity'),
        'unlocked_quantity': fields.function(_get_locked_quantity_info, type='float', multi="_get_locked_quantity_info",
            digits_compute=dp.get_precision('Product Unit of Measure'), string='Unlocked Quantity'),
    }

    _defaults = {
        'purchase_mode': 'new',
    }

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for lot in self.browse(cr, uid, ids, context):
            if lot.move_ids and 'product_id' in vals and lot.product_id.id != vals['product_id']:
                raise openerp.exceptions.Warning(
                    _('You are trying to change the product for a serial number that has been used in a stock move!'))
        super(stock_production_lot, self).write(cr, uid, ids, vals, context)
        return True


class stock_picking(Model):
    _inherit = ["stock.picking", "shallow.copy.mixin"]
    _name = 'stock.picking'

    def _get_transport_document_ref_prefix(self):
        return ''

    def _get_shipping_invoice_ref_prefix(self):
        return ''

    def _get_shipping_document_ref(self, cr, uid, ids, name, args, context=None):
        logger.debug('--------> techplus_l10n_it_sale stock.picking: _get_shipping_document_ref')
        res = {}
        td_prefix = self._get_transport_document_ref_prefix()
        si_prefix = self._get_shipping_invoice_ref_prefix()
        for o in self.browse(cr, uid, ids, context=context):
            if o.transport_document_id:
                res[o.id] = '%s%s' % (td_prefix,
                    o.transport_document_id.name or '?')
            elif o.shipping_invoice_id:
                res[o.id] = '%s%s' % (si_prefix,
                    o.shipping_invoice_id.number or '?')
            else:
                res[o.id] = None
        return res

    def _get_stock_picking_ids_by_transport_document_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale stock.picking: _get_stock_picking_ids_by_transport_document_ids')
        return self.pool.get('stock.picking').search(cr, uid, [
                ('transport_document_id', 'in', ids),
            ], context=context)

    def _get_stock_picking_ids_by_shipping_invoice_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale stock.picking: _get_stock_picking_ids_by_shipping_invoice_ids')
        return self.pool.get('stock.picking').search(cr, uid, [
                ('shipping_invoice_id', 'in', ids),
            ], context=context)

    def _get_goods_sale_value(self, cr, uid, ids, name, args, context=None):
        res = {}
        sale_line_obj = self.pool.get('sale.order.line')
        for o in self.browse(cr, uid, ids, context=context):
            amount = 0.0
            dropped_lines = 0
            for move in o.move_lines:
                if move.sale_line_id:
                    discount = 1.0 - (move.sale_line_id.discount / 100.0)
                    price = move.sale_line_id.price_unit
                    amount += move.product_qty * price * discount
                else:
                    dropped_lines += 1
            res[o.id] = {
                'goods_value': amount,
                'goods_dropped_value_lines': dropped_lines,
            }
        return res

    def _get_partner_to_invoice(self, cr, uid, picking, context=None):
        """ Gets the partner that will be invoiced
            Note that this function is inherited in the sale and purchase modules
            @param picking: object of the picking for which we are selecting the partner to invoice
            @return: object of the partner to invoice
        """
        if picking.customer_id:
            return picking.customer_id.id
        return picking.partner_id and picking.partner_id.id

    def _get_contents_html(self, cr, uid, ids, name, args, context=None):
        logger.debug('--------> techplus_l10n_it_sale stock.picking: _get_contents_html')
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            html_parts = ['<ul class="picking_contents">']
            for l in o.move_lines:
                pname = l.product_id.name_get()[0][1]
                pqty = l.product_qty
                #pname = l.product_id.name if l.product_id else ''
                html_parts.append('<li>%d x %s</li>' % (pqty, cgi.escape(pname)))
            html_parts.append('</ul>')
            res[o.id] = ''.join(html_parts)
        return res

    def _get_picking_ids_by_stock_move_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale stock.picking: _get_picking_ids_by_stock_move_ids')
        res = {}
        move_ids = self.pool.get('stock.move').browse(cr, uid, ids,
            context=context)
        for m in move_ids:
            if m.picking_id:
                res[m.picking_id.id] = True
        return res.keys()

    def _prepare_shipping_invoice_line(self, cr, uid, picking, invoice,
        context=None):
        res = super(stock_picking, self)._prepare_shipping_invoice_line(cr, uid,
            picking, invoice, context)
        return res if res and res.get('price_unit', 0.0) > 0.0 else None

    def _get_carriage_condition(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            condition = o.picking_carriage_condition_id or o.sale_carriage_condition_id
            res[o.id] = condition.id if condition else None
        return res

    def _set_carriage_condition(self, cr, uid, id, name, value, args, context=None):
        return self.write(cr, uid, [id], {
                'picking_carriage_condition_id': value,
            }, context=context)

    def _get_date_info(self, cr, uid, ids, name, args, context=None):
        res = {}
        today = date.today().strftime(DEFAULT_SERVER_DATE_FORMAT)
        for o in self.browse(cr, uid, ids, context=context):
            expectation = 'today'
            picking_date = o.min_date[:10] if o.min_date else False
            if today < picking_date:
                expectation = 'after_today'
            elif today > picking_date:
                expectation = 'before_today'
            res[o.id] = {
                'date_expectation': expectation,
            }
        return res

    def _get_invoice_ready(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            result = False
            if o.invoice_state == '2binvoiced' and not o.invoice_id and o.type == 'out':
                result = True
                # for move in o.move_lines:
                #     if not move.product_id.no_lot_required and not move.prodlot_id:
                #         result = False
                #         break
            res[o.id] = result
        return res

    def _search_invoice_ready(self, cr, uid, obj, name, args, domain=None, context=None):
        assert(not len(args) or not isinstance(args[0],tuple) or
            not len(args[0]) == 3 or not args[0][1].lower() != '=')
        cr.execute("""SELECT id FROM stock_picking AS sp
                      WHERE sp.invoice_state = '2binvoiced' AND sp.invoice_id IS NULL AND
                      sp.type = 'out' AND sp.state IN ('assigned', 'done')""")
        picking_ids = [x[0] for x in cr.fetchall()]
        if args[0][2] == True:
            return [('id', 'in', picking_ids)]
        return [('id', 'not in', picking_ids)]

    _columns = {
        'invoice_ready': fields.function(_get_invoice_ready, type='boolean', fnct_search=_search_invoice_ready,
            string='Ready For Invoicing'),
        'date_expectation': fields.function(_get_date_info, type='selection', multi='_get_date_info',
            string='Date Expectation', selection=DATE_EXPECTATIONS),
        'carriage_type': fields.related('carrier_id', 'type', type='selection', selection=CARRIAGE_TYPES,
            string='Carriage Type', readonly=True),
        'sale_carriage_condition_id': fields.related('sale_id', 'carriage_condition_id', type='many2one',
            relation='carriage.condition', string='Carriage Condition', readonly=True),
        'carriage_condition_id': fields.function(_get_carriage_condition, fnct_inv=_set_carriage_condition,
            type='many2one', obj='carriage.condition', string='Carriage Condition'),
        'picking_carriage_condition_id': fields.many2one('carriage.condition',
            'Picking Carriage condition', track_visibility='onchange'),
        'contents_html': fields.function(_get_contents_html, type='text',
            string='Contents', store = {
                'stock.move':
                    (_get_picking_ids_by_stock_move_ids,
                        ['name', 'product_qty', 'picking_id'], 50),
                # 'stock.picking':
                #     (lambda self, cr, uid, ids, context: ids,
                #         ['move_lines'], 10),
            }),
        'partner_delivery_notes': fields.related('partner_id', 'delivery_notes',
            string='Delivery Notes', type='text', readonly=True),
        'partner_id': fields.many2one('res.partner', 'Partner', readonly=False,
            states={'cancel':[('readonly',True)]}),
        'customer_id': fields.many2one('res.partner', 'Cessionary',
            states={'cancel':[('readonly',True)]}),
        'goods_value': fields.function(_get_goods_sale_value, type='float',
            string='Value of goods', readonly=True,
            multi='_get_goods_sale_value'),
        'goods_dropped_value_lines': fields.function(_get_goods_sale_value,
            type='integer', string='Lines with no sale order',
            multi='_get_goods_sale_value', readonly=True,
            digits_compute=dp.get_precision('Account')),
        'currency_id': fields.related('sale_id', 'pricelist_id', 'currency_id',
            type='many2one', relation='res.currency', string='Currency',
            readonly=True),

        # NOTA
        # Sul ritiro a mano il campo vettore deve essere vuoto!
        # Se il ritiro viene fatto da parte di un terzo su delega, viene
        # richiesta l'anagrafica del partner e deve essere
        # presente una delega (scansione firmata ed allegata)

        # TODELETE: BEGIN
        # 'carriage_condition_id': fields.many2one('carriage.condition',
        #     'Carriage condition'),
        'goods_description_id': fields.many2one('goods.description',
            'Description of goods'),
        'transportation_reason_id': fields.many2one('transportation.reason',
            'Reason for transportation'),
        'transportation_id': fields.many2one('transportation',
            'Transportation organized by'),
        'manual_weight': fields.float('Weight', digits=(10,2)),
        'manual_weight_net': fields.float('Net Weight', digits=(10,2)),
        'manual_volume': fields.float('Volume (m³)', digits=(10,2)),
        'date_receipt': fields.datetime('Receipt Date'),
        # TODELETE: END
        'ddt_number': fields.char('DDT', size=64, track_visibility='onchange'),
        'ddt_date': fields.date('DDT date'),
        'shipping_notes': fields.text('Shipping Notes'),
        'transport_document_id': fields.many2one('transport.document',
            string='Transport Document', ondelete='restrict'),
        'shipping_invoice_id': fields.many2one('account.invoice',
            string='Shipping Invoice'),
        'shipping_document_ref': fields.function(_get_shipping_document_ref,
            type='char', size=120, string='Shipping Document',
            readonly=True, store = {
                'stock.picking':
                    (lambda self, cr, uid, ids, context: ids,
                        ['transport_document_id', 'shipping_invoice_id'], 10),
                'transport.document':
                    (_get_stock_picking_ids_by_transport_document_ids, ['name'], 10),
                'account.invoice':
                    (_get_stock_picking_ids_by_shipping_invoice_ids, ['internal_number'], 10),
            }),
    }

    _defaults = {
        'number_of_packages': 1,
    }


    def on_change_partner_id(self, cr, uid, ids, partner_id, context=None):
        if partner_id:
            partner = self.pool.get('res.partner').read(cr, uid,
                partner_id, ['delivery_notes'], context=context)

            return {'value': {
                'partner_delivery_notes': partner['delivery_notes'],
            }}
        return {'value': {
            'partner_delivery_notes': None,
        }}


    def action_assign(self, cr, uid, ids, *args):
        """ Changes state of picking to available if all moves are confirmed.
        @return: True
        """
        wf_service = netsvc.LocalService("workflow")
        for pick in self.browse(cr, uid, ids):
            if pick.state == 'draft':
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_confirm', cr)
            move_ids = [x.id for x in pick.move_lines if x.state == 'confirmed']
            if not move_ids:
                if all([x.state == 'assigned' and
                        (x.lot_lock_id and not x.product_id.no_lot_required)
                        for x in pick.move_lines]):
                    pick.force_assign(cr, uid, pick.id)
                else:
                    raise openerp.exceptions.Warning(_('No confirmed moves found!'))
            self.pool.get('stock.move').action_assign(cr, uid, move_ids, raise_exceptions=True)
        return True



    # PICKING OVERRIDE - OLD VERSION
    # def action_assign(self, cr, uid, ids, *args, **kwargs):
    #     lock_obj = self.pool.get('stock.production.lot.lock')
    #     warehouse_id = self.pool.get('stock.warehouse').search(cr, uid, [])
    #     warehouse_id = warehouse_id[0] if warehouse_id else None
    #     reason = _('Stock Picking Out Product Assignment')
    #     wf_service = netsvc.LocalService("workflow")
    #     for pick in self.browse(cr, uid, ids):
    #         if pick.state == 'draft':
    #             wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_confirm', cr)
    #         move_ids = [x.id for x in pick.move_lines if x.state == 'confirmed']
    #         # if not move_ids:
    #         #     raise osv.except_osv(_('Warning!'),_('Not enough stock, unable to reserve the products.'))
    #         if pick.type == 'out':
    #             for line in pick.move_lines:
    #                 if line.prodlot_id:
    #                     if not line.lot_lock_id:
    #                         lock_id = lock_obj.create(cr, uid, {
    #                             'lot_id': line.prodlot_id.id,
    #                             'sale_order_line_id': line.picking_id.sale_line_id.id \
    #                                 if line.picking_id and line.picking_id.sale_line_id else None,
    #                             'stock_move_id': line.id,
    #                             'begin_time': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
    #                             'expiration_time': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
    #                             'lock_reason': reason,
    #                             'warehouse_id': warehouse_id,
    #                             'quantity': line.product_qty,
    #                             })
    #                         lock_obj.set_active(cr, uid, [lock_id], reason)
    #                         line.refresh()
    #                     line.write({
    #                         'location_id': line.lot_lock_id.lock_move_id.location_dest_id.id,
    #                         # le stock.move.line in stato 'assigned' non vengono processate dal metodo check_assign()
    #                         'state': 'assigned',
    #                     })
    #         if move_ids:
    #             self.pool.get('stock.move').action_assign(cr, uid, move_ids)
    #         wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
    #     return True

    def action_invoice_create(self, cr, uid, ids, journal_id=False, group=False, type='out_invoice', context=None):
        if context and context.get('active_model') == 'transport.document':
            doc_obj = self.pool.get('transport.document')
            pids = []
            for doc in doc_obj.browse(cr, uid, ids, context):
                pids += [p.id for p in doc.picking_ids]
            # return super(stock_picking, self).action_invoice_create(cr, uid, list(set(pids)), journal_id=journal_id,
            #     group=group, type=type, context=context)
            ids = list(set(pids))
        res = super(stock_picking, self).action_invoice_create(cr, uid, ids, journal_id=journal_id, group=group,
            type=type, context=context)
        if type not in ('out_invoice', 'out_refund'):
            return res
        invoice_obj = self.pool.get('account.invoice')
        for picking in self.pool.get('stock.picking.out').browse(cr, uid, res.keys(), context):
            invoice_id = res[picking.id]
            invoice_obj.replace_lines_with_margin_lines(cr, uid, invoice_id, context)
            picking.write({'invoice_id': invoice_id, 'invoice_state': 'invoiced'})
        return res

    def action_done(self, cr, uid, ids, context=None):
        pickings = self.browse(cr, uid, ids, context=context)
        return_obj = self.pool.get('product.to.return')

        import netsvc
        wf_service = netsvc.LocalService('workflow')

        for picking in pickings:
            for move in picking.move_lines:
                if move.transportation_reason in RETURN_TRANSPORTATION_REASONS:
                    return_id = return_obj.create(cr, uid, {
                            'move_from_id': move.id,
                        }, context)
                    wf_service.trg_validate(uid, 'product.to.return', return_id,
                    'waiting', cr)

        res = super(stock_picking, self).action_done(cr, uid, ids, context)

        for picking in pickings:
            for move in picking.move_lines:
                if move.lot_lock_id and move.lot_lock_id.state == 'active':
                    move.lot_lock_id.set_done()

        return res

    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial picking and moves done.
        @param partial_datas : Dictionary containing details of partial picking
                          like partner_id, partner_id, delivery_date,
                          delivery moves with product_id, product_qty, uom
        @return: Dictionary of values
        """
        if context is None:
            context = {}
        else:
            context = dict(context)
        res = {}
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        sequence_obj = self.pool.get('ir.sequence')
        wf_service = netsvc.LocalService("workflow")
        for pick in self.browse(cr, uid, ids, context=context):
            new_picking = None
            complete, too_many, too_few = [], [], []
            move_product_qty, prodlot_ids, product_avail, partial_qty, product_uoms = {}, {}, {}, {}, {}
            for move in pick.move_lines:
                if move.state in ('done', 'cancel'):
                    continue
                partial_data = partial_datas.get('move%s'%(move.id), {})
                product_qty = partial_data.get('product_qty',0.0)
                move_product_qty[move.id] = product_qty
                product_uom = partial_data.get('product_uom',False)
                product_price = partial_data.get('product_price',0.0)
                product_currency = partial_data.get('product_currency',False)
                prodlot_id = partial_data.get('prodlot_id')
                prodlot_ids[move.id] = prodlot_id
                product_uoms[move.id] = product_uom
                partial_qty[move.id] = uom_obj._compute_qty(cr, uid, product_uoms[move.id], product_qty, move.product_uom.id)
                if move.product_qty == partial_qty[move.id]:
                    complete.append(move)
                elif move.product_qty > partial_qty[move.id]:
                    too_few.append(move)
                else:
                    too_many.append(move)

                # Average price computation
                if (pick.type == 'in') and (move.product_id.cost_method == 'average'):
                    product = product_obj.browse(cr, uid, move.product_id.id)
                    move_currency_id = move.company_id.currency_id.id
                    context['currency_id'] = move_currency_id
                    qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)

                    if product.id not in product_avail:
                        # keep track of stock on hand including processed lines not yet marked as done
                        product_avail[product.id] = product.qty_available

                    if qty > 0:
                        new_price = currency_obj.compute(cr, uid, product_currency,
                                move_currency_id, product_price, round=False)
                        new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                                product.uom_id.id)
                        if product_avail[product.id] <= 0:
                            product_avail[product.id] = 0
                            new_std_price = new_price
                        else:
                            # Get the standard price
                            amount_unit = product.price_get('standard_price', context=context)[product.id]
                            new_std_price = ((amount_unit * product_avail[product.id])\
                                + (new_price * qty))/(product_avail[product.id] + qty)
                        # Write the field according to price type field
                        product_obj.write(cr, uid, [product.id], {'standard_price': new_std_price})

                        # Record the values that were chosen in the wizard, so they can be
                        # used for inventory valuation if real-time valuation is enabled.
                        move_obj.write(cr, uid, [move.id],
                                {'price_unit': product_price,
                                 'price_currency_id': product_currency})

                        product_avail[product.id] += qty



            for move in too_few:
                product_qty = move_product_qty[move.id]
                if not new_picking:
                    new_picking_name = pick.name
                    self.write(cr, uid, [pick.id],
                               {'name': sequence_obj.get(cr, uid,
                                            'stock.picking.%s'%(pick.type)),
                               })
                    new_picking = self.copy(cr, uid, pick.id,
                            {
                                'name': new_picking_name,
                                'move_lines' : [],
                                'state':'draft',
                            })
                    attachment_obj = self.pool.get('ir.attachment')
                    attachment_ids = attachment_obj.search(cr, uid, [
                            ('res_id', '=', pick.id),
                            ('res_model', '=', 'stock.picking.in'),
                        ], context=context)
                    attachment_obj.write(cr, uid, attachment_ids, {'res_id': new_picking}, context)
                if product_qty != 0:
                    defaults = {
                            'product_qty' : product_qty,
                            'product_uos_qty': product_qty, #TODO: put correct uos_qty
                            'picking_id' : new_picking,
                            'state': 'assigned',
                            'move_dest_id': False,
                            'price_unit': move.price_unit,
                            'product_uom': product_uoms[move.id]
                    }
                    prodlot_id = prodlot_ids[move.id]
                    if prodlot_id:
                        defaults.update(prodlot_id=prodlot_id)
                    move_obj.copy(cr, uid, move.id, defaults)
                move_obj.write(cr, uid, [move.id],
                        {
                            'product_qty': move.product_qty - partial_qty[move.id],
                            'product_uos_qty': move.product_qty - partial_qty[move.id], #TODO: put correct uos_qty
                            'prodlot_id': False,
                            'tracking_id': False,
                        })

            if new_picking:
                move_obj.write(cr, uid, [c.id for c in complete], {'picking_id': new_picking})
            for move in complete:
                defaults = {'product_uom': product_uoms[move.id], 'product_qty': move_product_qty[move.id]}
                if prodlot_ids.get(move.id):
                    defaults.update({'prodlot_id': prodlot_ids[move.id]})
                move_obj.write(cr, uid, [move.id], defaults)
            for move in too_many:
                product_qty = move_product_qty[move.id]
                defaults = {
                    'product_qty' : product_qty,
                    'product_uos_qty': product_qty, #TODO: put correct uos_qty
                    'product_uom': product_uoms[move.id]
                }
                prodlot_id = prodlot_ids.get(move.id)
                if prodlot_ids.get(move.id):
                    defaults.update(prodlot_id=prodlot_id)
                if new_picking:
                    defaults.update(picking_id=new_picking)
                move_obj.write(cr, uid, [move.id], defaults)

            # At first we confirm the new picking (if necessary)
            if new_picking:
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_confirm', cr)
                # Then we finish the good picking
                self.write(cr, uid, [pick.id], {
                        'backorder_id': new_picking,
                        'ddt_number': None,
                        'ddt_date': None,
                    })
                self.action_move(cr, uid, [new_picking], context=context)
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
                delivered_pack_id = pick.id
                back_order_name = self.browse(cr, uid, delivered_pack_id, context=context).name
                self.message_post(cr, uid, new_picking, body=_("Back order <em>%s</em> has been <b>created</b>.") % (back_order_name), context=context)
            else:
                self.action_move(cr, uid, [pick.id], context=context)
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
                delivered_pack_id = pick.id

            delivered_pack = self.browse(cr, uid, delivered_pack_id, context=context)
            res[pick.id] = {'delivered_picking': delivered_pack.id or False}

        return res


class stock_picking_out(Model):
    _inherit = ["stock.picking.out", "shallow.copy.mixin"]
    _name = 'stock.picking.out'

    def _get_contents_html(self, cr, uid, ids, name, args, context=None):
        return self.pool.get('stock.picking')._get_contents_html(cr, uid, ids, name, args, context)

    def _get_picking_ids_by_stock_move_ids(self, cr, uid, ids, context=None):
        return self.pool.get('stock.picking')._get_picking_ids_by_stock_move_ids(cr, uid, ids, context)

    def _get_shipping_document_ref(self, cr, uid, ids, name, args,
        context=None):
        return self.pool.get('stock.picking')._get_shipping_document_ref(cr, uid, ids, name, args, context)

    def _get_stock_picking_ids_by_transport_document_ids(self, cr, uid, ids,
        context=None):
        return self.pool.get('stock.picking')._get_stock_picking_ids_by_transport_document_ids(cr, uid, ids, context)

    def _get_stock_picking_ids_by_shipping_invoice_ids(self, cr, uid, ids,
        context=None):
        return self.pool.get('stock.picking')._get_stock_picking_ids_by_shipping_invoice_ids(cr, uid, ids, context)

    def _get_goods_sale_value(self, cr, uid, ids, name, args, context=None):
        return self.pool.get('stock.picking')._get_goods_sale_value(cr, uid, ids, context)

    def _get_carriage_condition(self, cr, uid, ids, name, args, context=None):
        return self.pool.get('stock.picking')._get_carriage_condition(cr, uid, ids, name, args, context)

    def _set_carriage_condition(self, cr, uid, id, name, value, args, context=None):
        return self.pool.get('stock.picking')._set_carriage_condition(cr, uid, id, name, value, args, context)

    def _get_date_info(self, cr, uid, ids, name, args, context=None):
        return self.pool.get('stock.picking')._get_date_info(cr, uid, id, name, value, args, context)

    def _get_invoice_ready(self, cr, uid, ids, name, args, context=None):
        return self.pool.get('stock.picking')._get_invoice_ready(cr, uid, ids, name, args, context)

    def _search_invoice_ready(self, cr, uid, obj, name, args, domain=None, context=None):
        return self.pool.get('stock.picking')._search_invoice_ready(cr, uid, obj, name, args, domain, context)

    _columns = {
        'invoice_ready': fields.function(_get_invoice_ready, type='boolean', fnct_search=_search_invoice_ready,
            string='Invoice Ready'),
        'date_expectation': fields.function(_get_date_info, type='selection', multi='_get_date_info',
            string='Date Expectation', selection=DATE_EXPECTATIONS),
        'carriage_type': fields.related('carrier_id', 'type', type='selection', selection=CARRIAGE_TYPES,
            string='Carriage Type', readonly=True),
        'carriage_condition_id': fields.function(_get_carriage_condition, fnct_inv=_set_carriage_condition,
            type='many2one', obj='carriage.condition', string='Carriage Condition'),
        'sale_carriage_condition_id': fields.related('sale_id', 'carriage_condition_id', type='many2one',
            relation='carriage.condition', string='Carriage Condition', readonly=True),
        'picking_carriage_condition_id': fields.many2one('carriage.condition',
            'Picking Carriage condition', track_visibility='onchange'),
        'contents_html': fields.function(_get_contents_html, type='text',
            string='Contents', store = {
                'stock.move':
                    (_get_picking_ids_by_stock_move_ids,
                        ['name', 'product_qty'], 10),
                'stock.picking.out':
                    (lambda self, cr, uid, ids, context: ids,
                        ['move_lines'], 10),
            }),
        'partner_delivery_notes': fields.related('partner_id', 'delivery_notes',
            type='text', string='Delivery Notes', readonly=True),
        'partner_id': fields.many2one('res.partner', 'Partner', readonly=False,
            states={'cancel':[('readonly',True)]}),
        'customer_id': fields.many2one('res.partner', 'Cessionary',
            states={'cancel':[('readonly',True)]}),
        'goods_value': fields.function(_get_goods_sale_value, type='float',
            string='Value of goods', readonly=True,
            multi='_get_goods_sale_value'),
        'goods_dropped_value_lines': fields.function(_get_goods_sale_value,
            type='integer', string='Lines with no sale order',
            multi='_get_goods_sale_value', readonly=True,
            digits_compute=dp.get_precision('Account')),
        'currency_id': fields.related('sale_id', 'pricelist_id', 'currency_id',
            type='many2one', relation='res.currency', string='Currency',
            readonly=True),

        # TODELETE: BEGIN
        'goods_description_id': fields.many2one('goods.description',
            'Description of goods'),
        'transportation_reason_id': fields.many2one('transportation.reason',
            'Reason for transportation'),
        'transportation_id': fields.many2one('transportation',
            'Transportation organized by'),
        'manual_weight': fields.float('Weight', digits=(10,2)),
        'manual_weight_net': fields.float('Net Weight', digits=(10,2)),
        'manual_volume': fields.float('Volume (m³)', digits=(10,2)),
        'date_receipt': fields.datetime('Receipt Date'),
        # TODELETE: END
        'ddt_number': fields.char('DDT', size=64, track_visibility='onchange'),
        'ddt_date': fields.date('DDT date'),


        'shipping_notes': fields.text('Shipping Notes'),
        'transport_document_id': fields.many2one('transport.document',
            string='Transport Document'),
        'shipping_invoice_id': fields.many2one('account.invoice',
            string='Shipping Invoice'),
        'shipping_document_ref': fields.function(_get_shipping_document_ref,
            type='char', size=120, string='Shipping Document',
            readonly=True, store = {
                'stock.picking.out':
                    (lambda self, cr, uid, ids, context: ids,
                        ['transport_document_id', 'shipping_invoice_id'], 10),
                'transport.document':
                    (_get_stock_picking_ids_by_transport_document_ids,
                        ['name'], 10),
                'account.invoice':
                    (_get_stock_picking_ids_by_shipping_invoice_ids,
                        ['internal_number'], 10),
            }),
    }

    _defaults = {
        'number_of_packages': 1,
    }

    def on_change_partner_id(self, cr, uid, ids, partner_id, context=None):
        return self.pool.get('stock.picking').on_change_partner_id(cr, uid, ids,
            partner_id, context)

    def create(self, cr, uid, vals, context=None):
        if 'name' not in vals or vals.get('name') == '/':
            seq_obj = self.pool.get('ir.sequence')
            if 'type' in vals and vals['type'] == 'out':
                vals['name'] = seq_obj.get(cr, uid, 'stock.picking.out')
            elif 'type' in vals and vals['type'] == 'internal':
                vals['name'] = seq_obj.get(cr, uid, 'stock.picking.internal')
            else:
                vals['name'] = seq_obj.get(cr, uid, 'stock.picking.in')
        return super(stock_picking_out, self).create(cr, uid, vals, context)

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for p in self.browse(cr, uid, ids, context):
            if p.transport_document_id:
                raise openerp.exceptions.Warning(_('Cannot delete a delivery '
                    'order linked to a transport document!'))
        return super(stock_picking_out, self).unlink(cr, uid, ids, context)

    def action_assign(self, cr, uid, ids, *args):
        return self.pool.get('stock.picking').action_assign(cr, uid, ids, *args)

    def action_confirm(self, cr, uid, ids, context=None):
        return self.pool.get('stock.picking').action_confirm(cr, uid, ids, context)

    # TODOELETE: BEGIN
    def remove_transport_document_association(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'transport_document_id': None}, context)
    # TODELETE: END

stock_picking_out()


class stock_picking_in(Model):
    _inherit = ["stock.picking.in", "shallow.copy.mixin"]
    _name = 'stock.picking.in'

    def _get_contents_html(self, cr, uid, ids, name, args, context=None):
        return self.pool.get('stock.picking')._get_contents_html(cr, uid, ids, name, args, context)

    def _get_picking_ids_by_stock_move_ids(self, cr, uid, ids, context=None):
        return self.pool.get('stock.picking')._get_picking_ids_by_stock_move_ids(cr, uid, ids, context)

    def _get_date_info(self, cr, uid, ids, name, args, context=None):
        return self.pool.get('stock.picking')._get_date_info(cr, uid, id, name, value, args, context)

    _columns = {
    'date_expectation': fields.function(_get_date_info, type='selection', multi='_get_date_info',
            string='Date Expectation', selection=DATE_EXPECTATIONS),
        'carriage_type': fields.related('carrier_id', 'type', type='selection', selection=CARRIAGE_TYPES,
            string='Carriage Type', readonly=True),
        'contents_html': fields.function(_get_contents_html, type='text',
            string='Contents', store = {
                'stock.move':
                    (_get_picking_ids_by_stock_move_ids,
                        ['name', 'product_qty'], 10),
                'stock.picking.in':
                    (lambda self, cr, uid, ids, context: ids,
                        ['move_lines'], 10),
            }),
        'ddt_number': fields.char('Supplier DDT', size=64,
            track_visibility='onchange'),
        'ddt_date': fields.date('Supplier DDT date'),
    }

    def action_confirm(self, cr, uid, ids, context=None):
        return self.pool.get('stock.picking').action_confirm(cr, uid, ids, context)

    def action_assign(self, cr, uid, ids, *args):
        return self.pool.get('stock.picking').action_assign(cr, uid, ids, *args)


class stock_move(Model):
    _inherit = ["stock.move", "shallow.copy.mixin"]
    _name = "stock.move"

    def _check_lot_lock(self, cr, uid, ids):
        logger.debug('--------> techplus_l10n_it_sale stock.move: _check_lot_lock')
        for o in self.browse(cr, uid, ids):
            if o.lot_lock_id and o.prodlot_id.id != o.lot_lock_id.lot_id.id:
                return False
        return True

    def _check_return_date(self, cr, uid, ids):
        for o in self.browse(cr, uid, ids):
            if o.transportation_reason in RETURN_TRANSPORTATION_REASONS and \
                not o.return_date:
                return False
        return True

    def _check_return_picking_id(self, cr, uid, ids):
        for o in self.browse(cr, uid, ids):
            if o.transportation_reason in RETURN_TRANSPORTATION_REASONS and \
                not o.picking_id:
                return False
        return True

    def _check_return_partner_id(self, cr, uid, ids):
        for o in self.browse(cr, uid, ids):
            if o.transportation_reason in RETURN_TRANSPORTATION_REASONS and \
                o.picking_id and not o.picking_id.partner_id:
                return False
        return True

    def _check_transportation_reason(self, cr, uid, ids):
        t = self.pool.get('ir.config_parameter').get_param(cr, uid,
            'techplus_l10n_it_sale.def_stock_move_transportation_reason_required')
        if t and t == 'True':
            for o in self.browse(cr, uid, ids):
                if o.picking_id and o.picking_id.type in ('in', 'out'):
                    if o.state == 'done' and not o.transportation_reason:
                        return False
        return True

    def _get_transport_document_reason(self, cr, uid, ids, name, args, context=None):
        logger.debug('--------> techplus_l10n_it_sale stock.move: _get_transport_document_reason')
        res = {}
        translation_obj = self.pool.get('ir.translation')
        for o in self.browse(cr, uid, ids, context=context):
            if o.return_move_from_id and o.return_move_from_id.transportation_reason:
                name = TRASPORTATION_REASONS_DICT[o.return_move_from_id.transportation_reason]
                name = translation_obj._get_source(cr, uid, None,
                    'selection', context.get('lang'), name)
                name = _('Return from %s') % name
            elif o.transportation_reason:
                name = TRASPORTATION_REASONS_DICT[o.transportation_reason]
                name = translation_obj._get_source(cr, uid, None,
                    'selection', context.get('lang'), name)
            else:
                name = ''
            res[o.id] = name
        return res

    def _get_is_return(self, cr, uid, ids, name, args, context=None):
        logger.debug('--------> techplus_l10n_it_sale stock.picking: _get_is_return')
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = o.transportation_reason in RETURN_TRANSPORTATION_REASONS
        return res

    def _get_lot_lock_info(self, cr, uid, ids, name, args, context=None):
        logger.debug('--------> techplus_l10n_it_sale stock.move: _get_lot_lock_info')
        res = {}
        lock_obj = self.pool.get('stock.production.lot.lock')
        for o in self.browse(cr, uid, ids, context=context):
            lock_id = lock_obj.search(cr, uid, [
                    ('stock_move_id', '=', o.id),
                    ('state', '=', 'active'),
                ], limit=1, context=context)
            res[o.id] = {
                'lot_lock_id': lock_id[0] if lock_id else None,
            }
        return res

    def _get_transportation_reason_text(self, cr, uid, ids, name, args, context=None):
        res = {}
        fields = self.fields_get(cr, uid, allfields=['transportation_reason'], context=context)
        reasons = dict(fields['transportation_reason']['selection'])
        for o in self.browse(cr, uid, ids, context=context):
            text = False
            if o.transportation_reason:
                text = reasons[o.transportation_reason]
            res[o.id] = text
        return res

    _columns = {
        'purchase_margin_scheme_type': fields.related('purchase_line_id',
            'margin_scheme_type', type='selection',
            selection=MARGIN_SCHEME_MODES, string='Purchase Mode',
            readonly=True),
        'is_return': fields.function(_get_is_return, type='boolean',
            string='Is Return', store=True),
        'transportation_reason': fields.selection(TRANSPORTATION_REASONS,
            string='Transportation Reason', readonly=False,
            states={'done': [('readonly', True)]}),
        'transportation_reason_text': fields.function(_get_transportation_reason_text, type='char',
            string='Transportation Reason'),
        'return_date': fields.date('Return Date', readonly=False,
            states={'done': [('readonly', True)]}),
        'return_move_from_id': fields.many2one('stock.move',
            string='Return Move From',),
        'return_move_from_date': fields.related('return_move_from_id', 'date',
            type='date', string='Return Move From Date', readonly=True),
        'transport_document_reason': fields.function(
            _get_transport_document_reason, type='char',
            string='Transportation Reason'),
        'customer_id': fields.related('picking_id', 'customer_id',
            type='many2one', relation='res.partner', string='Cessionary',
            readonly=True),
        'destination_id': fields.related('picking_id', 'partner_id',
            type='many2one', relation='res.partner', string='Destination',
            readonly=True),
        'picking_type': fields.related('picking_id', 'type', type='selection',
            string='Picking Type', readonly=True, selection=PICKING_TYPES),
        # 'notes': fields.text('Notes'),
        'lot_lock_id': fields.function(_get_lot_lock_info, type='many2one',
            obj='stock.production.lot.lock', multi='_get_lot_lock_info', string='Lot Lock'),
    }

    _constraints = [
        (_check_lot_lock, 'The lot cannot be different from the locked one!', ['prodlot_id']),
        (_check_return_date, 'The return date is required!', ['transportation_reason', 'return_date']),
        (_check_return_picking_id, 'The picking is required for return transpostation reason!',
            ['transportation_reason']),
        (_check_return_partner_id, 'The partner on picking is required for return transpostation reason!',
            ['transportation_reason']),
        (_check_transportation_reason, 'The reason on moves is required!', ['state']),
    ]

    def write(self, cr, uid, ids, vals, context=None):
        logger.debug('--------> techplus_l10n_it_sale stock.picking: write')
        if 'state' in vals and vals['state'] == 'cancel':
            lot_lock_obj = self.pool.get('stock.production.lot.lock')
            lock_ids = lot_lock_obj.search(cr, uid, [
                    ('stock_move_id', 'in', ids),
                    ('state', '=', 'active'),
                ], context=context)
            lot_lock_obj.set_done(cr, uid, lock_ids, reason=_('Stock Move Cancelled'), context=context)
        return super(stock_move, self).write(cr, uid, ids, vals, context=context)

    def action_assign(self, cr, uid, ids, *args, **kwargs):
        logger.debug('--------> techplus_l10n_it_sale stock.picking: action_assign')
        """ Changes state to confirmed or waiting.
        @return: List of values
        """
        raise_exceptions = kwargs.get('raise_exceptions', False)
        todo = []
        lock_obj = self.pool.get('stock.production.lot.lock')
        warehouse_id = self.pool.get('stock.warehouse').search(cr, uid, [])
        warehouse_id = warehouse_id[0] if warehouse_id else None
        reason = _('Stock Picking Out Product Assignment')
        picking_ids = set()
        for move in self.browse(cr, uid, ids):
            if move.state in ('confirmed', 'waiting'):
                assigned = False
                if move.picking_id == 'out':
                    if not move.prodlot_id and not move.procuct_id.no_lot_required:
                        assigned = True
                    elif move.prodlot_id:
                        if not move.lot_lock_id:
                            lock_id = lock_obj.create(cr, uid, {
                                'lot_id': move.prodlot_id.id,
                                'sale_order_line_id': move.picking_id.sale_line_id.id \
                                    if move.picking_id and move.picking_id.sale_line_id else None,
                                'stock_move_id': move.id,
                                'begin_time': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                'expiration_time': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                'lock_reason': reason,
                                'warehouse_id': warehouse_id,
                                'quantity': move.product_qty,
                                })
                            try:
                                lock_obj.set_active(cr, uid, [lock_id], reason)
                            except Exception as e:
                                if raise_exceptions:
                                    raise
                                logger.warning(e.message)
                            move.refresh()
                        move.write({
                            'location_id': move.lot_lock_id.lock_move_id.location_dest_id.id,
                            'state': 'assigned',
                        })
                        assigned = True
                        picking_ids.add(move.picking_id.id)
                if not assigned:
                    todo.append(move.id)
        if picking_ids:
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_write(uid, 'stock.picking', pick_id, cr)
        res = self.check_assign(cr, uid, todo)
        return res


class stock_inventory(Model):
    _name = 'stock.inventory'
    _inherit = ['stock.inventory', 'mail.thread']

    _columns = {
        'name': fields.char('Inventory Reference', size=64, required=True, readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange'),
        'date': fields.datetime('Creation Date', required=True, readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange'),
        'date_done': fields.datetime('Date done', track_visibility='onchange'),
        'state': fields.selection( (('draft', 'Draft'), ('cancel','Cancelled'), ('confirm','Confirmed'), ('done', 'Done')), 'Status', readonly=True, select=True, track_visibility='onchange'),

    }