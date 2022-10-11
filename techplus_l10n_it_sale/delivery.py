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

from .transport_document import RESPONSIBLE_TYPES

CARRIAGE_TYPES = [
    ('picking_from_stock', 'Picking From Stock'),
    ('uninsured_shipments', 'Uninsured Shipments'),
    ('insured_shipments', 'Insured Shipments')
]

class delivery_carrier(Model):
    _inherit = "delivery.carrier"

    _columns = {
        'carriage_condition_id': fields.many2one('carriage.condition', 'Carriage condition'),
        'goods_description_id': fields.many2one('goods.description', 'Description of goods'),
        'transportation_reason_id': fields.many2one('transportation.reason', 'Reason for transportation'),
        'transportation_responsible_id': fields.many2one('transportation.responsible',
            'Transportation organized by'),
        'responsible_type': fields.related('transportation_responsible_id', 'responsible_type', type='selection',
            string='Responsible Type', selection=RESPONSIBLE_TYPES, readonly=True),
        'type': fields.selection(CARRIAGE_TYPES, string='Type', required=True),
    }

    _defaults = {
        'type': 'uninsured_shipments',
    }