# -*- coding: utf-8 -*-
##############################################################################
#
#    Tech Plus l10n It Sale
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


class change_move_return_date_wizard(TransientModel):
    _name = "change.move.return.date.wizard"

    _columns = {
        'new_date': fields.date('New Date'),
    }

    def default_get(self, cr, uid, fields=None, context=None):
        return_date = self.pool.get('stock.move').browse(cr, uid,
            context.get('active_id'), context).return_date

        return {
            'new_date': return_date,
        }

    def proceed(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context)
        self.pool.get('stock.move').write(cr, uid, context.get('active_id'),
            {'return_date': wizard.new_date}, context)
        return {
            'type': 'ir.actions.act_window_close',
        }

change_move_return_date_wizard()