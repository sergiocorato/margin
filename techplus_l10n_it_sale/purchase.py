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

import openerp.addons.decimal_precision as dp
import openerp.exceptions

from openerp.osv import fields
from openerp.osv.orm import Model

from openerp.tools.translate import _

from stock import MARGIN_SCHEME_MODES, MARGIN_SCHEME_MODES_USED, MARGIN_SCHEME_MODES_NOT_NEW

class purchase_order_line(Model):
    _inherit = "purchase.order.line"

    def _get_tax_print_description(self, cr, uid, ids, name, args,
        context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            description = ''
            for t in o.taxes_id:
                if description:
                    description += '; '
                description += t.purchase_print_name if t.purchase_print_name \
                    else t.name
            res[o.id] = description
        return res

    _columns = {
        'list_price': fields.float('Sale Price',
            digits_compute=dp.get_precision('Product Price')),
        'tax_print_description': fields.function(_get_tax_print_description,
            type='text', string='Tax Print Description'),
        'margin_scheme_type': fields.selection(MARGIN_SCHEME_MODES,
            string='Purchase Mode', required=True),
    }

    _defaults = {
        'margin_scheme_type': 'new',
    }

    def default_get(self, cr, uid, fields, context=None):
        res = super(purchase_order_line, self).default_get(cr, uid, fields, context)
        position_id = context.get('fiscal_position', None)
        if position_id:
            is_margin_scheme = self.pool.get('account.fiscal.position').browse(cr, uid, position_id, context
                ).is_margin_scheme
            if not is_margin_scheme:
                res['margin_scheme_type'] = 'new'
            else:
                res['margin_scheme_type'] = 'new_no_vat'
        return res

    def on_change_margin_scheme_type(self, cr, uid, ids, margin_scheme_type, product_id, fiscal_position_id=False,
        pricelist_id=False, qty=1, partner_id=False, uom_id=False, date_order=False, context=None):
        fiscal_position_obj = self.pool.get('account.fiscal.position')
        tax_obj = self.pool.get('account.tax')
        pricelist_obj = self.pool.get('product.pricelist')
        product_obj = self.pool.get('product.product')
        value = {}
        fpos = fiscal_position_id and fiscal_position_obj.browse(cr, uid, fiscal_position_id, context=context) or False
        if fpos and fpos.purchase_margin_scheme_tax:
            if margin_scheme_type in MARGIN_SCHEME_MODES_NOT_NEW:
                value['taxes_id'] = [(6, 0, [fpos.purchase_margin_scheme_tax.id])]
            elif margin_scheme_type in ('new',) and product_id:
                product = product_obj.browse(cr, uid, product_id, context)
                taxes = tax_obj.browse(cr, uid, map(lambda x: x.id,
                    product.supplier_taxes_id))
                tax_ids = fiscal_position_obj.map_tax(cr, uid, fpos, taxes)
                if any(tax.id == fpos.purchase_margin_scheme_tax.id for tax in tax_obj.browse(cr, uid, tax_ids,
                    context)):
                    tax_ids = [tax.id for tax in taxes]
                value['taxes_id'] = [(6, 0, tax_ids)]
        return {
            'value': value,
        }

    def onchange_product_id(self, cr, uid, ids, pricelist_id, product_id, qty, uom_id, partner_id, date_order=False,
        fiscal_position_id=False, date_planned=False, name=False, price_unit=False, margin_scheme_type=False,
        context=None):
        if not context:
            context = {}
        res = super(purchase_order_line, self).onchange_product_id(cr, uid, ids, pricelist_id, product_id, qty, uom_id,
            partner_id, date_order, fiscal_position_id, date_planned, name, price_unit, context)
        fiscal_position_obj = self.pool.get('account.fiscal.position')
        fpos = fiscal_position_id and fiscal_position_obj.browse(cr, uid, fiscal_position_id, context=context) or False
        val = res.setdefault('value', {})
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context)
            val['list_price'] = product.list_price
        else:
            val['list_price'] = 0.0
        if 'date_planned' in val and not context.get('use_date_planned'):
            del(val['date_planned'])
        if fpos and fpos.purchase_margin_scheme_tax and margin_scheme_type in MARGIN_SCHEME_MODES_NOT_NEW:
            val['taxes_id'] = [(6, 0, [fpos.purchase_margin_scheme_tax.id])]
        return res

purchase_order_line()