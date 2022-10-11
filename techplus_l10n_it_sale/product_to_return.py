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

import operator
import cgi
import openerp.addons.decimal_precision as dp
import openerp.exceptions

from openerp import pooler
from openerp.osv import fields
from openerp.osv.orm import Model
from openerp.tools.translate import _
from datetime import date, datetime, timedelta
from transport_document import TRANSPORTATION_REASONS
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools import float_compare

import logging
logger = logging.getLogger(__name__)

# 1 - CONFERMA DEL PICKING IN/OUT
# Si crea un oggetto product_to_return quando la causale del picking è in
# ('loan', 'sale_or_return', 'sale_on_consignment', 'repair', 'tolling')
# e l'oggetto viene confermato.

# Si crea anche un secondo picking di tipo opposto a quello
# collegato alla move_from_id che imposti la restituzione per una certa data
# questo secondo picking si deve portare in stato confermato.

# Il passaggio di stato della move_return_id oppure il collegamento alla
# invoice_line_id determineranno il passaggio di stato dell'oggetto a 'Returned'
# oppure a 'Invoiced'

# 2 - VENDITA
# Se si crea una fattura di vendita di un lotto allacciato ad una restituzione,
# allora bisognerà gestire l'annullamento della move_return_id e gestire la
# fatturazione dei prodotti che non verranno ritornati

# All'interno dei lotti bisogna far vedere se si tratta di un lotto allacciato
# ad una specifica causale...

# Stati delle move:[
#     ('draft', 'New'),
#     ('cancel', 'Cancelled'),
#     ('waiting', 'Waiting Another Move'),
#     ('confirmed', 'Waiting Availability'),
#     ('assigned', 'Available'),
#     ('done', 'Done'),
# ]

RETURN_TYPES = [
    ('outgoing', 'Delivered to'),
    ('incoming', 'Received by'),
]
# TODO: sulle procure di vendita fixare da 'outgoing' a 'incoming'

RETURN_STATES = [
    ('draft', 'Draft'),
    ('waiting', 'Waiting'),
    ('ready', 'Ready for return'),
    ('kept', 'Kept'),
    ('returned', 'Returned'),
    ('invoiced', 'Invoiced'),
    ('cancel', 'Cancel'),
]

RETURN_TRANSPORTATION_REASONS = [
    'loan', # Comodato d'uso
    'sale_or_return', # Conto visione
    'sale_on_consignment', # Conto vendita
    'repair', # Riparazione
    'tolling', # Conto lavoro
    'on_consignment', # Conto deposito
]

STOCK_MOVE_STATES = [
    ('draft', 'New'),
    ('cancel', 'Cancelled'),
    ('waiting', 'Waiting Another Move'),
    ('confirmed', 'Waiting Availability'),
    ('assigned', 'Available'),
    ('done', 'Done'),
]

KEPT_STATES = [
    ('to_account', 'To Account'),
    ('partial_accounted', 'Partially Accounted'),
    ('accounted', 'Accounted'),
]

class kept_product_to_return(Model):
    _name = "kept.product.to.return"
    _inherit = ["mail.thread", "check.bypass.mixin"]
    _description = "Kept Product To Return"

    def _get_type(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = None
            if o.move_from_id.picking_id:
                if o.move_from_id.picking_id.type == 'in':
                    res[o.id] = 'incoming'
                elif o.move_from_id.picking_id.type == 'out':
                    res[o.id] = 'outgoing'
                # c'è anche il caso type == 'internal'
        return res

    def _get_values(self, cr, uid, ids, name, args, context=None):
        res = {}
        return_obj = self.pool.get('product.to.return')
        uom_obj = self.pool.get('product.uom')
        p = self.pool.get('decimal.precision').precision_get(cr, uid,
            'Product Unit of Measure')
        for o in self.browse(cr, uid, ids, context=context):
            return_ids = return_obj.search(cr, uid, [
                    ('move_from_id', '=', o.move_from_id.id)
                ], context=context)
            state = 'to_account' # TODO: se non ci sono righe deve sepre essere to_account
            # TODO: se non ci sono righe e price_unit è 0.0 impostare sempre in to_account
            receipt_quantity = 0.0
            receipt_amount = 0.0
            invoiced_amount = 0.0
            warning_message = []
            draft_invoice_ids = set()
            draft_receipt_ids = set()
            price_total = o.price_unit * o.product_qty
            if o.invoice_line_ids:
                for line in o.invoice_line_ids:
                    if line.invoice_id.state != 'cancel':
                        if line.invoice_id.state == 'draft':
                            draft_invoice_ids.add(line.invoice_id.id)
                        # invoiced_quantity += uom_obj._compute_qty(cr, uid,
                        #     line.uos_id.id, line.quantity, o.product_uom_id.id)
                        if 'invoice' in line.invoice_id.type:
                            invoiced_amount += line.price_unit * line.quantity
                        elif 'refund' in line.invoice_id.type:
                            invoiced_amount -= line.price_unit * line.quantity
                        else:
                            raise openerp.exceptions.Warning(_('Cannot handle the invoice type %s!'
                                ) % line.invoice_id.type)

            if o.receipt_line_ids:
                for line in o.receipt_line_ids:
                    if line.voucher_id.state != 'cancel' and line.voucher_id.type in ('purchase', 'receipt'):
                        if line.voucher_id.state == 'draft':
                            draft_receipt_ids.add(line.voucher_id.id)
                        receipt_amount += line.amount
            has_accout_documents = o.invoice_line_ids or o.receipt_line_ids
            if has_accout_documents and not o._is_bypassed('ACCOUNTED_AMOUNT_OK') and (price_total > (invoiced_amount + receipt_amount)):
                state = 'partial_accounted'
                warning_message.append(_('The accounted amount is less then the total amount.'))
            elif has_accout_documents and not o._is_bypassed('ACCOUNTED_AMOUNT_OK') and (price_total < (invoiced_amount + receipt_amount)):
                state = 'partial_accounted'
                warning_message.append(_('The accounted amount is more then the total amount.'))
            elif has_accout_documents or o._is_bypassed('ACCOUNTED_AMOUNT_OK'):
                state = 'accounted'
            if draft_invoice_ids:
                warning_message.append(_('This product is linked to draft invoice(s).'))
            if draft_receipt_ids:
                warning_message.append(_('This product is linked to draft receipt(s).'))
            res[o.id] = {
                'product_to_return_id': return_ids[0] if return_ids else None,
                'state': state,
                'invoiced_amount': invoiced_amount,
                'receipt_amount': receipt_amount,
                'price_total': price_total,
                'warning_message': '\n'.join(warning_message),
                'left_amount': price_total - (invoiced_amount + receipt_amount),
                'has_warnings': bool(warning_message),
            }
        return res

    def _get_kept_product_ids_by_check_bypass_line_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale kept.product.to.return: _get_kept_product_ids_by_check_bypass_line_ids')
        res = {}
        bypasses = self.pool.get('check.bypass').browse(cr, uid, ids, context=context)
        for e in bypasses:
            if e.object_id._name == 'kept.product.to.return':
                res[e.object_id.id] = True
        return res.keys()

    def _get_kept_product_ids_by_invoice_line_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale kept.product.to.return: _get_kept_product_ids_by_invoice_line_ids')
        res = {}
        lines = self.pool.get('account.invoice.line').browse(cr, uid, ids, context=context)
        for e in lines:
            if e.kept_product_id:
                res[e.kept_product_id.id] = True
        return res.keys()

    def _get_kept_product_ids_by_invoice_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale kept.product.to.return: _get_kept_product_ids_by_invoice_ids')
        res = {}
        invoices = self.pool.get('account.invoice').browse(cr, uid, ids, context=context)
        product_to_return_ids = set()
        for invoice in invoices:
            for line in invoice.invoice_line:
                if line.kept_product_id:
                    product_to_return_ids.add(line.kept_product_id.id)
        return list(product_to_return_ids)

    def _get_kept_product_ids_by_voucher_line_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale kept.product.to.return: _get_kept_product_ids_by_voucher_line_ids')
        res = {}
        lines = self.pool.get('account.voucher.line').browse(cr, uid, ids, context=context)
        for e in lines:
            if e.kept_product_id:
                res[e.kept_product_id.id] = True
        return res.keys()

    def _get_kept_product_ids_by_voucher_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale kept.product.to.return: _get_kept_product_ids_by_voucher_ids')
        res = {}
        vouchers = self.pool.get('account.voucher').browse(cr, uid, ids, context=context)
        product_to_return_ids = set()
        for voucher in vouchers:
            for line in voucher.line_ids:
                if line.kept_product_id:
                    product_to_return_ids.add(line.kept_product_id.id)
        return list(product_to_return_ids)

    def _get_kept_product_to_return_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale kept.product.to.return: _get_kept_product_to_return_ids')
        return ids

    def _get_kept_product_to_return_ids_by_stock_move_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale kept.product.to.return: _get_product_to_return_ids_by_stock_move_ids')
        res = {}
        moves = self.pool.get('stock.move').browse(cr, uid, ids, context=context)
        move_from_ids = {}
        for move in moves:
            if move.return_move_from_id:
                move_from_ids[move.return_move_from_id.id] = True
        return self.pool.get('kept.product.to.return').search(cr, uid, [
                ('move_from_id', 'in', move_from_ids.keys()),
            ], context=context)

    def _get_current_user_id(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = uid
        return res

    _rec_name = 'product_id'

    _columns = {
        'current_user_id': fields.function(_get_current_user_id, type='many2one', obj='res.users',
            string='Current User'),
        'move_from_id': fields.many2one('stock.move', string='Move From', required=True, ondelete='restrict'),
        'partner_id': fields.related('move_from_id', 'picking_id', 'partner_id', type='many2one',
            relation='res.partner', string='Partner', readonly=True),
        'reason': fields.text('Reason'),
        'date': fields.date('Date', required=True),
        'product_qty': fields.float('Quantity', required=True, track_visibility='onchange',
            digits_compute=dp.get_precision('Product Unit of Measure')),
        'product_uom_id': fields.related('move_from_id', 'product_uom', type='many2one', relation='product.uom',
            string='Unit of Measure', readonly=True, store=True),
        'product_id': fields.related('move_from_id', 'product_id', type='many2one', relation='product.product',
            string='Product', readonly=True),
        'lot_id': fields.related('move_from_id', 'prodlot_id', type='many2one', relation='stock.production.lot',
            string='Lot', readonly=True),
        'invoice_line_ids': fields.one2many('account.invoice.line', 'kept_product_id', string='Invoice Lines'),
        'receipt_line_ids': fields.one2many('account.voucher.line', 'kept_product_id', string='Receipt Lines'),
        'product_to_return_id': fields.function(_get_values, type='many2one', obj='product.to.return',
            multi='_get_values', string='Product To Return', store=True),
        'state': fields.function(_get_values, type='selection', selection=KEPT_STATES, string='Accounting State',
            multi='_get_values',
            store = {
                'check.bypass':
                    (_get_kept_product_ids_by_check_bypass_line_ids, [], 10),
                'account.voucher':
                    (_get_kept_product_ids_by_voucher_ids, [], 10),
                'account.voucher.line':
                    (_get_kept_product_ids_by_voucher_line_ids, [], 10),
                'account.invoice':
                    (_get_kept_product_ids_by_invoice_ids, [], 10),
                'account.invoice.line':
                    (_get_kept_product_ids_by_invoice_line_ids, [], 10),
                'kept.product.to.return':
                    (_get_kept_product_to_return_ids, [], 10),
            }),
        'invoiced_amount': fields.function(_get_values, type='float', multi='_get_values', string='Invoiced Amount',
            digits_compute=dp.get_precision('Account'), store = {
                'account.invoice':
                    (_get_kept_product_ids_by_invoice_ids, [], 10),
                'account.invoice.line':
                    (_get_kept_product_ids_by_invoice_line_ids, [], 10),
                'kept.product.to.return':
                    (_get_kept_product_to_return_ids, [], 10),
            }),
        'receipt_amount': fields.function(_get_values, type='float',  multi='_get_values', string='Invoiced Amount',
            digits_compute=dp.get_precision('Account'), store = {
                'account.voucher':
                    (_get_kept_product_ids_by_voucher_ids, [], 10),
                'account.voucher.line':
                    (_get_kept_product_ids_by_voucher_line_ids, [], 10),
                'kept.product.to.return':
                    (_get_kept_product_to_return_ids, [], 10),
            }),
        'left_amount': fields.function(_get_values, type='float', multi='_get_values', string='Left amount',
            digits_compute=dp.get_precision('Account'), store = {
                'account.invoice':
                    (_get_kept_product_ids_by_invoice_ids, [], 10),
                'account.invoice.line':
                    (_get_kept_product_ids_by_invoice_line_ids, [], 10),
                'account.voucher':
                    (_get_kept_product_ids_by_voucher_ids, [], 10),
                'account.voucher.line':
                    (_get_kept_product_ids_by_voucher_line_ids, [], 10),
                'kept.product.to.return':
                    (_get_kept_product_to_return_ids, [], 10),
            }),
        'notification_date_limit': fields.related('move_from_id', 'return_date',
            type='date', string='Notification Date Limit', readonly=True, store = {
                'kept.product.to.return':
                    (_get_kept_product_to_return_ids, [], 10),
                'stock.move':
                    (_get_kept_product_to_return_ids_by_stock_move_ids, ['return_date'], 20),
            }),
        'price_total': fields.function(_get_values, type='float', digits_compute=dp.get_precision('Account'),
            multi='_get_values', string='Total Price'),
        'warning_message': fields.function(_get_values, type='text', multi='_get_values', string='Warning Message'),
        'has_warnings': fields.function(_get_values, type='text', multi='_get_values', string='Has Warnings'),
        'type': fields.function(_get_type, type='selection', string='Type', selection=RETURN_TYPES, store=True,
            select=True),
        'price_unit': fields.float(string='Unit Price', digits_compute=dp.get_precision('Account'),
            track_visibility='onchange'),
        'company_id': fields.related('move_from_id', 'company_id', type='many2one', relation='res.company',
            string='Company', readonly=True),
        'transportation_reason': fields.related('move_from_id', 'transportation_reason', type='selection',
            selection=TRANSPORTATION_REASONS, string='Transportation Reason', readonly=True),
        'transportation_reason_text': fields.related('move_from_id', 'transportation_reason_text', type='char',
            string='Transportation Reason', readonly=True),
        'notification_sent': fields.boolean('Notification Sent', track_visibility='onchange'),
    }

    _defaults = {
        'state': 'to_account',
    }

    _order = 'date desc'

    def _get_kept_notification_template_id(self, cr, uid, context=None):
        ir_model_data_obj = self.pool.get('ir.model.data')
        try:
            template_id = ir_model_data_obj.get_object_reference(cr, uid, 'techplus_l10n_it_sale',
                'email_template_kept_product_notification_it')[1]
        except ValueError:
            template_id = False
        return template_id

    def action_notification_send(self, cr, uid, ids, context=None):
        '''
        This function opens a window to compose an email, with the template message loaded by default
        '''
        assert len(ids) == 1, 'This option should only be used for a single id at a time.'
        kept_product = self.browse(cr, uid, ids[0], context)
        if kept_product.type != 'incoming':
            raise openerp.exceptions.Warning(_('This email communication is just for products kept by your company.'))
        template_id = self._get_kept_notification_template_id(cr, uid, context)
        ir_model_data = self.pool.get('ir.model.data')
        try:
            compose_form_id = ir_model_data.get_object_reference(cr, uid, 'mail',
                'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict(context)
        ctx.update({
            'default_model': 'kept.product.to.return',
            'default_res_id': ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_notification_as_sent': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def update_warnings(self, cr, uid, expiration_warning_days=30, context=None):
        expiration_date = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        datetime_warning_date = (datetime.now() + timedelta(days=expiration_warning_days))
        warning_date = datetime_warning_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        kptr_ids = self.search(cr, uid, [
                ('state', '!=', 'accounted'),
            ], context=context)
        for kptr in self.browse(cr, uid, kptr_ids, context):
            if kptr.notification_date_limit <= expiration_date:
                if kptr.notification_date_limit == expiration_date:
                    message = _("The return date expires today.")
                else:
                    message = _("The return date has been exceeded by %d day(s).") % (
                        datetime.now() - datetime.strptime(kptr.notification_date_limit,
                            DEFAULT_SERVER_DATE_FORMAT)).days
                self.message_post(cr, uid, kptr.id, body=message, type='comment',
                    subtype='techplus_l10n_it_sale.mt_kept_late_products_to_account_warning', context=context)
            elif kptr.notification_date_limit <= warning_date:
                message = _("The return date will expire in %d day(s).") % (
                        datetime_warning_date - datetime.strptime(kptr.notification_date_limit,
                            DEFAULT_SERVER_DATE_FORMAT)).days
                self.message_post(cr, uid, kptr.id, body=message, type='comment',
                    subtype='techplus_l10n_it_sale.mt_kept_products_to_account_warning', context=context)


class product_to_return(Model):
    _name = "product.to.return"
    _description = "Product to return"
    _inherit = ["mail.thread"]

    def _get_type(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = None
            if o.move_from_id.picking_id:
                if o.move_from_id.picking_id.type == 'in':
                    res[o.id] = 'incoming'
                elif o.move_from_id.picking_id.type == 'out':
                    res[o.id] = 'outgoing'
                # c'è anche il caso type == 'internal'
        return res

    def _get_values(self, cr, uid, ids, name, args, context=None):
        logger.debug('--------> techplus_l10n_it_sale product.to.return: get_values')
        res = {}
        uom_obj = self.pool.get('product.uom')
        p = self.pool.get('decimal.precision').precision_get(cr, uid, 'Product Unit of Measure')
        for o in self.browse(cr, uid, ids, context=context):
            return_planned_quantity = 0.0
            return_done_quantity = 0.0
            kept_quantity = 0.0
            for move in o.move_return_ids:
                if move.state not in ('draft', 'cancel', 'done'):
                    return_planned_quantity += uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty,
                        o.product_uom_id.id)
                if move.state == 'done':
                    return_done_quantity += uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty,
                        o.product_uom_id.id)
            for kept in o.kept_product_to_return_ids:
                kept_quantity += uom_obj._compute_qty(cr, uid, kept.product_uom_id.id, kept.product_qty,
                        o.product_uom_id.id)
                # for line in kept.invoice_line_ids:
                #     invoiced_quantity += uom_obj._compute_qty(cr, uid,
                #         line.uos_id.id, line.quantity, o.product_uom_id.id)
            res[o.id] = {
                'return_planned_quantity': return_planned_quantity,
                'return_done_quantity': return_done_quantity,
                'kept_quantity': kept_quantity,
                'return_plan_completed': (round(return_done_quantity, p) +
                    round(return_planned_quantity, p) + round(kept_quantity, p) == round(o.product_qty, p)),
                'return_completed': (round(return_done_quantity, p) +
                    round(kept_quantity, p) == round(o.product_qty, p)),
                'unknown_fate_quantity': round(o.product_qty - (
                    return_planned_quantity + return_done_quantity + kept_quantity), p),
            }
        return res

    def _get_product_to_return_ids_by_stock_move_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale product.to.return: _get_product_to_return_ids_by_stock_move_ids')
        res = {}
        move_ids = self.pool.get('stock.move').browse(cr, uid, ids,
            context=context)
        move_from_ids = {}
        for e in move_ids:
            if e.return_move_from_id:
                move_from_ids[e.return_move_from_id.id] = True
        return self.pool.get('product.to.return').search(cr, uid, [
                ('move_from_id', 'in', move_from_ids.keys()),
            ], context=context)

    def _get_product_to_return_ids_by_kept_product_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale product.to.return: _get_product_to_return_ids_by_kept_product_ids')
        res = {}
        kept_ids = self.pool.get('kept.product.to.return').browse(cr, uid, ids,
            context=context)
        move_from_ids = {}
        for e in kept_ids:
            if e.move_from_id:
                move_from_ids[e.move_from_id.id] = True
        return self.pool.get('product.to.return').search(cr, uid, [
                ('move_from_id', 'in', move_from_ids.keys()),
            ], context=context)

    def _get_product_to_return_ids_by_invoice_line_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale product.to.return: _get_product_to_return_ids_by_invoice_line_ids')
        res = {}
        line_ids = self.pool.get('account.invoice.line').browse(cr, uid, ids,
            context=context)
        kept_ids = {}
        for e in line_ids:
            if e.kept_product_id:
                kept_ids[e.kept_product_id.id] = True
        move_from_ids = {}
        for e in self.pool.get('kept.product.to.return').browse(cr, uid,
            kept_ids.keys(), context):
            if e.move_from_id:
                move_from_ids[e.move_from_id.id] = True
        return self.pool.get('product.to.return').search(cr, uid, [
                ('move_from_id', 'in', move_from_ids.keys()),
            ], context=context)

    def _get_move_return_ids(self, cr, uid, ids, name, args, context=None):
        logger.debug('--------> techplus_l10n_it_sale product.to.return: _get_move_return_ids')
        res = {}
        move_obj = self.pool.get('stock.move')
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = move_obj.search(cr, uid, [
                    ('return_move_from_id', '=', o.move_from_id.id),
                ], context=context)
        return res

    def _get_product_to_return_ids(self, cr, uid, ids, context=None):
        logger.debug('--------> techplus_l10n_it_sale product.to.return: _get_product_to_return_ids')
        return ids

    def _get_view_id_ref(self, cr, uid, module, view):
        return self.pool.get('ir.model.data').get_object_reference(
            cr, uid, module, view)[1]

    _columns = {
        'name': fields.char('Name', size=64, required=True, readonly=True),
        'date': fields.related('move_from_id', 'date', type='date', string='Date', readonly=True),
        'lot_id': fields.related('move_from_id', 'prodlot_id', type='many2one', relation='stock.production.lot',
            string='Lot', readonly=True),
        'product_id': fields.related('move_from_id', 'product_id', type='many2one', relation='product.product',
            string='Product', readonly=True),
        'partner_from_id': fields.related('move_from_id', 'picking_id', 'partner_id', type='many2one',
            relation='res.partner', string='Partner From', readonly=True),
        'return_date': fields.related('move_from_id', 'return_date', type='date', string='Return Date', readonly=True,
            store = {
                'product.to.return':
                    (_get_product_to_return_ids, [], 20),
                'stock.move':
                    (_get_product_to_return_ids_by_stock_move_ids,
                        ['return_date'], 20),
            }),
        'picking_from_id': fields.related('move_from_id', 'picking_id',
            type='many2one', relation='stock.picking', string='Picking From',
            readonly=True),
        'move_from_id': fields.many2one('stock.move', string='Stock Move FROM',
            required=True, domain=[('transportation_reason', 'in',
                RETURN_TRANSPORTATION_REASONS)], ondelete='restrict',
            readonly=True),
        'move_from_notes': fields.related('move_from_id', 'note', type='text',
            string='Notes', readonly=True),
        'type': fields.function(_get_type, type='selection', fnct_search=None,
            selection=RETURN_TYPES, string='Type', store=True, select = True),
        'product_qty': fields.related('move_from_id', 'product_qty',
            digits_compute=dp.get_precision('Product Unit of Measure'),
            type='float', string='Quantity', readonly=True, store = {
                'product.to.return':
                    (_get_product_to_return_ids, [], 10),
            }),
        'product_uom_id': fields.related('move_from_id', 'product_uom', type='many2one', relation='product.uom',
            string='Unit of Measure', readonly=True, store = {
                'product.to.return':
                    (_get_product_to_return_ids, [], 10),
            }),
        'kept_product_to_return_ids': fields.one2many('kept.product.to.return',
            'product_to_return_id', string='Kept Products', readonly=True),
        'notes': fields.text('Notes'),
        'reason': fields.related('move_from_id', 'transportation_reason',
            type='selection', string='Reason', readonly=True,
            selection=TRANSPORTATION_REASONS),
        'state': fields.related('move_from_id', 'state', type='selection',
            selection=STOCK_MOVE_STATES, string='State', readonly=True),
        'move_return_ids': fields.function(_get_move_return_ids,
            type='one2many', obj='stock.move', string='Return Moves'),
        'return_planned_quantity': fields.function(_get_values, type='float',
            digits_compute=dp.get_precision('Product Unit of Measure'), multi='_get_values',
            string='Return Planned Quantity', store = {
                'stock.move':
                    (_get_product_to_return_ids_by_stock_move_ids,
                        ['product_uom', 'product_qty', 'state'], 20),
                'product.to.return':
                    (_get_product_to_return_ids, [], 20),
            }, help="Quantity to be returned not yet delivered."),
        'return_done_quantity': fields.function(_get_values, type='float',
            digits_compute=dp.get_precision('Product Unit of Measure'), multi='_get_values',
            string='Return Done Quantity', store = {
                'stock.move':
                    (_get_product_to_return_ids_by_stock_move_ids,
                        ['product_uom', 'product_qty', 'state'], 20),
                'product.to.return':
                    (_get_product_to_return_ids, [], 20),
            }, help="Quantity to be returned already delivered."),
        'unknown_fate_quantity': fields.function(_get_values, type='float',
            digits_compute=dp.get_precision('Product Unit of Measure'), multi='_get_values',
            string='Unknown Fate Quantity', store = {
                'stock.move':
                    (_get_product_to_return_ids_by_stock_move_ids,
                        ['product_uom', 'product_qty', 'state'], 20),
                'kept.product.to.return':
                    (_get_product_to_return_ids_by_kept_product_ids,
                        ['product_uom_id', 'product_qty'], 20),
                'product.to.return':
                    (_get_product_to_return_ids, [], 20),
            }, help="Quantity for which is yet to be known if it will be " \
            "kept or returned."),
        'kept_quantity': fields.function(_get_values, type='float',
            digits_compute=dp.get_precision('Product Unit of Measure'), multi='_get_values', string='Kept Quantity',
            store = {
                'kept.product.to.return':
                    (_get_product_to_return_ids_by_kept_product_ids,
                        ['product_uom_id', 'product_qty'], 20),
                'product.to.return':
                    (_get_product_to_return_ids, [], 20),
            }),
        'invoiced_quantity': fields.function(_get_values, type='float',
            digits_compute=dp.get_precision('Product Unit of Measure'), multi='_get_values', string='Invoiced Quantity',
            store = {
                'account.invoice.line':
                    (_get_product_to_return_ids_by_invoice_line_ids,
                        ['uos_id', 'quantity'], 20),
                'product.to.return':
                    (_get_product_to_return_ids, [], 20),
            }),
        'return_plan_completed': fields.function(_get_values, type='boolean', multi='_get_values',
            string='Return Plan Completed', store = {
                'stock.move':
                    (_get_product_to_return_ids_by_stock_move_ids,
                        ['product_uom', 'product_qty', 'state'], 20),
                'kept.product.to.return':
                    (_get_product_to_return_ids_by_kept_product_ids,
                        ['product_uom_id', 'product_qty'], 20),
                'product.to.return':
                    (_get_product_to_return_ids, [], 20),
            }),
        'return_completed': fields.function(_get_values, type='boolean', multi='_get_values', string='Return Completed',
            store = {
                'stock.move':
                    (_get_product_to_return_ids_by_stock_move_ids,
                        ['product_uom', 'product_qty', 'state'], 20),
                'kept.product.to.return':
                    (_get_product_to_return_ids_by_kept_product_ids,
                        ['product_uom_id', 'product_qty'], 20),
                'product.to.return':
                    (_get_product_to_return_ids, [], 20),
            }),
    }

    _defaults = {
        'name': '/',
    }

    _sql_constraints = [
        ('move_from_uniq', 'unique(move_from_id)',
            'The move from must be unique!'),
        ('name_uniq', 'unique(name)', 'The name must be unique!'),
    ]

    _order = 'return_date desc'

    def keep(self, cr, uid, ids, context=None):
        assert len(ids) == 1
        ptr = self.pool.get('product.to.return').browse(cr, uid, ids[0], context)
        view_id = self._get_view_id_ref(cr, uid, 'techplus_l10n_it_sale', 'view_kept_product_to_return_wizard_form')
        model = 'kept.product.to.return.wizard'
        return {
                'type': 'ir.actions.act_window',
                'name': _('Keep product'),
                'res_model': model,
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': view_id,
                'target': 'new',
                'context': context,
                'flags': {
                    'form': {
                        'initial_mode': 'edit',
                    }
                }
            }

    def update_warnings(self, cr, uid, expiration_warning_days=30, context=None):
        expiration_date = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        datetime_warning_date = (datetime.now() + timedelta(days=expiration_warning_days))
        warning_date = datetime_warning_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        ptr_ids = self.search(cr, uid, [
                ('return_completed', '=', False),
            ], context=context)
        for ptr in self.browse(cr, uid, ptr_ids, context):
            if ptr.return_date <= expiration_date:
                if ptr.return_date == expiration_date:
                    message = _("The return date expires today.")
                else:
                    message = _("The return date has been exceeded by %d day(s).") % (
                        datetime.now() - datetime.strptime(ptr.return_date, DEFAULT_SERVER_DATE_FORMAT)).days
                self.message_post(cr, uid, ptr.id, body=message, type='comment',
                    subtype='techplus_l10n_it_sale.mt_late_products_to_be_returned_warning', context=context)
            elif ptr.return_date <= warning_date:
                message = _("The return date will expire in %d day(s).") % (
                        datetime_warning_date - datetime.strptime(ptr.return_date, DEFAULT_SERVER_DATE_FORMAT)).days
                self.message_post(cr, uid, ptr.id, body=message, type='comment',
                    subtype='techplus_l10n_it_sale.mt_products_to_be_returned_warning', context=context)

    def create(self, cr, user, vals, context=None):
        if ('name' not in vals) or (vals.get('name')=='/'):
            vals['name'] = self.pool.get('ir.sequence').get(cr, user,
                'seq.product.to.return')
        return super(product_to_return, self).create(cr, user, vals, context)

    # def write(self, cr, uid, ids, data, context=None):
    #     if isinstance(ids, (int, long,)):
    #         ids = [ids]
    #     if 'invoice_line_id' in data.keys():
    #         for p in self.browse(cr, uid, ids, context):
    #             if p.invoice_line_id and \
    #                p.invoice_line_id != data['invoice_line_id']:
    #                 n = p.invoice_id.number
    #                 raise openerp.exceptions.Warning(_(
    #                     "You're trying to update the invoice line link of a "
    #                     "product to return already linked to %s. "
    #                     "In order to update this data you must delete the "
    #                     "referenced invoice line!") %
    #                     n if n else _('a draft invoice'))
    #     return super(product_to_return, self).write(cr, uid, ids, data,
    #         context=context)

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for record in self.browse(cr, uid, ids, context):
            if record.state != 'draft':
                raise openerp.exceptions.Warning(_(
                    'Only products to return in draft state can be deleted!'))
        return super(product_to_return, self).unlink(cr, uid, ids, context)

    def create_return_pickings(self, cr, uid, return_ids=None,
        days_to_compute=0, date=None, quantity=None, reason=None, context=None):
        if context and context.get('active_model') == 'product.to.return' and \
           context.get('active_ids') and not return_ids:
            return_ids = context['active_ids']
        # TODO: Check active_id
        picking_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        start_time = datetime.now()
        logger.info('PICKING_RETURN: Create return pickings')
        import netsvc
        wf_service = netsvc.LocalService('workflow')
        try:
            if date:
                date = datetime.strptime(date, DEFAULT_SERVER_DATE_FORMAT)
            else:
                date = start_time.date()
            if return_ids:
                if isinstance(return_ids, (int, long)):
                    return_ids = [return_ids]
            if not return_ids:
                date_limit = date + timedelta(days=days_to_compute)
                domain = [
                    ('return_plan_completed', '=', False),
                    ('return_date', '<=', datetime.strftime(date_limit,
                        DEFAULT_SERVER_DATE_FORMAT)),
                ]
                return_ids = self.search(cr, uid, domain, context=context)
            picking_from_ids = {}
            for ptr in self.browse(cr, uid, return_ids, context):
                if ptr.reason not in RETURN_TRANSPORTATION_REASONS:
                    raise Exception(
                        'PRODUCT_RETURN_ERROR: Unsupported Transportation ' \
                        'Reason for stock move %s' % ptr.name)
                if ptr.reason and not ptr.return_date:
                    raise Exception(
                        'PRODUCT_RETURN_ERROR: No return_date found ' \
                        'for stock move %s' % ptr.name)
                if ptr.picking_from_id:
                    picking_from_ids[ptr.picking_from_id.id] = True
                else:
                    logger.error(
                        'PICKING_RETURN_ERROR: No picking for "id: %d."' % r.id)
                    raise Exception()
            res = {}
            for picking in picking_obj.browse(cr, uid,
                picking_from_ids.keys(), context):
                product_to_return_ids = self.search(cr, uid, [
                        ('id', 'in', return_ids),
                        ('picking_from_id', '=', picking.id)
                    ], context=context)
                if picking.type not in ('out', 'in'):
                    raise Exception(
                        'PICKING_RETURN_ERROR: Unsupported Picking Type: ' \
                        'can\'t create return picking for %s.' % picking.name)
                seq = 'stock.picking.in' if picking.type == 'out' else \
                    'stock.picking.out'
                return_picking_id = picking_obj.create(cr, uid, {
                        'name': self.pool.get('ir.sequence').get(cr, uid, seq),
                        'type': 'in' if picking.type == 'out' else 'out',
                        'date': datetime.strftime(date,
                            DEFAULT_SERVER_DATE_FORMAT),
                        'origin': _('Scheduled Return for %s'
                            ) % picking.name,
                        'location_id': picking.location_dest_id.id if \
                            picking.location_dest_id else None,
                        'location_dest_id': picking.location_id.id if \
                            picking.location_id else None,
                        'move_type': 'direct',
                        'state': 'draft',
                        'partner_id': picking.customer_id.id if \
                            picking.customer_id else picking.partner_id.id,
                        'customer_id': picking.customer_id.id if \
                            picking.customer_id else picking.partner_id.id,
                    }, context)
                for ptr in self.browse(cr, uid, product_to_return_ids,
                    context):
                    move_from = ptr.move_from_id
                    if quantity and quantity <= ptr.unknown_fate_quantity:
                        product_qty = quantity
                    else:
                        product_qty =  ptr.unknown_fate_quantity
                    note = move_from.note if move_from.note else ''
                    if move_from.picking_id and move_from.picking_id.ddt_number:
                        notes = [note] if note else []
                        if move_from.picking_id.ddt_date:
                            notes.append(_('Related to transport document %s ' \
                                'delivered on %s')
                                % (move_from.picking_id.ddt_number,
                                    move_from.picking_id.ddt_date))
                        else:
                            notes.append(_('Related to transport document %s') \
                                % move_from.picking_id.ddt_number)
                        note = '\n'.join([n for n in notes])
                    if reason:
                        note = ('%s\n%s' % (note, reason)) if note else reason
                    move_id = move_obj.create(cr, uid, {
                            'return_move_from_id': move_from.id,
                            'transportation_reason': 'return',
                            'picking_id': return_picking_id,
                            'name': move_from.name,
                            'priority': move_from.priority,
                            'date': move_from.return_date,
                            'date_expected': move_from.return_date,
                            'product_id': move_from.product_id.id,
                            'product_qty': product_qty,
                            'product_uom': move_from.product_uom.id,
                            'product_packaging': move_from.product_packaging.id \
                                if move_from.product_packaging else None,
                            'location_id': move_from.location_dest_id.id,
                            'location_dest_id': move_from.location_id.id,
                            'partner_id': move_from.partner_id.id if \
                                move_from.partner_id else None,
                            'prodlot_id': move_from.prodlot_id.id if \
                                move_from.prodlot_id else None,
                            'auto_validate': False,
                            'note': note,
                            'price_unit': move_from.price_unit,
                            'price_currency_id': move_from.price_currency_id.id \
                                if move_from.price_currency_id else None,
                            'company_id': move_from.company_id.id,
                            'origin': move_from.picking_id.name,
                            'type': 'in' if picking.type == 'out' else 'out',
                        }, context)
                    res[ptr.id] = move_id
                wf_service.trg_validate(uid, 'stock.picking', return_picking_id,
                    'button_confirm', cr)
                # DONE: se le move NON hanno quantità sufficiente per la restituzione deve dare errore, altrimenti il picking deve assegnare la quantità in uscita.
                picking_obj.action_assign(cr, uid, [return_picking_id])
            logger.info('PICKING_RETURN: Creation of return Picking complete')
            logger.info('Total Time: %s' % str(datetime.now() - start_time))
        except Exception as e:
            logger.error(e)
            raise
        return res
