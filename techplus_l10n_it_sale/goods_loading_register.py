# -*- coding: utf-8 -*-
##############################################################################
#
#    Tech Plus l10n it sale
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

from openerp.osv import fields
from openerp.osv.orm import Model

from openerp.tools.translate import _
from .stock import MARGIN_SCHEME_MODES_NOT_NEW

LINE_STATES = [
    ('draft', 'Draft'),
    ('loaded', 'Loaded'),
    ('unloaded', 'Unloaded'),
    ('returned', 'Returned'), # Check: viene usato?
]

FISCALYEAR_STATES = [
    ('draft','Open'),
    ('done','Closed'),
]

class goods_loading_register_line(Model):
    _name = "goods.loading.register.line"
    _description = "Goods loading/unloading register for used goods etc. Line"

    def reset_workflow(self, cr, uid, ids, context=None):
        from techplus_base.tools import reset_workflows
        reset_workflows(cr, uid, ids, 'goods.loading.register.line', [])
        return True

    def _get_next_sequence(self, cr, uid, context=None):
        return self.pool.get('ir.sequence').get(cr, uid,
            'goods.loading.registry.entry')

    def _get_margin(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            if o.price_out:
                res[o.id] = o.price_out - o.price_in
            else:
                res[o.id] = 0.0
        return res

    def _get_line_ids_from_invoice_line(self, cr, uid, ids, context=None):
        res = {}
        entry_ids = self.pool.get('account.invoice.line').browse(cr, uid, ids,
            context=context)
        for e in entry_ids:
            res[e.goods_loading_register_entry_id.id] = True
        return res.keys()

    def _get_line_ids_from_voucher_line(self, cr, uid, ids, context=None):
        res = {}
        entry_ids = self.pool.get('account.voucher.line').browse(cr, uid, ids,
            context=context)
        for e in entry_ids:
            res[e.goods_loading_register_entry_id.id] = True
        return res.keys()

    _columns = {
        'register_id': fields.many2one('goods.loading.register', string='Register', required=True, ondelete='cascade'),
        'code': fields.char('Code', size=64),
        'state': fields.selection(LINE_STATES, string='State', readonly=True),
        'lot_id': fields.many2one('stock.production.lot', string='Lot', required=True),
        'document_in': fields.char('Purchase Document', size=128),
        'identity_document_id': fields.many2one('identity.document', string='Identity Document'),
        'document_out': fields.char('Sale Document', size=128),
        'date_in': fields.date('Purchase Date'),
        'date_out': fields.date('Sale Date'),
        'price_in': fields.float('Purchase Price', digits_compute=dp.get_precision('Account')),
        'price_out': fields.float('Sale Price', digits_compute=dp.get_precision('Account')),
        'product_id': fields.related('lot_id', 'product_id', type='many2one', relation='product.product',
            string='Product', readonly=True),
        'margin': fields.function(_get_margin, type='float', digits_compute=dp.get_precision('Account'),
            string='Margin on Sale', readonly=True),
        'invoice_line_in': fields.many2one('account.invoice.line', string='Purchase Invoice Line', ondelete='cascade'),
        'invoice_line_out': fields.many2one('margin.scheme.invoice.line', string='Sale Margin Scheme Invoice Line'),
        'voucher_line_in': fields.many2one('account.voucher.line', string='Purchase Voucher Line', ondelete='cascade'),
        'invoice_in_id': fields.related('invoice_line_in', 'invoice_id', type='many2one',
            relation='account.invoice', string='Invoice In', readonly=True),
        'invoice_out_id': fields.related('invoice_line_out', 'invoice_id', type='many2one',
            relation='account.invoice', string='Invoice Out', readonly=True),
        'return_line_id': fields.many2one('goods.loading.register.line', string='Return Line'),
    }

    _defaults = {
        'state': 'draft',
        'code': None,
    }

    _order = 'code desc'

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        return [(r.id, '[%s] %s %s' % (r.code, r.lot_id.name_get()[0][1], r.lot_id.product_id.name_get()[0][1])
            ) for r in self.browse(cr, uid, ids, context=context)]

    def name_search(self, cr, uid, name='', args=None, operator='ilike',
        context=None, limit=10):
        if not args:
            args = []
        ids = []
        if name:
            ids = self.search(cr, uid, [
                    '|',
                    ('code', 'ilike', name),
                    ('lot_id.ref', 'ilike', name),
                ] + args, limit=limit, order='', context=context)
        else:
            ids = self.search(cr, uid, [] + args,
                limit=limit, order='code desc', context=context)
        return self.name_get(cr, uid, ids, context)

    def create(self, cr, uid, vals, context=None):
        line_id = super(goods_loading_register_line, self).create(cr, uid, vals, context)
        line = self.browse(cr, uid, line_id, context)
        if line.register_id.fiscalyear_id.state == 'done':
            raise openerp.exceptions.Warning(_('Can\'t add new entries to a '\
                'register having a closed fiscal year!'))
        return line_id

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(goods_loading_register_line, self).write(cr, uid, ids,
            vals, context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for l in self.browse(cr, uid, ids, context):
            if l.state != 'draft':
                raise openerp.exceptions.Warning(
                    _('Only draft entries can be unlinked! Entry: %s') % l.code)
            if l.invoice_line_in or l.invoice_line_out or l.voucher_line_in:
                error = []
                if l.invoice_line_in or l.invoice_line_out:
                    invoice_line = l.invoice_line_in if l.invoice_line_in else l.invoice_line_out
                    if invoice_line.invoice_id.state not in ('draft', 'cancel'):
                        error.append(_('invoice'))
                        error.append('ID %d' % invoice_line.invoice_id.id)
                        error.append('[%s]' % invoice_line.invoice_id.number or '')
                        error.append(invoice_line.invoice_id.partner_id.name)
                elif l.voucher_line_in.voucher_id.state not in ('draft', 'cancel'):
                    error.append(_('receipt'))
                    error.append('ID %d' % l.voucher_line_in.voucher_id.id)
                    error.append('[%s]' % l.voucher_line_in.voucher_id.number or '')
                    error.append(l.voucher_line_in.partner_id.name)
                if error:
                    error = filter(lambda i: i, error)
                    error = ' '.join(error) if error else ''
                    raise openerp.exceptions.Warning(
                        _('Can\'t delete any entry already linked to a fiscal document! Entry %s on %s'
                            ) % (l.code, error))

        return super(goods_loading_register_line, self).unlink(cr, uid, ids, context)

    def signal_draft(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        import netsvc
        wf_service = netsvc.LocalService("workflow")
        for cid in ids:
            wf_service.trg_validate(uid, 'goods.loading.register.line', cid, 'set_draft', cr)
        return True

    def set_draft(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids, context):
            if not line.code:
                line.write({'code': self._get_next_sequence(cr, uid, context)})
        return self.write(cr, uid, ids, {'state': 'draft'})

    def signal_loaded(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        import netsvc
        wf_service = netsvc.LocalService("workflow")
        for line in ids:
            wf_service.trg_validate(uid, 'goods.loading.register.line', line, 'set_loaded', cr)
        return True

    def set_loaded(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids, context):
            if not line.code:
                line.write({'code': self._get_next_sequence(cr, uid, context)})
        return self.write(cr, uid, ids, {
                'state': 'loaded',
                'date_out': None,
            })

    def signal_unloaded(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        import netsvc
        wf_service = netsvc.LocalService("workflow")
        for cid in ids:
            wf_service.trg_validate(uid, 'goods.loading.register.line', cid, 'set_unloaded', cr)
        return True

    def set_unloaded(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids, context):
            if not line.code:
                raise openerp.exceptions.Warning(
                    _('Error: no code found for entry having lot %s') % line.lot_id.name_get(cr, uid, [line.lot_id.id],
                        context)[1][0])
        return self.write(cr, uid, ids, {'state': 'unloaded'})

    def signal_returned(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        import netsvc
        wf_service = netsvc.LocalService("workflow")
        for cid in ids:
            wf_service.trg_validate(uid, 'goods.loading.register.line', cid, 'set_returned', cr)
        return True

    def set_returned(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids, context):
            if not line.code:
                raise openerp.exceptions.Warning(
                    _('Error: no code found for entry having lot %s') % line.lot_id.name_get(cr, uid, [line.lot_id.id],
                        context)[1][0])
        return self.write(cr, uid, ids, {'state': 'returned'})


class goods_loading_register(Model):
    _name = "goods.loading.register"
    _description = "Goods loading/unloading register for used goods etc."

    def _get_register_name(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = '%s - %s' % (o.fiscalyear_id.name, o.company_id.partner_id.name)
        return res

    _columns = {
        'name': fields.function(_get_register_name, type='char', string='Name',
            store=True),
        'company_id': fields.related('fiscalyear_id', 'company_id',
            type='many2one', relation='res.company', string='Company',
            readonly=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear',
            string='Fiscal Year', required=True),
        'line_ids': fields.one2many('goods.loading.register.line',
            'register_id', string='Lines'),
        'state': fields.related('fiscalyear_id', 'state',
            type='selection', selection=FISCALYEAR_STATES, string='Company',
            readonly=True),
    }

    _sql_constraints = [
        ('fiscalyear_id_uniq', 'unique(fiscalyear_id)', _('You can create just one register for each fiscal year!'))
    ]

    _order = 'name asc'

    def get_register_id_by_date(self, cr, uid, date, context=None):
        period_obj = self.pool.get('account.period')
        period_ids = period_obj.find(cr, uid, date, context=context)
        period_id = period_ids and period_ids[0] or False
        if not period_id:
            raise openerp.exceptions.Warning(_('Can\'t find period!'))
        fiscalyear = period_obj.browse(cr, uid, period_id,
            context).fiscalyear_id
        register_ids = self.search(cr, uid, [
                ('fiscalyear_id', '=', fiscalyear.id)
            ], context=context)
        if register_ids:
            return register_ids[0]
        return self.create(cr, uid, {
                'fiscalyear_id': fiscalyear.id,
            }, context)

    def check_product_and_lot(self, cr, uid, product, lot, context=None):
        if not product:
            raise openerp.exceptions.Warning(
                _('Margin scheme lines must specify a product!'))
        if product.type == 'service':
            raise openerp.exceptions.Warning(
                _('Margin scheme lines cannot specify a product having type "service"!'))
        if not lot:
            raise openerp.exceptions.Warning(
                _('Lot is required for: %s') % line.product_id.name)
        if product.id != lot.product_id.id:
            raise openerp.exceptions.Warning(
                _('The product %s doesn\'t match the lot %s') % (product.name, lot.ref))

    def update_from_receipts(self, cr, uid, voucher_ids, context=None):
        if isinstance(voucher_ids, (int, long)):
            voucher_ids = [voucher_ids]
        for voucher in self.pool.get('account.voucher').browse(cr, uid,
            voucher_ids, context):
            if voucher.type == 'purchase':
                self.update_from_purchase_receipt(cr, uid, voucher, context)
        return True

    def update_from_purchase_receipt(self, cr, uid, voucher, context=None):
        register_line_obj = self.pool.get('goods.loading.register.line')
        if not voucher.is_margin_scheme:
            return False
        if not voucher.tax_id:
            raise openerp.exceptions.Warning(
                _('Margin scheme receipts must contain a tax for margin scheme!'))
        for line in voucher.line_dr_ids:
            self.check_product_and_lot(cr, uid, line.product_id, line.lot_id, context)
            if register_line_obj.search(cr, uid, [
                    ('lot_id', '=', line.lot_id.id),
                    ('state', '=', 'loaded'),
                    '|',
                    ('invoice_line_in', '!=', False),
                    ('voucher_line_in', '!=', line.id),
                ], context=context):
                raise openerp.exceptions.Warning(
                    _('The load/unload register already contains a record in "loaded" state for lot %s'
                        ) % line.lot_id.ref)
            # line.lot_id.write({'purchase_mode': 'used'})
            register_line_ids = register_line_obj.search(cr, uid, [
                    ('voucher_line_in', '=', line.id),
                ], context=context)
            if len(register_line_ids) > 1:
                raise openerp.exceptions.Warning(
                    _('The load/unload register already contains more lines with "line_id" %s') % line.id)
            if register_line_ids:
                register_line_id = register_line_ids[0]
                register_line = register_line_obj.browse(cr, uid, register_line_id, context)
                if register_line.state != 'draft':
                    raise openerp.exceptions.Warning(
                    _('The load/unload register line for lot %s in register %s code %s must be in "draft" state!'
                      ) % (register_line.lot_id.ref, register_line.register_id.name, register_line.code))
                if register_line.lot_id.id != line.lot_id.id:
                    raise openerp.exceptions.Warning(
                        _('The load/unload register line and invoice line must have the same "lot_id"'))
                register_line.write({
                    'document_in': voucher.number,
                    'date_in': voucher.date,
                    'price_in': line.amount,
                    })
                register_line_obj.signal_loaded(cr, uid, register_line.id, context)
                if register_line.document_out:
                    register_line_obj.signal_unloaded(cr, uid, register_line.id, context)
            else:
                register_id = self.get_register_id_by_date(cr, uid, voucher.date, context),
                register_line_id = register_line_obj.create(cr, uid, {
                        'register_id': register_id,
                        'lot_id': line.lot_id.id,
                        'voucher_line_in': line.id,
                        'document_in': voucher.number,
                        'date_in': voucher.date,
                        'price_in': line.amount,
                        'identity_document_id': voucher.identity_document_id.id,
                    }, context)
                register_line_obj.signal_loaded(cr, uid, register_line_id, context)
        return True

    def cancel_from_invoices(self, cr, uid, invoice_ids, context=None):
        if isinstance(invoice_ids, (int, long)):
            invoice_ids = [invoice_ids]
        for invoice in self.pool.get('account.invoice').browse(cr, uid, invoice_ids, context):
            if invoice.type == 'out_invoice':
                self.cancel_from_out_invoice(cr, uid, invoice, context)

    def cancel_from_out_invoice(self, cr, uid, invoice, context=None):
        register_line_obj = self.pool.get('goods.loading.register.line')
        invoice_line_ids = [l.id for l in invoice.margin_scheme_line_ids]
        register_line_ids = register_line_obj.search(cr, uid, [
                ('invoice_line_out', 'in', invoice_line_ids)
            ], context=context)
        for line in register_line_obj.browse(cr, uid, register_line_ids, context):
            line.write({
                    'document_out': None,
                    'date_out': None,
                    'price_out': None,
                })
            line.signal_draft()
            line.signal_loaded()
        return True

    def update_from_invoices(self, cr, uid, invoice_ids, context=None):
        if isinstance(invoice_ids, (int, long)):
            invoice_ids = [invoice_ids]
        for invoice in self.pool.get('account.invoice').browse(cr, uid, invoice_ids, context):
            if invoice.type == 'in_invoice':
                self.update_from_in_invoice(cr, uid, invoice, context)
            elif invoice.type == 'out_refund':
                self.update_from_out_refund(cr, uid, invoice, context)
            elif invoice.type in ('out_invoice', 'in_refund'):
                self.update_from_out_invoice(cr, uid, invoice, context)
            else:
                raise openerp.exceptions.Warning(
                    _('Register cannot be update for an invoice having type "%s"!') % invoice.type)

    def update_from_out_invoice(self, cr, uid, invoice, context=None):
        register_line_obj = self.pool.get('goods.loading.register.line')
        for line in invoice.margin_scheme_line_ids:
            self.check_product_and_lot(cr, uid, line.product_id, line.lot_id, context)
            register_line_ids = register_line_obj.search(cr, uid, [
                    ('lot_id', '=', line.lot_id.id),
                    ('state', '=', 'loaded'),
                ], order="date_in desc", context=context)
            if not register_line_ids:
                raise openerp.exceptions.Warning(_('%s (%s) is not loaded on goods load/unload register!') % (
                    line.product_id.name, line.lot_id.ref))
            if len(register_line_ids) > 1:
                raise openerp.exceptions.Warning(
                    _('Consintency error: found more than one entry for lot %s in loaded state on goods register!'
                      ) % line.lot_id.ref)
            register_line_obj.write(cr, uid, register_line_ids[0], {
                    'invoice_line_out': line.id,
                    'price_out': line.amount,
                    'document_out': invoice.number,
                    'date_out': invoice.date_invoice,
                    'state': 'unloaded',
                }, context)

    def update_from_in_invoice(self, cr, uid, invoice, context=None):
        register_line_obj = self.pool.get('goods.loading.register.line')
        for line in invoice.invoice_line:
            if line.is_margin_scheme:
                self.check_product_and_lot(cr, uid, line.product_id, line.lot_id, context)
                if register_line_obj.search(cr, uid, [
                        ('lot_id', '=', line.lot_id.id),
                        ('state', '=', 'loaded'),
                        '|',
                        ('invoice_line_in', '!=', line.id),
                        ('voucher_line_in', '!=', False),
                    ], context=context):
                    raise openerp.exceptions.Warning(
                        _('The load/unload register already contains a record in "loaded" state for lot %s'
                            ) % line.lot_id.ref)
                register_line_ids = register_line_obj.search(cr, uid, [
                        ('invoice_line_in', '=', line.id),
                    ], context=context)
                if len(register_line_ids) > 1:
                    raise openerp.exceptions.Warning(
                        _('The load/unload register already contains more lines with "line_id" %s') % line.id)
                if register_line_ids:
                    register_line_id = register_line_ids[0]
                    register_line = register_line_obj.browse(cr, uid, register_line_id, context)
                    if register_line.state != 'draft':
                        raise openerp.exceptions.Warning(
                        _('The load/unload register line for lot %s in register %s code %s must be in "draft" state!'
                          ) % (register_line.lot_id.ref, register_line.register_id.name, register_line.code))
                    if register_line.lot_id.id != line.lot_id.id:
                        raise openerp.exceptions.Warning(
                            _('The load/unload register line and invoice line must have the same "lot_id"'))
                    register_line.write({
                        'document_in': invoice.number,
                        'date_in': invoice.date_invoice,
                        'price_in': line.price_subtotal,
                        })
                    register_line_obj.signal_loaded(cr, uid, register_line.id, context)
                    if register_line.document_out:
                        register_line_obj.signal_unloaded(cr, uid, register_line.id, context)
                else:
                    register_id = self.get_register_id_by_date(cr, uid, invoice.date_invoice, context),
                    register_line_id = register_line_obj.create(cr, uid, {
                            'register_id': register_id,
                            'lot_id': line.lot_id.id,
                            'invoice_line_in': line.id,
                            'document_in': invoice.number,
                            'date_in': invoice.date_invoice,
                            'price_in': line.price_subtotal,
                        }, context)
                    register_line_obj.signal_loaded(cr, uid, register_line_id, context)
        return True


    def update_from_out_refund(self, cr, uid, invoice, context=None):
        register_line_obj = self.pool.get('goods.loading.register.line')
        for line in invoice.margin_scheme_line_ids:
            self.check_product_and_lot(cr, uid, line.product_id, line.lot_id, context)
            register_id = self.get_register_id_by_date(cr, uid, invoice.date_invoice, context),
            new_register_line_id = register_line_obj.create(cr, uid, {
                    'register_id': register_id,
                    'lot_id': line.lot_id.id,
                    'invoice_line_in': line.untaxable_line_id.id,
                    'document_in': invoice.number,
                    'date_in': invoice.date_invoice,
                    'price_in': line.untaxable_line_id.price_subtotal,
                }, context)
            register_line_obj.signal_loaded(cr, uid, new_register_line_id, context)
            line.register_line_id.write({'state': 'returned'})
        return True
