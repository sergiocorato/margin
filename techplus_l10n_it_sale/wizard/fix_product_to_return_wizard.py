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


class fix_product_to_return_wizard(TransientModel):
    _name = "fix.product.to.return.wizard"

    _columns = {
        'action': fields.selection([
                ('toggle_return_type', 'Toggle Return Type'),
            ], string='Type', required=True),
    }

    def default_get(self, cr, uid, fields=None, context=None):
        return {
        }

    def proceed(self, cr, uid, ids, context=None):
        return_obj = self.pool.get('product.to.return')
        kept_obj = self.pool.get('kept.product.to.return')
        wizard = self.browse(cr, uid, ids[0], context)

        def invert_return_type(ids, obj):
            incoming_ids = []
            outgoing_ids = []
            for p in obj.browse(cr, uid, ids, context):
                if p.type == 'incoming':
                    incoming_ids.append(p.id)
                else:
                    outgoing_ids.append(p.id)
            obj.write(cr, uid, incoming_ids, {'type': 'outgoing'}, context)
            obj.write(cr, uid, outgoing_ids, {'type': 'incoming'}, context)
            return True

        if wizard.action == 'toggle_return_type':
            invert_return_type(return_obj.search(cr, uid, [], context=context), return_obj)
            invert_return_type(kept_obj.search(cr, uid, [], context=context), kept_obj)
        else:
            raise openerp.exceptions.Warning(_('Action %s not managed!') % wizard.action)
        return {
            'type': 'ir.actions.act_window_close',
        }