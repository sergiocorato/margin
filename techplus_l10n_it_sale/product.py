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

from openerp.osv import fields, osv
from openerp.osv.orm import Model


class pricelist_partnerinfo(osv.osv):
    _inherit = 'pricelist.partnerinfo'
    _columns = {
        'note': fields.char('Note', size=256),
    }

pricelist_partnerinfo()

class product_template(Model):
    _inherit = ['product.template', 'mail.thread']
    _name = "product.template"

    _columns = {
        'uom_id': fields.many2one('product.uom', 'Unit of Measure', required=True, help="Default Unit of Measure used for all stock operation.", track_visibility='onchange'),
        'uom_po_id': fields.many2one('product.uom', 'Purchase Unit of Measure', required=True, help="Default Unit of Measure used for purchase orders. It must be in the same category than the default unit of measure.", track_visibility='onchange'),
        'uos_id' : fields.many2one('product.uom', 'Unit of Sale',
            help='Sepcify a unit of measure here if invoicing is made in another unit of measure than inventory. Keep empty to use the default unit of measure.', track_visibility='onchange'),
        'no_lot_required': fields.boolean('No Lot Required on Moves'),
    }

    _defaults = {
        'no_lot_required': True,
    }

class product_product(Model):
    _inherit = "product.product"

    def _get_warning_message(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = ''
        return res

    _columns = {
        'warning_message': fields.function(_get_warning_message, type='text',
            string='Warning Message'),
    }

product_product()