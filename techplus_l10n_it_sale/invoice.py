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
import openerp.addons.decimal_precision as dp
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime
from openerp.osv import fields
from openerp.osv.orm import Model

from openerp.tools.translate import _
from stock import MARGIN_SCHEME_MODES, MARGIN_SCHEME_MODES_NOT_NEW

INVOICE_STATES =[
    ('draft','Draft'),
    ('proforma','Pro-forma'),
    ('proforma2','Pro-forma'),
    ('open','Open'),
    ('paid','Paid'),
    ('cancel','Cancelled'),
]

INVOICE_TYPES = [
    ('out_invoice', 'Customer Invoice'),
    ('in_invoice', 'Supplier Invoice'),
    ('out_refund', 'Customer Refund'),
    ('in_refund', 'Supplier Refund'),
]

UE_CODES = [
    'BE', 'BG', 'CZ', 'DK', 'DE', 'EE', 'IE', 'EL', 'ES', 'FR', 'HR', 'IT', 'CY', 'LV',
    'LT', 'LU', 'HU', 'MT', 'NL', 'AT', 'PL', 'PT', 'RO', 'SI', 'SK', 'FI', 'SE', 'UK',
]

LINE_TYPES = [
    ('invoice', 'Invoice'),
    ('refund', 'Refund'),
]




class margin_scheme_invoice_line(Model):
    _name = "margin.scheme.invoice.line"
    _description = "Margin Scheme Invoice Line"

    def _get_amount(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = (o.taxable_line_id.price_unit *
                o.taxable_line_id.quantity) + (o.untaxable_line_id.price_unit * o.untaxable_line_id.quantity)
        return res

    _columns = {
        'name': fields.char('Description', size=256, required=True),
        'invoice_id': fields.many2one('account.invoice', string='Invoice', ondelete='cascade'),
        'taxable_line_id': fields.many2one('account.invoice.line', string='Taxable Line', required=True, readonly=True),
        'untaxable_line_id': fields.many2one('account.invoice.line', string='Untaxable Line', required=True,
            readonly=True),
        'register_line_id': fields.many2one('goods.loading.register.line',
            string='Register Entry', required=True, domain=[('state','=','loaded')], readonly=True),
        'lot_id': fields.related('register_line_id', 'lot_id', type='many2one',
            relation='stock.production.lot', string='Lot', readonly=True),
        'product_id': fields.related('lot_id', 'product_id', type='many2one',
            relation='product.product', string='Product', readonly=True),
        'uos_id': fields.many2one('product.uom', 'Unit of Measure', ondelete='set null', select=True),
        'quantity': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), required=True),
        'amount': fields.function(_get_amount, type='float', string='Amount',
            digits_compute=dp.get_precision('Account')),
        'sequence': fields.integer('Sequence'),
        'state': fields.related('invoice_id', 'state', type='selection', string='State', readonly=True,
            selection=INVOICE_STATES),
        'commodity_code_id': fields.many2one('invoice.line.commodity.code', string='Commodidty Code'),
        'type': fields.selection(LINE_TYPES, string='Type', required=True),
    }

    _defaults = {
        'sequence': 1,
        'quantity': 1.0,
        'type': 'invoice',
    }

    _sql_constraints = [
        ('register_line_id_uniq', 'unique (register_line_id, type)',
            'The register_line_id must be unique! Another margin scheme invoice line using ' \
            'the same good\'s load/unload register line has been found.'),
    ]

    _order = 'sequence, id asc'

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        invoice_line_ids = set()
        for record in self.browse(cr, uid, ids, context):
            if record.taxable_line_id:
                invoice_line_ids.add(record.taxable_line_id.id)
            if record.untaxable_line_id:
                invoice_line_ids.add(record.untaxable_line_id.id)
        res = super(margin_scheme_invoice_line, self).unlink(cr, uid, ids,
            context)
        self.pool.get('account.invoice.line').unlink(cr, uid,
            list(invoice_line_ids), context)
        return res

    def update_amount(self, cr, uid, ids, amount, context=None):
        for line in self.browse(cr, uid, ids, context):
            purchase_amount = line.register_line_id.price_in
            margin_amount = amount - purchase_amount
            if margin_amount < 0.0:
                margin_amount = 0.0
            if purchase_amount > amount:
                purchase_amount = amount
            line.taxable_line_id.write({
                    'price_unit': margin_amount,
                    'quantity': 1.0,
                })
            line.untaxable_line_id.write({
                    'price_unit': purchase_amount,
                    'quantity': 1.0,
                })
        return True


class account_invoice_tax(Model):
    _inherit = "account.invoice.tax"

    _columns = {
        'is_margin_scheme': fields.boolean('Margin Scheme Tax'),
    }

    _defaults = {
        'is_margin_scheme': False,
    }


class account_invoice(Model):
    _inherit = "account.invoice"

    def _get_ms_info(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = {
                'ms_amount_untaxed': o.amount_untaxed,
                'ms_amount_tax': o.amount_tax,
                'ms_amount_total': o.amount_total,
                'ms_residual': o.residual,
            }
        return res

    def _get_has_attachments(self, cr, uid, ids, name, args, context=None):
        res = {}
        attachment_obj = self.pool.get('ir.attachment')
        for invoice_id in ids:
            res[invoice_id] = bool(attachment_obj.search(cr, uid, [
                    ('res_model', '=', 'account.invoice'),
                    ('res_id', '=', invoice_id),
                ], context=context))
        return res

    def _get_invoice_ids_by_ir_attachment_ids(self, cr, uid, ids, context=None):
        res = {}
        attachment_ids = self.pool.get('ir.attachment').browse(cr, uid, ids,
            context=context)
        for attachment in attachment_ids:
            if attachment.res_model == 'account.invoice':
                res[attachment.res_id] = True
        return res.keys()

    def _get_custom_export_notification_id(self, cr, uid, ids, name, args, context=None):
        res = {}
        notification_obj = self.pool.get('custom.export.notification')
        for inv_id in ids:
            notification_ids = notification_obj.search(cr, uid, [('invoice_id', '=', inv_id)], context=context)
            res[inv_id] = notification_ids[0] if notification_ids else None
        return res

    def _get_invoice_ids_by_custom_export_notification_ids(self, cr, uid, ids, context=None):
        res = {}
        entry_ids = self.pool.get('custom.export.notification').browse(cr, uid, ids,
            context=context)
        for e in entry_ids:
            res[e.invoice_id.id] = True
        return res.keys()

    def _get_journal_match(self, cr, uid, invoice, context=None):
        position = invoice.fiscal_position
        if position:
            if invoice.type == 'in_invoice':
                if not position.default_purchase_journal_id or \
                   position.default_purchase_journal_id.id != invoice.journal_id.id:
                    return False
            elif invoice.type == 'in_refund':
                if not position.default_purchase_refund_journal_id or \
                   position.default_purchase_refund_journal_id.id != invoice.journal_id.id:
                    return False
            elif invoice.type == 'out_invoice':
                if not position.default_sale_journal_id or \
                   position.default_sale_journal_id.id != invoice.journal_id.id:
                    return False
            elif invoice.type == 'out_refund':
                if not position.default_sale_refund_journal_id or \
                   position.default_sale_refund_journal_id.id != invoice.journal_id.id:
                    return False
        return True

    def _check_vat_and_fiscal_code(self, cr, uid, invoice, context=None):
        country_code = invoice.partner_id.country_id.code if invoice.partner_id.country_id else None
        is_company = invoice.partner_id.is_company
        if country_code and country_code in UE_CODES:
            if invoice.type in ('in_refund', 'in_invoice'):
                if not invoice.partner_id.vat:
                    return False
            elif invoice.type in ('out_invoice', 'out_refund'):
                if is_company and not invoice.partner_id.vat:
                    return False
                elif not is_company and not invoice.partner_id.fiscal_code:
                    return False
        return True

    def _get_invoice_info(self, cr, uid, ids, name, args, context=None):
        res = {}
        p_order_obj = self.pool.get('purchase.order')
        for o in self.browse(cr, uid, ids, context=context):
            p_order_ids = set()
            for picking in o.picking_ids:
                if picking.purchase_id:
                    p_order_ids.add(picking.purchase_id.id)
            for order in o.purchase_ids:
                p_order_ids.add(order.id)
            terms = any(order.notes for order in p_order_obj.browse(cr, uid, list(p_order_ids), context))
            text = []
            # ORDER CONDITIONS
            conditions = []
            for order in p_order_obj.browse(cr, uid, list(p_order_ids), context):
                if order.notes and order.notes.strip():
                    conditions.append('[%s] %s' % (order.name, order.notes.strip()))
            cond_text = ' - '.join(conditions)
            text.append(_('Order conditions: %s') % cond_text) if conditions else ''
            # FISCAL CHECKS
            country_code = o.partner_id.country_id.code if o.partner_id.country_id else None
            if not country_code:
                text.append(_('Missing country in partner address.'))
            if not self._get_journal_match(cr, uid, o, context):
                text.append(
                    _('The journal of the invoice fiscal position does not match the selected journal.'))
            if not self._check_vat_and_fiscal_code(cr, uid, o, context):
                text.append(
                    _('Missing VAT or fiscal code in partner address.'))
            if o.type[:2] == 'in':
                orders = p_order_obj.browse(cr, uid, list(p_order_ids), context)
            else:
                orders = o.rel_order_ids
            # MARKETPLACE CKECKS
            if hasattr(o, 'marketplace_id') and o.marketplace_id:
                text.append(
                    _('This invoice will be payed through marketplace: %s') % o.marketplace_id.name)
            res[o.id] = {
                'purchase_order_ids': list(p_order_ids),
                'has_orders': bool(p_order_ids), # TODO: espandere con un OR dentro al bool per le vendite
                'has_order_terms_and_conditions': terms,
                'warning_message': '\n'.join([t for t in text]),
                'rel_orders_origin': ', '.join([order.origin or '' for order in orders])
            }
        return res

    def _get_margin_scheme_tax_line_ids(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            exclude_ids = []
            if o.fiscal_position and o.fiscal_position.is_margin_scheme:
                exclude_ids.append(o.fiscal_position.sale_margin_scheme_tax_on_margin.tax_code_id.id)
                exclude_ids.append(o.fiscal_position.sale_margin_scheme_tax_on_untaxed.tax_code_id.id)
            res[o.id] = [line.id for line in o.tax_line if line.tax_code_id.id not in exclude_ids]
        return res

    _columns = {
        'rel_orders_origin': fields.function(_get_invoice_info, type='char', multi='_get_invoice_info',
            string='Orders Origin'),
        'warning_message': fields.function(_get_invoice_info, type='text', multi='_get_invoice_info',
            string='Warning Message'),
        'purchase_ids': fields.many2many('purchase.order', 'purchase_invoice_rel', 'invoice_id',
            'purchase_id', 'Purchase Orders'),
        'purchase_order_ids': fields.function(_get_invoice_info, type='one2many', obj='purchase.order',
            multi='_get_invoice_info', string='Purchase Orders'),
        'has_orders': fields.function(_get_invoice_info, type='boolean', multi='_get_invoice_info',
            string='Has Orders'),
        'has_order_terms_and_conditions': fields.function(_get_invoice_info, type='boolean', multi='_get_invoice_info',
            string='Has Order Terms And Conditions'),
        'has_attachments': fields.function(_get_has_attachments, type='boolean',
            string='Has Attachments', store = {
                'ir.attachment':
                    (_get_invoice_ids_by_ir_attachment_ids, [], 10),
            }),
        'shipping_invoice': fields.boolean('Shipping Invoice', readonly=True,
            states={'draft': [('readonly', False)]}),
        'partner_shipping_id': fields.many2one('res.partner',
            'Delivery Address', readonly=True,
            states={'draft': [('readonly', False)]},
            # domain="[('id', 'child_of', partner_id)]",
            help="Delivery address for shipping invoice.",
            ondelete='restrict'),
        'carriage_condition_id': fields.many2one('carriage.condition',
            'Carriage condition', readonly=True,
            states={'draft': [('readonly', False)]}),
        'goods_description_id': fields.many2one('goods.description',
            'Description of goods', readonly=True,
            states={'draft': [('readonly', False)]}),
        'transportation_reason_id': fields.many2one('transportation.reason',
            'Reason for transportation', readonly=True,
            states={'draft': [('readonly', False)]}),
        'transportation_responsible_id': fields.many2one(
            'transportation.responsible', 'Transportation organized by',
            readonly=True, states={'draft': [('readonly', False)]}),
        'manual_weight': fields.float('Weight', digits=(10,2), readonly=True,
            states={'draft': [('readonly', False)]}),
        'manual_weight_net': fields.float('Net Weight', digits=(10,2),
            readonly=True, states={'draft': [('readonly', False)]}),
        'manual_volume': fields.float('Volume (m³)', digits=(10,2),
            readonly=True, states={'draft': [('readonly', False)]}),
        'number_of_packages': fields.integer('Number of packages',
            readonly=True, states={'draft': [('readonly', False)]}),
        'carrier_id': fields.many2one('delivery.carrier', string='Carrier',
            readonly=True, states={'draft': [('readonly', False)]}),
        'date_transport': fields.datetime('Transport Date'),
        'date_receipt': fields.datetime('Receipt Date'),
        'shipping_notes': fields.text('Shipping Notes', readonly=True,
            states={'draft': [('readonly', False)]}),
        'product_id': fields.related('invoice_line', 'product_id',
            type='many2one', relation='product.product', string='Product'),

        'is_margin_scheme': fields.related('fiscal_position', 'is_margin_scheme', type='boolean',
            string='Is Margin Scheme', readonly=True),
        'margin_scheme_line_ids': fields.one2many('margin.scheme.invoice.line',
            'invoice_id', string='Margin Scheme Lines'),
        'ms_amount_untaxed': fields.function(_get_ms_info, type='float',
            digits_compute=dp.get_precision('Account'), string='Subtotal',
            multi='_get_ms_info'),
        'ms_amount_tax': fields.function(_get_ms_info, type='float',
            digits_compute=dp.get_precision('Account'), string='Tax',
            multi='_get_ms_info'),
        'ms_amount_total': fields.function(_get_ms_info, type='float',
            digits_compute=dp.get_precision('Account'), string='Total',
            multi='_get_ms_info'),
        'ms_residual': fields.function(_get_ms_info, type='float',
            digits_compute=dp.get_precision('Account'), string='Balance',
            multi='_get_ms_info'),
        'commodity_code_required': fields.related('fiscal_position',
            'commodity_code_required', type='boolean',
            string='Commodity Code Required', readonly=True),
        'custom_export_notification_required': fields.related('fiscal_position',
            'custom_export_notification_required', type='boolean',
            string='Custom Export Notification Required', readonly=True),
        'include_ivoice_copy_extra_ue': fields.related('fiscal_position',
            'include_ivoice_copy_extra_ue', type='boolean',
            string='Include Invoice Copy Extra UE', readonly=True),
        'custom_export_notification_id': fields.function(_get_custom_export_notification_id, arg=None,
            fnct_inv=None, fnct_inv_arg=None, type='many2one', obj='custom.export.notification',
            string='Custom Export Notification', store = {
                'custom.export.notification':
                    (_get_invoice_ids_by_custom_export_notification_ids, [], 10),
            }),
        'move_name': fields.related('move_id', 'name', type='char', string='Move Name'),
        'invoice_number': fields.related('internal_number', type='char', string='Invoice Number'),
        'identity_document_required': fields.related('fiscal_position', 'identity_document_required', type='boolean',
            string='Identity Document Required', readonly=True),
        'identity_document_id': fields.many2one('identity.document', string='Identity Document',
            track_visibility='onchange'),
        'text_invoice_in': fields.related('fiscal_position', 'text_invoice_in', type='text',
            string='Fiscal position text to print', readonly=True),
        'text_invoice_out': fields.related('fiscal_position', 'text_invoice_out', type='text',
            string='Fiscal position text to print', readonly=True),
        'print_lot_ref': fields.related('fiscal_position', 'print_lot_ref_on_invoices', type='boolean',
            relation='rel_model', string='Print lot references on lines', readonly=True),
        'margin_scheme_tax_line_ids': fields.function(_get_margin_scheme_tax_line_ids, type='one2many',
            obj='account.invoice.tax', string='Margin Scheme Tax Lines'),
    }

    _defaults = {
        'number_of_packages': 1,
        'custom_export_notification_required': False,
    }

    def replace_lines_with_margin_lines(self, cr, uid, ids, context=None):
        margin_invoice_lines = []
        if isinstance(ids, (int, long)):
            ids = [ids]
        goods_load_line_obj = self.pool['goods.loading.register.line']
        for invoice in self.browse(cr, uid, ids, context):
            for line in invoice.invoice_line:
                if line.lot_id.purchase_mode in MARGIN_SCHEME_MODES_NOT_NEW and \
                   not line.lot_id.loaded_goods_loading_register_line_ids and 'invoice' in invoice.type:
                    raise openerp.exceptions.Warning(
                        _('Lot [%s] refers to an used item: no any used goods registrer line in loaded ' \
                          'state has been found for it. Please, check the registering of a purchase ' \
                          'receipt or invoice in order to proceed.') % line.lot_id.ref)
                if line.lot_id and goods_load_line_obj.search(
                        cr, uid, [('lot_id', '=', line.lot_id.id)]):
                    if not invoice.fiscal_position or not invoice.fiscal_position.is_margin_scheme:
                        if not invoice.company_id.out_invoice_margin_scheme_default_fiscal_position:
                            raise openerp.exceptions.Warning(
                                _('Please, set a default margin scheme fiscal position on company\'s ' \
                                  'account settings'))
                        invoice.write({
                            'fiscal_position': invoice.company_id.out_invoice_margin_scheme_default_fiscal_position.id,
                            })
                        invoice.switch_taxes_and_accounts()
                        invoice.refresh()
                        line.refresh()
                    register_line_id = goods_load_line_obj.search(
                        cr, uid, [('lot_id', '=', line.lot_id.id)],
                        order='id desc', context=context)[0]
                    register_line = goods_load_line_obj.browse(
                        cr, uid, register_line_id, context)
                    price_subtotal = line.price_subtotal
                    if invoice.type == 'out_refund':
                        register_line_obj = self.pool[
                            'goods.loading.register.line']
                        register_line_ids = register_line_obj.search(cr, uid, [
                            ('lot_id', '=', line.lot_id.id),
                            ('state', '=', 'returned')])
                        returned_lines = register_line_obj.browse(
                            cr, uid, register_line_ids)
                        if returned_lines:
                            price_subtotal = returned_lines[0].price_out
                    order_line_ids = [l.id for l in line.order_line_ids]
                    margin_invoice_lines.append((line.invoice_id, register_line, price_subtotal, order_line_ids,
                        line.lot_id))
                    line.unlink()
        # FIX mixed margin lines check
        if margin_invoice_lines:
            for line in margin_invoice_lines:
                self._create_margin_invoice_lines(cr, uid, line[0], line[1], line[2], line[3], line[4], context)
        for invoice in self.browse(cr, uid, ids, context):
            invoice.button_compute()
        return [l[0] for l in margin_invoice_lines]

    def _create_margin_invoice_lines(self, cr, uid, invoice, register_line, amount, sale_order_line_ids, lot=False,
        context=None):
        fiscal_position = invoice.fiscal_position
        if fiscal_position is None or not fiscal_position.is_margin_scheme:
            raise openerp.exceptions.Warning(
            _('The invoice has no margin scheme fiscal position!'))
        if not fiscal_position.sale_margin_scheme_tax_on_margin or \
           not fiscal_position.sale_margin_scheme_tax_on_untaxed:
           raise openerp.exceptions.Warning(
            _('Missing default margin scheme taxes on fiscal position!'))
        taxed_tax_id = fiscal_position.sale_margin_scheme_tax_on_margin.id
        untaxed_tax_id = fiscal_position.sale_margin_scheme_tax_on_untaxed.id
        margin_line_obj = self.pool.get('margin.scheme.invoice.line')
        line_obj = self.pool.get('account.invoice.line')
        lot = register_line.lot_id if register_line else lot
        product = lot.product_id
        product_name = product.name_get()[0][1]
        account_id = product.property_account_income.id
        if not account_id:
            account_id = product.categ_id.property_account_income_categ.id
        if invoice.fiscal_position:
            for line in invoice.fiscal_position.account_ids:
                if account_id == line.account_src_id.id:
                    account_id = line.account_dest_id.id
        purchase_amount = register_line.price_in if register_line else 0.0
        margin_amount = amount - purchase_amount
        if margin_amount < 0.0:
            margin_amount = 0.0
        if purchase_amount > amount:
            purchase_amount = amount
        taxable_line_id = line_obj.create(cr, uid, {
                'invoice_id': invoice.id,
                'name': '[%s] %s' % (_('Taxable'), product_name),
                'lot_id': lot.id,
                'is_margin_scheme': True,
                'product_id': product.id,
                'account_id': account_id,
                'quantity': 1.0,
                'price_unit': margin_amount,
                'invoice_line_tax_id': [(6, 0, [taxed_tax_id])],
                'order_line_ids': [(6, 0, sale_order_line_ids)]
            }, context)
        untaxable_line_id = line_obj.create(cr, uid, {
                'invoice_id': invoice.id,
                'name': '[%s] %s' % (_('Untaxable'), product_name),
                'lot_id': lot.id,
                'is_margin_scheme': True,
                'product_id': product.id,
                'account_id': account_id,
                'quantity': 1.0,
                'price_unit': purchase_amount,
                'invoice_line_tax_id': [(6, 0, [untaxed_tax_id])],
                'order_line_ids': [(6, 0, sale_order_line_ids)]
            }, context)
        invoice.button_reset_taxes()
        line_data = {
            'invoice_id': invoice.id,
            'register_line_id': register_line.id if register_line else False,
            'taxable_line_id': taxable_line_id,
            'untaxable_line_id': untaxable_line_id,
            'name': '%s %s' % (lot.name_get()[0][1], product.name_get()[0][1]),
            'type': 'invoice' if invoice.type == 'out_invoice' else 'refund',
        }
        return margin_line_obj.create(cr, uid, line_data, context)

    def button_reset_taxes(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(account_invoice, self).button_reset_taxes(cr, uid, ids, context)
        itax_obj = self.pool.get('account.invoice.tax')
        register_line_obj = self.pool.get('goods.loading.register.line')
        for invoice in self.browse(cr, uid, ids, context):
            sale_margin_invoice = False
            margin_total_amount = 0.0
            if any(line.is_margin_scheme for line in invoice.invoice_line):
                sale_margin_invoice = True
                if not invoice.fiscal_position:
                    raise openerp.exceptions.Warning(_('Please set a fiscal '\
                        'position before computing taxes and total amount!'))
            for line in invoice.invoice_line:
                if line.is_margin_scheme and not line.lot_id and line.product_id.type != 'service':
                    raise openerp.exceptions.Warning(_('Margin scheme line %s requires a lot!'
                        ) % line.product_id.name)
        return res

    def on_change_transportation_responsible(self, cr, uid, ids, transportation_responsible_id, context=None):
        # Si possono aggiungere all'onchange anche altri campi per popolare notes...
        notes =[]
        if transportation_responsible_id:
            responsible = self.pool.get('transportation.responsible').browse(cr, uid, transportation_responsible_id,
                context)
            if responsible.note:
                notes.append(responsible.note)
        if notes:
            res = {'shipping_notes': '\n'.join(notes)}
        else:
            res = {}
        return {'value': res}

    def on_change_fiscal_position(self, cr, uid, ids, fiscal_position_id, invoice_type, partner_id, letter_of_intent_id,
        date_invoice, amount_untaxed, period_id, context=None):
        value = {}
        res = super(account_invoice, self).on_change_fiscal_position(cr, uid, ids, fiscal_position_id, invoice_type,
            partner_id, letter_of_intent_id, date_invoice, amount_untaxed, period_id, context)
        if fiscal_position_id:
            position = self.pool.get('account.fiscal.position').browse(cr, uid, fiscal_position_id, context)
            value['is_margin_scheme'] = position.is_margin_scheme
            value['shipping_invoice'] = position.shipping_invoice
            value['identity_document_required'] = position.identity_document_required
            if invoice_type == 'out_invoice':
                if position.default_sale_journal_id:
                    value['journal_id'] = position.default_sale_journal_id.id
            elif invoice_type == 'in_invoice':
                if position.default_purchase_journal_id:
                    value['journal_id'] = position.default_purchase_journal_id.id
            elif invoice_type == 'out_refund':
                if position.default_sale_refund_journal_id:
                    value['journal_id'] = position.default_sale_refund_journal_id.id
            elif invoice_type == 'in_refund':
                if position.default_purchase_refund_journal_id:
                    value['journal_id'] = position.default_purchase_refund_journal_id.id
            else:
                raise openerp.exceptions.Warning(
                    _('Wrong invoice type %s') % invoice_type)
            res.setdefault('value', {}).update(value)
        return res

    def invoice_validate(self, cr, uid, ids, context=None):
        ptr_obj = self.pool.get('product.to.return')
        product_uom_obj = self.pool.get('product.uom')
        for invoice in self.browse(cr, uid, ids, context):
            if any(not line.commodity_code_id for line in invoice.invoice_line) and invoice.commodity_code_required:
                raise openerp.exceptions.Warning(_('Each line must spacify a commodity code!'))
        res = super(account_invoice, self).invoice_validate(cr, uid, ids, context)
        self.pool.get('goods.loading.register').update_from_invoices(cr, uid, ids, context)
        # Auto keep product to return on invoice confirmation
        for invoice in self.browse(cr, uid, ids, context):
            if invoice.type == 'out_invoice' and invoice.company_id.out_invoice_auto_keep_sold_product_to_return:
                for line in invoice.invoice_line:
                    if line.lot_id and line.quantity:
                        ptr_ids = ptr_obj.search(cr, uid, [
                                ('lot_id', '=', line.lot_id.id),
                                ('unknown_fate_quantity', '>', 0.0),
                            ], context=context)
                        if not ptr_ids:
                            continue
                        left_line_quantity = line.quantity
                        kept_products = []
                        for ptr in ptr_obj.browse(cr, uid, ptr_ids, context):
                            kept_price_unit = 0.0
                            if left_line_quantity <= 0.0:
                                break
                            ptr_uom = ptr.product_uom_id
                            ptr_quantity_on_line_uom = ptr.product_qty
                            if line.uos_id.id != ptr_uom.id:
                                ptr_quantity_on_line_uom = product_uom_obj._compute_qty(cr, uid, ptr_uom.id,
                                    ptr.product_qty, to_uom_id=line.uos_id.id)
                            line_quantity_ptr_uom = product_uom_obj._compute_qty(cr, uid, line.uos_id.id,
                                    left_line_quantity, to_uom_id=ptr_uom.id)
                            left_line_quantity = - (ptr_quantity_on_line_uom - left_line_quantity)
                            kept_quantity = ptr.product_qty \
                                if (ptr.product_qty - line_quantity_ptr_uom) <= 0.0 \
                                else line_quantity_ptr_uom
                            kept_products.append((0, 0, {
                                'move_from_id': ptr.move_from_id.id,
                                'reason': _('Auto created in out invoice "%s" confirmation.') % line.invoice_id.number,
                                'date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                                'product_qty': kept_quantity,
                                'price_unit': kept_price_unit,
                            }))
                        line.write({'auto_created_kept_product_to_return_ids': kept_products})
        return res




    def action_cancel(self, cr, uid, ids, context=None):
        res = super(account_invoice, self).action_cancel(cr, uid, ids, context)
        self.pool.get('goods.loading.register').cancel_from_invoices(cr, uid, ids, context)
        # Delete auto created kept product to return
        for invoice in self.browse(cr, uid, ids, context):
            if invoice.type == 'out_invoice' and invoice.company_id.out_invoice_auto_keep_sold_product_to_return:
                for line in invoice.invoice_line:
                    for kptr in line.auto_created_kept_product_to_return_ids:
                        if kptr.state == 'to_account':
                            kptr.unlink()
        return res

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        k_ids = set()
        for i in self.browse(cr, uid, ids, context):
            for l in i.invoice_line:
                if l.kept_product_id:
                    k_ids.add(l.kept_product_id.id)
        res = super(account_invoice, self).unlink(cr, uid, ids, context)
        self.pool.get('kept.product.to.return').write(cr, uid, list(k_ids), {}, context)
        return res


class account_invoice_line(Model):
    _inherit = "account.invoice.line"

    def _get_loading_register_entry_id(self, cr, uid, ids, name, args, context=None):
        res = {}
        entry_obj = self.pool.get('goods.loading.register.line')
        margin_line_obj = self.pool.get('margin.scheme.invoice.line')
        for o in self.browse(cr, uid, ids, context=context):
            entry_ids = []
            if o.invoice_id.type == 'in_invoice':
                entry_ids = entry_obj.search(cr, uid, [
                        ('invoice_line_in', '=', o.id),
                    ], context=context)
            elif o.invoice_id.type == 'out_invoice':
                margin_line_ids = margin_line_obj.search(cr, uid, [
                    '|',
                    ('taxable_line_id', '=', o.id),
                    ('untaxable_line_id', '=', o.id),
                    ], context=context)
                if margin_line_ids:
                    entry_ids = [margin_line_obj.browse(cr, uid, margin_line_ids[0], context).register_line_id.id]
            res[o.id] = entry_ids[0] if entry_ids else None
        return res

    _columns = {
        'order_line_ids': fields.many2many('sale.order.line', 'sale_order_line_invoice_rel', 'invoice_id',
            'order_line_id', 'Order Lines', readonly=True),
        'kept_product_id': fields.many2one('kept.product.to.return', string='Kept Product To Return',
            help='The link to the kept product.', ondelete='restrict'),
        # Campi richiesti per la compilazione del registro carico/scarco beni...
        'lot_id': fields.many2one('stock.production.lot', string='Lot'),
        'is_margin_scheme': fields.boolean('Margin Scheme'),
        'goods_loading_register_entry_id': fields.function(_get_loading_register_entry_id, type='many2one',
            obj='goods.loading.register.line', string='Goods Loading Register Entry'),
        'commodity_code_id': fields.many2one('invoice.line.commodity.code', string='Commodidty Code'),
        'date_invoice': fields.related('invoice_id', 'date_invoice', type='date', string='Invoice Date', readonly=True),
        'invoice_type': fields.related('invoice_id', 'type', type='selection', string='Invoice type', readonly=True,
            selection=INVOICE_TYPES),
        'auto_created_kept_product_to_return_ids': fields.many2many('kept.product.to.return',
            'account_invoice_line_auto_created_kept_product_to_return_rel', 'line_id', 'kept_product_id',
            string='Auto created kept product to return'),
    }

    _defaults = {
        'is_margin_scheme': False,
    }

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        k_ids = set()
        for l in self.browse(cr, uid, ids, context):
            if l.kept_product_id:
                k_ids.add(l.kept_product_id.id)
        res = super(account_invoice_line, self).unlink(cr, uid, ids, context)
        self.pool.get('kept.product.to.return').write(cr, uid, list(k_ids), {}, context)
        return res


    def on_change_is_margin_scheme(self, cr, uid, ids, is_margin_scheme,
        product_id, fiscal_position_id=False, qty=1,
        partner_id=False, uom_id=False, date_order=False, invoice_type=False,
        context=None):
        fiscal_position_obj = self.pool.get('account.fiscal.position')
        tax_obj = self.pool.get('account.tax')
        pricelist_obj = self.pool.get('product.pricelist')
        product_obj = self.pool.get('product.product')
        value = {}
        fpos = fiscal_position_id and fiscal_position_obj.browse(cr, uid,
                fiscal_position_id, context=context) or None
        tax_ids = []
        if is_margin_scheme and fpos:
            if invoice_type == 'in_invoice' and fpos.purchase_margin_scheme_tax:
                tax_ids.append(fpos.purchase_margin_scheme_tax.id)
            elif invoice_type == 'out_invoice' and fpos.sale_margin_scheme_tax_on_margin:
                tax_ids.append(fpos.sale_margin_scheme_tax_on_margin.id)
            value['invoice_line_tax_id'] = [(6, 0, tax_ids)]
        elif not is_margin_scheme and product_id:
            product = product_obj.browse(cr, uid, product_id, context)
            # TODO: Gestire i casi sulle note di credito
            if invoice_type in ('in_invoice', 'in_refund'):
                taxes = tax_obj.browse(cr, uid, map(lambda x: x.id,
                    product.supplier_taxes_id))
            else:
                taxes = tax_obj.browse(cr, uid, map(lambda x: x.id,
                    product.taxes_id))

            tax_ids = fiscal_position_obj.map_tax(cr, uid, fpos, taxes)
            margin_tax_ids = (
                fpos.sale_margin_scheme_tax_on_margin.id,
                fpos.sale_margin_scheme_tax_on_untaxed.id,
                fpos.purchase_margin_scheme_tax.id,
            )
            margin_tax_ids = filter(lambda i: i, margin_tax_ids)
            if margin_tax_ids and any(tax_id in margin_tax_ids for tax_id in tax_ids):
                tax_ids = [tax.id for tax in taxes]
            value['invoice_line_tax_id'] = [(6, 0, tax_ids)]
        return {
            'value': value,
        }

    def product_id_change(self, cr, uid, ids, product, uom_id, qty=0, name='',
        type='out_invoice', partner_id=False, fposition_id=False,
        price_unit=False, currency_id=False, context=None, company_id=None):
        res = super(account_invoice_line, self).product_id_change(cr, uid, ids,
            product, uom_id, qty, name, type, partner_id, fposition_id,
            price_unit, currency_id, context, company_id)
        fpos_obj = self.pool.get('account.fiscal.position')
        fpos = fposition_id and fpos_obj.browse(cr, uid, fposition_id,
            context=context) or False
        if fpos:
            res['value']['is_margin_scheme'] = fpos.is_margin_scheme
        return res


class invoce_line_commodity_code(Model):
    _name = "invoice.line.commodity.code"
    _description = "Invoice Line Commodity Code" # Codice T.A.R.I.C.

    _columns = {
        'code': fields.char('Code', size=32, required=True),
        'name': fields.char('Name', size=128, required=True),
        'description': fields.text('Description'),
    }
    _order = 'code asc'

    _sql_constraints = [
        ('code_unique', 'unique(code)', _('Each code must be unique!'))
    ]

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        return [(r.id, "[%s] %s" % (r.code,
            r.name)) for r in self.browse(cr, uid, ids, context=context)]
