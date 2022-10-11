# -*- coding: utf-8 -*-
##############################################################################
#
#    Tech Plus l10n it Sale
#    Copyright (C) Tech Plus srl (<http://www.techplus.it>).
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
from openerp.osv.orm import TransientModel

from openerp.tools.translate import _


class change_sale_order_tax_wizard(TransientModel):
    _name = "change.sale.order.tax.wizard"

    _columns = {
        'tax_ids': fields.many2many('account.tax',
            'change_sale_order_tax_wizard_taxes_rel', 'wizard_id', 'tax_id',
            string='New Taxes',
            domain="[('type_tax_use', 'in', ('sale', 'all'))]"),
        'order_id': fields.many2one('sale.order', string='Order',
            required=True, readonly=True),
        'order_line_ids': fields.many2many('sale.order.line',
            'change_sale_order_tax_wizard_lines_rel', 'wizard_id', 'line_id',
            string='Order Lines', domain="[('order_id', '=', order_id)]"),
    }

    def default_get(self, cr, uid, fields=None, context=None):
        if not context or not context.get('active_id'):
            raise openerp.exceptions.Warning(
                _('"active_id" not found in "context!"'))
        order_id = context.get('active_id')

        line_ids = [line.id for line in self.pool.get('sale.order').browse(cr,
            uid, order_id, context).order_line]

        return {
            'order_id': order_id,
            'order_line_ids': [(6, 0, line_ids)],
        }

    def proceed(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context)
        line_obj = self.pool.get('sale.order.line')
        if not wizard.order_line_ids:
            raise openerp.exceptions.Warning(
                _('At least one sale order line is required!'))
        tax_ids = [t.id for t in wizard.tax_ids]
        for line in wizard.order_line_ids:
            line.write({'tax_id': [(6, 0, tax_ids)]})
        return {
            'type': 'ir.actions.act_window_close',
        }

change_sale_order_tax_wizard()