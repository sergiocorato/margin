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
from datetime import date, datetime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.tools import float_compare

class return_product_to_return_wizard(TransientModel):
    _name = "return.product.to.return.wizard"

    _columns = {
        'product_qty': fields.float('Quantity', required=True,
            digits_compute=dp.get_precision('Product Unit of Measure')),
        'product_uom_id': fields.related('product_to_return_id', 'move_from_id',
            'product_uom', type='many2one', relation='product.uom',
            string='Unit of Measure', readonly=True),
        'reason': fields.text('Description', required=True),
        'date': fields.date('Date', required=True),
        'product_to_return_id': fields.many2one('product.to.return',
            string='Product To Return', required=True, readonly=True),
        'quantity_available': fields.float('Quantity Available',
            digits_compute=dp.get_precision('Product Unit of Measure'),
            readonly=True),
        'move_from_id': fields.related('product_to_return_id', 'move_from_id',
            type='many2one', relation='stock.move', string='Move From',
            readonly=True),
        'product_id': fields.related('product_to_return_id', 'product_id',
            type='many2one', relation='product.product', string='Product',
            readonly=True),
    }

    def default_get(self, cr, uid, fields=None, context=None):
        if context is None:
            context = {}
        return_obj = self.pool.get('product.to.return')
        active_model = context.get('active_model')
        active_id = context.get('active_id')
        if active_model != 'product.to.return' or not active_id:
            return {}
        return_product = return_obj.browse(cr, uid, active_id, context)
        return {
            'product_to_return_id': active_id,
            'quantity_available': return_product.unknown_fate_quantity,
            'product_uom_id': return_product.product_uom_id.id,
            'date': datetime.strftime(datetime.now().date(),
                DEFAULT_SERVER_DATE_FORMAT),
            'product_id': return_product.product_id.id,
        }

    def proceed(self, cr, uid, ids, context=None):
        return_obj = self.pool.get('product.to.return')
        wizard = self.browse(cr, uid, ids[0], context)
        if wizard.product_qty <= 0.0:
            raise openerp.exceptions.Warning(
                _('The quantity should be greater then zero!'))
        if wizard.product_qty > wizard.product_to_return_id.unknown_fate_quantity:
            p = self.pool.get('decimal.precision').precision_get(cr, uid,
                'Product Unit of Measure')
            raise openerp.exceptions.Warning(
                _('The quantity should be less or equal to %.' + str(p) + 'f!') %
                wizard.product_to_return_id.unknown_fate_quantity)
        return_obj.create_return_pickings(cr, uid,
            return_ids=wizard.product_to_return_id.id,
            quantity=wizard.product_qty, reason=wizard.reason, context=context)
        return {
            'type': 'ir.actions.act_window_close',
        }

return_product_to_return_wizard()