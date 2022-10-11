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

from openerp.osv import fields
from openerp.osv.orm import Model

from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class custom_export_notification(Model):
    _name = "custom.export.notification"
    _inherit = 'filestore'
    _description = "Custom Export Notification"
    _rec_name = 'invoice_id'

    _columns = {
        'mrn_number': fields.char('Movement Reference Number', size=32, required=True),
        'awb_number': fields.char('Airwaybill Number', size=32, required=True),
        'date': fields.date('Data', required=True),
        'invoice_id': fields.many2one('account.invoice', string='Invoice', required=True),
        'amount': fields.related('invoice_id', 'amount_total', type='float', string='Amount',
            readonly=True),
    }

    _sql_constraints = [
        ('invoice_id_uniq', 'unique(invoice_id)',
            'A custom export notification linked to this invoice already exists!'),
    ]

custom_export_notification()