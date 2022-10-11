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
from ..stock import MARGIN_SCHEME_MODES_NOT_NEW

class stock_picking_out_split_margin_scheme_lines(TransientModel):
    _name = "stock.picking.out.split.margin.scheme.lines"

    _columns = {

    }

    # def default_get(self, cr, uid, fields=None, context=None):
    #     return {
    #         'type': 'type1',
    #     }

    def proceed(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context)
        picking_ids = []
        if context.get('active_model') != 'stock.picking.out':
            raise openerp.exceptions.Warning(_('Please, select one or more delivery order.'))
        picking_obj = self.pool.get('stock.picking.out')
        for picking in picking_obj.browse(cr, uid, context.get('active_ids', []), context):
            picking_state = picking.state
            picking_ids.append(picking.id)
            not_new_line_ids, new_line_ids = [], []
            for line in picking.move_lines:
                if line.prodlot_id and line.prodlot_id.purchase_mode in MARGIN_SCHEME_MODES_NOT_NEW:
                    not_new_line_ids.append(line.id)
                else:
                    new_line_ids.append(line.id)
            if not_new_line_ids and new_line_ids:
                used_items_picking_id = picking_obj.shallow_copy(cr, uid, picking.id, default={
                        'move_lines': [],
                        'origin': picking.origin,
                    }, context=context)
                self.pool.get('stock.move').write(cr, uid, not_new_line_ids, {'picking_id': used_items_picking_id},
                    context)
                # TODO: Check
                used_picking = picking_obj.browse(cr, uid, used_items_picking_id, context)

                if picking_state in ('confirmed', 'assigned'):
                    used_picking.action_confirm()
                    if picking_obj.test_assigned(cr, uid, [used_picking.id]):
                        used_picking.action_assign_wkf()
                if picking_state == 'done':
                    used_picking.action_move()
                picking_ids.append(used_picking.id)

        # TODO: controllare il flusso per portartlo come quello del picking di origine

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.out',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'target': 'current',
            'domain': [('id', 'in', picking_ids)],
        }
