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

from openerp.osv import fields
from openerp.osv.orm import Model

from openerp.tools.translate import _

class res_partner(Model):
    _inherit = "res.partner"

    def _get_view_id_ref(self, cr, uid, module, view):
        return self.pool.get('ir.model.data').get_object_reference(
            cr, uid, module, view)[1]

    _columns =  {
        'carriage_condition_id': fields.many2one('carriage.condition',
            'Carriage condition'),
        'goods_description_id': fields.many2one('goods.description',
            'Description of goods'),
        'transportation_reason_id': fields.many2one('transportation.reason',
            'Reason for transportation'),
        'transportation_id': fields.many2one('transportation',
            'Transportation organized by'),
        'carrier': fields.boolean('Carrier'),
        'carrier_register_number': fields.char('Register Number', size=64),
        'delivery_notes': fields.text(string='Delivery Notes'),
    }

    def view_pickings_to_invoice(self, cr, uid, ids, context=None):
        p = self.browse(cr, uid, ids[0], context)

        tree_view_id = self._get_view_id_ref(cr, uid, 'stock',
            'view_picking_in_tree')

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.in',
            'view_mode': 'tree,form',
            'view_id': False,
            'views': [
                (tree_view_id, 'tree'),
                (False, 'form'),
            ],
            'target': 'current',
            'context': {
                'search_default_partner_id': p.id,
                'search_default_to_invoice': True,
            }
        }

    def name_search(self, cr, uid, name, args=None, operator='ilike',
        context=None, limit=100):
        if not args:
            args = []
        if not context:
            context = {}
        if name:
            # Be sure name_search is symetric to name_get
            name = name.split(' / ')[-1]
            args = ['|', '|', ('name', operator, name), ('vat', operator, name),
                ('fiscal_code', operator, name)] + args
        ids = self.search(cr, uid, args, limit=limit, context=context)
        return self.name_get(cr, uid, ids, context)

res_partner()