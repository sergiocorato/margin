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

from openerp.osv import fields
from openerp.osv.orm import Model

from stock import MARGIN_SCHEME_MODES, MARGIN_SCHEME_MODES_NOT_NEW


class account_voucher(Model):
    _inherit = "account.voucher"

    def _get_company_default(self, cr, uid, context=None):
        return self.pool.get('res.company')._company_default_get(
            cr, uid, context=context)

    _columns = {
        'is_margin_scheme': fields.boolean('Margin Scheme'),
        'identity_document_id': fields.many2one('identity.document',
            string='Identity Document', track_visibility='onchange',
            domain="[('partner_id', '=', partner_id)]"),
    }

    _defaults = {
        'is_margin_scheme': False,
    }

    def button_refresh_voucher_lines(self, cr, uid, ids, context=None):
        voucher_line_obj = self.pool.get('account.voucher.line')

        for voucher in self.browse(cr, uid, ids, context):
            value = self.onchange_partner_id(cr, uid, [voucher.id],
                voucher.partner_id.id, voucher.journal_id.id,
                voucher.amount, voucher.currency_id.id,
                voucher.type, voucher.date, context)['value']

            line_ids = [l.id for l in voucher.line_ids]
            if line_ids:
                voucher_line_obj.unlink(cr, uid, line_ids, context)

            lines = value.get('line_cr_ids', []) + value.get('line_dr_ids', [])
            for line in lines:
                line['voucher_id'] = voucher.id
                voucher_line_obj.create(cr, uid, line, context)

        return {'type': 'ir.actions.act_window_close'}

    def proforma_voucher(self, cr, uid, ids, context=None):
        register_obj = self.pool.get('goods.loading.register')
        super(account_voucher, self).proforma_voucher(cr, uid, ids, context)
        register_obj.update_from_receipts(cr, uid, ids, context)
        return True

    def on_change_margin_scheme(self, cr, uid, ids, is_margin_scheme, context=None):
        company_id = self._get_company_default(cr, uid, context)
        company = self.pool.get('res.company').browse(cr, uid, company_id, context)
        tax_id = company.margin_account_tax_for_purchase_receipts_id
        value = {
            'tax_id': tax_id.id if tax_id and is_margin_scheme else None,
        }
        return {'value': value}

account_voucher()


class account_voucher_line(Model):
    _inherit = 'account.voucher.line'

    def _get_lading_register_entry_id(self, cr, uid, ids, name, args,
        context=None):
        res = {}
        entry_obj = self.pool.get('goods.loading.register.line')
        for o in self.browse(cr, uid, ids, context=context):
            entry_ids = entry_obj.search(cr, uid, [
                    ('voucher_line_in', '=', o.id),
                ], context=context)
            res[o.id] = entry_ids[0] if len(entry_ids) > 0 else None
        return res

    _columns = {
        'lot_id': fields.many2one('stock.production.lot', string='Lot'),
        'product_id': fields.related('lot_id', 'product_id', type='many2one',
            relation='product.product', string='Product', readonly=True),
        'goods_loading_register_entry_id': fields.function(
            _get_lading_register_entry_id, type='many2one',
            obj='goods.loading.register.line',
            string='Goods Loading Register Entry'),
        'kept_product_id': fields.many2one('kept.product.to.return',
            string='Kept Product To Return', ondelete='restrict'),
        'is_margin_scheme': fields.related('voucher_id', 'is_margin_scheme',
            type='boolean', string='Margin Scheme', readonly=True),
    }

    def on_change_lot_id(self, cr, uid, ids, lot_id, context=None):
        value = {'name': ''}
        if lot_id:
            lot = self.pool.get('stock.production.lot').browse(cr, uid,
                lot_id, context)
            value['name'] = lot.product_id.name_get()[0][1]
        return {'value': value}

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        k_ids = set()
        for l in self.browse(cr, uid, ids, context):
            if l.kept_product_id:
                k_ids.add(l.kept_product_id.id)
        res = super(account_voucher_line, self).unlink(cr, uid, ids, context)
        self.pool.get('kept.product.to.return').write(cr, uid, list(k_ids), {}, context)
        return res