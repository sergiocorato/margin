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

import openerp.exceptions
import time
import netsvc
import logging
import openerp.addons.decimal_precision as dp
import cgi

from dateutil.relativedelta import relativedelta
from datetime import date, datetime, timedelta
from openerp.osv import fields
from openerp.osv.orm import Model
from openerp.tools.translate import _
from openerp import pooler
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from product_to_return import RETURN_TRANSPORTATION_REASONS
from .delivery import CARRIAGE_TYPES

logger = logging.getLogger(__name__)

STOCK_MOVE_STATES = [
    ('draft', 'New'),
    ('cancel', 'Cancelled'),
    ('waiting', 'Waiting Another Move'),
    ('confirmed', 'Waiting Availability'),
    ('assigned', 'Available'),
    ('done', 'Done'),
]

FEE_TYPES = [
    ('percentage', 'Percentage'),
    ('fee', 'Fee'),
    ('greater', 'The greater amount between the fee and the percentage'),
    ('lower', 'The lower amount between the fee and the percentage'),
]


class sale_order(Model):
    _inherit = "sale.order"

    def _prepare_order_line_move(self, cr, uid, order, line, picking_id, date_planned, context=None):
        res = super(sale_order, self)._prepare_order_line_move(cr, uid, order, line, picking_id, date_planned, context)
        res['transportation_reason'] = 'sale'
        return res

    def _make_invoice(self, cr, uid, order, lines, context=None):
        if context is None:
            context = {}

        inv_id = super(sale_order, self)._make_invoice(cr, uid, order, lines,
            context)
        partner = self.pool.get('res.partner').browse(cr, uid,
            order.partner_id.id)
        carriage_condition_id = order.carriage_condition_id.id
        if not carriage_condition_id:
            carriage_condition_id = partner.carriage_condition_id.id if partner.carriage_condition_id else None
        self.pool.get('account.invoice').write(cr, uid, inv_id, {
            'carriage_condition_id': carriage_condition_id,
            'goods_description_id': partner.goods_description_id.id if partner.goods_description_id else None,
            'transportation_reason_id': partner.transportation_reason_id.id if partner.transportation_reason_id else None,
            # 'transportation_id': partner.transportation_id.id if partner.transportation_id else None,
        })

        return inv_id

    def _get_sale_line_info(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            services_only = True
            for line in o.order_line:
                if line.product_id and line.product_id.type != 'service':
                    services_only = False
                    break
            res[o.id] = {
                'services_only': services_only,
            }
        return res

    _columns =  {
        'carriage_condition_id': fields.many2one('carriage.condition', string='Carriage condition', readonly=True,
            states={'draft':[('readonly',False)], 'sent':[('readonly',False)]}),
        'validity': fields.date('Validity'),
        'shipping_notes': fields.text('Shipping Notes'),
        'product_id': fields.related('order_line', 'product_id', type='many2one', relation='product.product',
            string='Product'),
        'order_line_name': fields.related('order_line', 'name', type='char', string='Line description'),
        'services_only': fields.function(_get_sale_line_info, type='boolean', multi='_get_sale_line_info',
            string='Services Only'),
        'carrier_type': fields.related('carrier_id', 'type', type='selection', selection=CARRIAGE_TYPES,
            string='Carrier Type', readonly=True),
    }

    def on_change_carrier_id(self, cr, uid, ids, carrier_id, context=None):
        value = {
            'carrier_type': False,
            'carriage_condition_id': False,
            'goods_description_id': False,
            'transportation_reason_id': False,
            'transportation_responsible_id': False,
        }
        if carrier_id:
            carrier = self.pool.get('delivery.carrier').browse(cr, uid, carrier_id, context)
            value['carriage_condition_id'] = carrier.carriage_condition_id.id
            value['goods_description_id'] = carrier.goods_description_id.id
            value['transportation_reason_id'] = carrier.transportation_reason_id.id
            value['transportation_responsible_id'] = carrier.transportation_responsible_id.id
            if carrier.type:
                value['carrier_type'] = carrier.type
        return {'value': value}

    def onchange_shop_id(self, cr, uid, ids, shop_id, partner_id, context=None):
        value = super(sale_order, self).onchange_shop_id(cr, uid, ids, shop_id, context)['value']
        if partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context)
            if partner.property_product_pricelist and 'pricelist_id' in value:
                del(value['pricelist_id'])
        return {'value': value}

    def default_get(self, cr, uid, fields=None, context=None):
        res = super(sale_order, self).default_get(cr, uid, fields, context)
        if 'partner_id' in res:
            partner = self.pool.get('res.partner').browse(cr, uid, res['partner_id'], context)
            if partner.property_product_pricelist:
                res['pricelist_id'] = partner.property_product_pricelist.id
        return res

    def on_change_carriage_condition(self, cr, uid, ids, carriage_condition_id, context=None):
        res = {}
        incoterm_ids = []
        if carriage_condition_id:
            condition = self.pool.get('carriage.condition').browse(cr, uid, carriage_condition_id, context)
            if condition.incoterm_code:
                incoterm_ids = self.pool.get('stock.incoterms').search(cr, uid, [
                        ('code', '=', condition.incoterm_code),
                    ], limit=1, context=context)
        res['incoterm'] = incoterm_ids[0] if incoterm_ids else None
        return {'value': res}

    def set_to_cancel_quotations(self, cr, uid, cron=False, date=None,
        days_to_subtract=60, context=None):
        start_time = datetime.now()
        logger.info('-----------------> Cancel old quotations request')
        self._cr = pooler.get_db(cr.dbname).cursor()

        try:
            if date:
                date = datetime.strptime(date, DEFAULT_SERVER_DATE_FORMAT)
            else:
                date = start_time.date()
            expiry_date = date - timedelta(days=days_to_subtract)
            order_ids = self.search(self._cr, uid,[
                    ('state', 'in', ('draft', 'sent')),
                    '|',
                    ('validity', '<', date),
                    ('validity', '=', False),
                    ('date_order', '<', expiry_date)
                ], context=context)
            wf_service = netsvc.LocalService('workflow')
            for order_id in order_ids:
                wf_service.trg_validate(uid, 'sale.order', order_id,
                    'cancel', self._cr)
            self._cr.commit()
            self._cr.close()
            logger.info('-----------------> Cancel old quotations complete')
            logger.info('Total Time: %s' % str(datetime.now() - start_time))

        except Exception as e:
            logger.error('-----------------> Cancel old quotations error')
            logger.error('cancel quotations exception: %s' % str(e))
            self._cr.rollback()
            self._cr.close()

        return None

    def _update_lot_locks(self, cr, uid, order_lines, context=None):
        lock_obj = self.pool.get('stock.production.lot.lock')
        move_obj = self.pool.get('stock.move')
        locks_lookup = {}
        for line in order_lines:
            if line.lot_lock_id:
                locks_lookup[line.id] = line.lot_lock_id.id
        move_ids = move_obj.search(cr, uid, [('sale_line_id', 'in', locks_lookup.keys())], context=context)
        for move in move_obj.browse(cr, uid, move_ids, context):
            lock_obj.write(cr, uid, locks_lookup[move.sale_line_id.id], {
                    'stock_move_id': move.id,
                }, context)

    def _create_pickings_and_procurements(self, cr, uid, order, order_lines, picking_id=False,
        one_picking_per_line=False, context=None):
        super(sale_order, self)._create_pickings_and_procurements(cr, uid, order, order_lines, picking_id, one_picking_per_line, context)
        self._update_lot_locks(cr, uid, order_lines, context)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        super(sale_order, self).action_cancel(cr, uid, ids, context)
        for order in self.browse(cr, uid, ids, context):
            for line in order.order_line:
                if line.lot_lock_id:
                    line.lot_lock_id.set_done(reason=_('Sale Order Cancelled'))
        return True

    def action_ship_create(self, cr, uid, ids, *args):
        res = super(sale_order, self).action_ship_create(cr, uid, ids, *args)

        # read stock.picking.out defaults
        tmp = self.pool.get('ir.values').get_defaults(cr, uid, 'stock.picking.out')
        defaults = {}
        for id, field_name, value in tmp:
            defaults[field_name] = value
        # TODELETE: BEGIN
        default_carriage_condition_id = defaults.get('carriage_condition_id')
        default_goods_description_id = defaults.get('goods_description_id')
        default_transportation_reason_id = defaults.get('transportation_reason_id')
        default_transportation_id = defaults.get('transportation_id')
        # TODELETE: END

        # update stock.picking records
        for order in self.browse(cr, uid, ids, context={}):
            partner = order.partner_id
            pk_obj = self.pool.get('stock.picking')
            picking_ids = pk_obj.search(cr, uid, [('sale_id', '=', order.id)])

            carriage_condition_id = partner.carriage_condition_id.id if partner.carriage_condition_id else default_carriage_condition_id
            goods_description_id = partner.goods_description_id.id if partner.goods_description_id else default_goods_description_id
            transportation_reason_id = partner.transportation_reason_id.id if partner.transportation_reason_id else default_transportation_reason_id
            transportation_id = partner.transportation_id.id if partner.transportation_id else default_transportation_id

            for picking_id in picking_ids:
                vals = {
                    # TODELETE: BEGIN
                    'carriage_condition_id': carriage_condition_id,
                    'goods_description_id': goods_description_id,
                    'transportation_reason_id': transportation_reason_id,
                    'transportation_id': transportation_id,
                    # TODELETE: END
                    'shipping_notes': order.shipping_notes,
                    'customer_id': order.partner_invoice_id.id,
                }
                # if hasattr(order, 'logistics_notes'):
                #     vals['note'] = order.logistics_notes
                pk_obj.write(cr, uid, picking_id, vals)

        return res


class sale_order_line(Model):
    _inherit = "sale.order.line"

    def _is_gift(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = bool(o.gift_reference_line_id)
        return res

    def _has_gift(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = bool(o.gift_line_ids)
        return res

    def _get_lot_lock_info(self, cr, uid, ids, name, args, context=None):
        res = {}
        lock_obj = self.pool.get('stock.production.lot.lock')
        for o in self.browse(cr, uid, ids, context=context):
            lock_id = lock_obj.search(cr, uid, [
                    ('sale_order_line_id', '=', o.id),
                    ('state', '=', 'active'),
                ], limit=1, context=context)
            res[o.id] = {
                'lot_lock_id': lock_id[0] if lock_id else None,
            }
        return res

    def _get_view_id_ref(self, cr, uid, module, view):
        return self.pool.get('ir.model.data').get_object_reference(
            cr, uid, module, view)[1]

    def _get_has_rel_invoices(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = len(o.invoice_lines) > 0
        return res

    _columns = {
        'partner_id': fields.related('order_id', 'partner_id', type='many2one', relation='res.partner',
            string='Partner', readonly=True),
        'order_name': fields.related('order_id', 'name', type='char', string='Order', readonly=True),
        'date_order': fields.related('order_id', 'date_order', type='date', string='Order Date', readonly=True),
        'is_gift': fields.function(_is_gift, type='boolean', string='Is Gift', readonly=True),
        'has_gift': fields.function(_has_gift, type='boolean', string='Has Gift', readonly=True),
        'gift_reference_line_id': fields.many2one('sale.order.line', string='Gift Reference', ondelete='restrict'),
        'gift_line_ids': fields.one2many('sale.order.line', 'gift_reference_line_id', string='Gift'),
        'lot_id': fields.many2one('stock.production.lot', string='Lot', domain="[('product_id', '=', product_id)]"),
        'lot_lock_ids': fields.one2many('stock.production.lot.lock', 'sale_order_line_id', string='Lot Locks'),
        'lot_lock_id': fields.function(_get_lot_lock_info, type='many2one',
            obj='stock.production.lot.lock', multi='_get_lot_lock_info', string='Lot Lock',
            help="The active lot lock associated to the current line."),
        # 'has_lot_lock': fields.function(_get_lot_lock_info, arg=None, fnct_inv=None, fnct_inv_arg=None,
        #     type='boolean', multi='_get_lot_lock_info', string='Has Lot Lock'),
        'lot_lock_expiration_time': fields.related('lot_lock_id', 'expiration_time', type='datetime',
            relation='rel_model', string='Lot Lock Expiration', readonly=True),
        'has_rel_invoices': fields.function(_get_has_rel_invoices, type='boolean', string='Has Releated Invoices'),
    }

    def create(self, cr, uid, vals, context=None):
        if vals.get('lot_id') and vals.get('product_id'):
            lot = self.pool.get('stock.production.lot').browse(cr, uid, vals['lot_id'], context)
            if lot.product_id.id != vals['product_id']:
                product = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context)
                raise openerp.exceptions.Warning(
                    _('Cannot crate the line for "%s" because the lot is releated to a different product!'
                        ) % product.name)
        if vals.get('lot_id') and not vals.get('product_id'):
            raise openerp.exceptions.Warning(
                 _('Cannot crate the line for lot [%s] because the line does not specify any product!'
                    ) % lot.ref)
        return super(sale_order_line, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids, context):
            if ('product_id' in vals or 'lot_id' in vals) and line.lot_lock_id:
                raise openerp.exceptions.Warning(
                    _('Before changing product or lot in a sale order line you must remove the lot lock!'))
        super(sale_order_line, self).write(cr, uid, ids, vals, context)
        for line in self.browse(cr, uid, ids, context):
            if line.lot_id and line.product_id and (line.lot_id.product_id.id != line.product_id.id):
                raise openerp.exceptions.Warning(
                    _('Cannot update the line for "%s" because the lot is releated to a different product!'
                        ) % line.product_id.name)
            if line.lot_id and not line.product_id:
                raise openerp.exceptions.Warning(
                 _('Cannot update the line for lot [%s] because the line does not specify any product!'
                    ) % lot.ref)
        return True

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids, context):
            if line.lot_lock_id:
                self.pool.get('stock.production.lot.lock').set_done(cr, uid, [line.lot_lock_id.id],
                    _('Releated sale order line has been deleted!'), context)
        return super(sale_order_line, self).unlink(cr, uid, ids, context)

    def lot_id_change(self, cr, uid, ids, product_id, lot_id, context=None):
        return {'value': {}}

    def action_open_rel_invoice(self, cr, uid, ids, context=None):
        if len(ids) < 1:
            raise openerp.exceptions.Warning(_('No order line selected!'))
        invoice_obj = self.pool.get('account.invoice')
        invoices = self.browse(cr, uid, ids[0], context).invoice_lines
        tree_view_id = self._get_view_id_ref(cr, uid, 'account', 'invoice_tree')
        form_view_id = self._get_view_id_ref(cr, uid, 'account', 'invoice_form')
        invoice_ids = list(set([i.invoice_id.id for i in invoices]))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice',
            'view_mode': 'tree,form',
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', invoice_ids)],
            'target': 'current',
        }

    def create_gift_line(self, cr, uid, ref_line_id, qty, context=None):
        # Gift Product Info
        gift_product_id = self.pool.get('ir.config_parameter').get_param(cr,
            uid, 'techplus_l10n_it_sale.def_gift_product_id')
        gift_product_id = int(gift_product_id) if gift_product_id else None
        if not gift_product_id:
            raise openerp.exceptions.Warning(_(
                "A default gift product must be defined first!"))
        gift_product = self.pool.get('product.product').browse(cr, uid,
            gift_product_id, context)
        gift_line_tax_ids  = [(6, 0, [t.id for t in gift_product.taxes_id])]

        ref_line = self.browse(cr, uid, ref_line_id, context)
        # Reference Line Check
        if ref_line.gift_reference_line_id:
            raise openerp.exceptions.Warning(_(
                "Cannot create a gift line referred to another gift line!"))
        if ref_line.gift_line_ids:
            raise openerp.exceptions.Warning(_(
                "Only one gift line is allowed for each sale order line!"))

        # Gift Order Line Creation
        vals = {
            'gift_reference_line_id': ref_line.id,
            'order_id': ref_line.order_id.id,
            'product_id': gift_product.id,
            'name': '%s: %s' % (gift_product.name, ref_line.name),
            'product_uom': ref_line.product_uom.id,
            'product_uom_qty': qty,
            'price_unit': -ref_line.price_unit,
            'discount': ref_line.discount,
            'tax_id': gift_line_tax_ids,
            'state': 'draft',
        }

        # sequence
        if context and 'gift_line_sequence' in context:
            vals['sequence'] = context['gift_line_sequence']

        # techplus_sale_margin support
        if 'purchase_price' in ref_line:
            vals['purchase_price'] = -ref_line.purchase_price

        # techplus_sale_discount support
        if 'report_unit_price' in ref_line:
            vals.update({
                'report_unit_price': - ref_line.report_unit_price,
                'report_discount1': ref_line.report_discount1,
                'report_discount2': ref_line.report_discount2,
                'report_discount3': ref_line.report_discount3,
            })

        gift_line_id = self.create(cr, uid, vals, context)

        return gift_line_id
