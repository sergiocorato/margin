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

import datetime as dt
import openerp.exceptions
import openerp.addons.decimal_precision as dp

from openerp.osv import fields
from openerp.osv.orm import Model

from openerp.tools.translate import _
from openerp.addons.techplus_base.tools import number_to_it_text
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

RESPONSIBLE_TYPES = [
    ('company', 'Company'),
    ('carrier', 'Carrier'),
    ('recipient', 'Recipient'),
]

TRANSPORT_DOCUMENT_STATES = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('delivered', 'Delivered'),
]

TRANSPORTATION_REASONS = [
    ('sale', 'Sale'), # Vendita
    ('purchase', 'Purchase'), # Acquisto
    ('withdrawal', 'Withdrawal'), # Recesso
    ('loan', 'Loan for use'), # Comodato d'uso
    ('sale_or_return', 'Sale or return'), # Conto visione
    ('sale_on_consignment', 'Sale on consignment'), # Conto vendita
    ('repair', 'Repair'), # Riparazione
    ('tolling', 'Tolling'), # Conto Lavoro
    ('on_consignment', 'On Consignment'), # Conto Deposito
    ('return', 'Return'), # Reso
    ('replacement', 'Replacement') # Sostituzione
]

TRASPORTATION_REASONS_DICT = dict(TRANSPORTATION_REASONS)


class carriage_condition(Model):
    _name = "carriage.condition"
    _description = "Carriage Condition"
    _columns = {
        'name':fields.char('Carriage Condition', size=64, required=True,
            readonly=False),
        'incoterm_code': fields.char('Code', size=3, required=True, help="Code for Incoterms"),
        'note': fields.text('Note'),
    }


class goods_description(Model):
    _name = 'goods.description'
    _description = "Description of Goods"

    _columns = {
        'name':fields.char('Description of Goods', size=64, required=True,
            readonly=False),
        'note': fields.text('Note'),
    }


class transportation_reason(Model):
    _name = 'transportation.reason'
    _description = 'Reason for transportation'

    _columns = {
        'name':fields.char('Reason for Transportation', size=64, required=True,
            readonly=False),
        'note': fields.text('Note'),
        'reason': fields.selection(TRANSPORTATION_REASONS, string='Reason'),
    }

# TODELETE: BEGIN
class transportation(Model):
    _name = 'transportation'
    _description = 'Transportation organized by'

    _columns = {
        'name':fields.char('Transportation organized by', size=64, required=True,
            readonly=False),
        'note': fields.text('Note'),
    }

transportation()
# TODELETE: END


class transportation_responsible(Model):
    _name = 'transportation.responsible'
    _description = 'Transportation organized by'

    _columns = {
        'name':fields.char('Transportation organized by', size=64, required=True,
            readonly=False),
        'note': fields.text('Note'),
        'hide_responsible_address': fields.boolean('Hide Responsible Address'),
        'responsible_type': fields.selection(RESPONSIBLE_TYPES, string='Responsible Type'),
    }


class transport_document(Model):
    _name = 'transport.document'
    _description = "Transport Document"
    _inherit = ['filestore', 'mail.thread', "check.bypass.mixin"]
    _rec_name = 'file_name'

    def _default_company(self, cr, uid, context=None):
        return self.pool.get('res.company')._company_default_get(cr, uid,
            'transport.document', context=context)

    def _data_get(self, cr, uid, ids, name, arg, context=None):
        return super(transport_document, self)._data_get(
            cr, uid, ids, name, arg, context)

    def _data_set(self, cr, uid, id, name, value, arg, context=None):
        return super(transport_document, self)._data_set(
            cr, uid, id, name, value, arg, context)

    def _get_date_shipping_string(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            if o.date_shipping:
                res[o.id] = dt.datetime.strptime(o.date_shipping,
                    DEFAULT_SERVER_DATETIME_FORMAT).date().strftime('%d/%m/%Y')
            else:
                res[o.id] = ''
        return res
    def _get_picking_line_ids(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            move = []
            for picking in o.picking_ids:
                for move_line in picking.move_lines:
                    move.append(move_line.id)
            res[o.id] = move
        return res

    def _get_to_be_invoiced(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = any(p.invoice_state == '2binvoiced'
                for p in o.picking_ids)
        return res

    def _search_to_be_invoiced(self, cr, uid, obj, name, args, context=None):
        cr.execute("SELECT DISTINCT transport_document_id FROM stock_picking "
            "WHERE transport_document_id IS NOT NULL AND "
            "invoice_state = '2binvoiced'")
        return [('id', 'in', [d[0] for d in cr.fetchall()])]

    def _get_sale_value(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            amount = 0.0
            goods_dropped_value_lines = 0
            currency_id = None
            errors = []
            for picking in o.picking_ids:
                if not currency_id and picking.currency_id:
                    currency_id = picking.currency_id.id
                else:
                    if picking.currency_id and \
                        picking.currency_id.id != currency_id:
                        errors.append('Picking %s has different currency. ' \
                                'Can\'t display Sale Value!' % picking.name)
                amount += picking.goods_value
                goods_dropped_value_lines += picking.goods_dropped_value_lines
            res[o.id] = {
                'goods_value': amount,
                'goods_dropped_value_lines': goods_dropped_value_lines,
                'currency_id': currency_id,
                'goods_value_error': '; '.join(errors) or '',
            }
        return res

    # def _get_user_id(self, cr, uid, ids, name, args, context=None):
    #     res = {}
    #     for o in self.browse(cr, uid, ids, context=context):
    #         res[o.id] = uid
    #     return res

    def _get_insured_value_text(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context=context):
            res[o.id] = number_to_it_text(o.insured_value) if o.insured_value else ''
        return res

    def _get_warning_message(self, cr, uid, ids, name, args, context=None):
        return self.pool.get('transport.document').get_warning_message(cr, uid, ids, name, args, context)

    _columns = {
        # 'user_id': fields.function(_get_user_id, type='many2one', obj='res.users', string='User'),
        'state': fields.selection(TRANSPORT_DOCUMENT_STATES, string='Status',
            readonly=True, track_visibility='onchange'),

        'company_id': fields.many2one('res.company', 'Company', required=True),

        'customer_id': fields.many2one('res.partner', string='Cessionary',
            required=True, states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }, track_visibility='onchange'),
        'partner_id': fields.many2one('res.partner', string='Destination',
            required=True, states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }, track_visibility='onchange'),

        'picking_ids': fields.one2many('stock.picking.out',
            'transport_document_id', string='Delivery Orders', states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),
        'picking_line_ids': fields.function(_get_picking_line_ids,
            type='many2many', obj='stock.move', string='Picking Lines'),

        'name': fields.char('Number', size=64, readonly=True,
            track_visibility='onchange'),
        'date_shipping': fields.datetime('Shipping Date', states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),
        'date_receipt': fields.datetime('Receipt Date', states={
                'delivered': [('readonly', True)],
            }),

        'carriage_condition_id': fields.many2one('carriage.condition',
            'Carriage condition', states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),
        'goods_description_id': fields.many2one('goods.description',
            'Description of goods', states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),
        'transportation_reason_id': fields.many2one('transportation.reason',
            'Reason for transportation', states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),
        'transportation_responsible_id': fields.many2one(
            'transportation.responsible',
            'Transportation organized by', states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),
        'manual_weight': fields.float('Weight', digits=(10,2), states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),
        'manual_weight_net': fields.float('Net Weight', digits=(10,2), states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),
        'manual_volume': fields.float('Volume (m³)', digits=(10,2), states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),

        'number_of_packages': fields.integer('Number of packages', states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),
        'carrier_id': fields.many2one('delivery.carrier', string='Carrier'),

        'shipping_notes': fields.text('Shipping Notes', states={
                'confirmed': [('readonly', True)],
                'delivered': [('readonly', True)],
            }),
        'origin': fields.char(string='Origin', size=256),
        'person_delegated_for_picking': fields.many2one('res.partner',
            string='Person delegated for picking'),
        # source file
        'attached_document_delegation': fields.function(_data_get,
            arg='attached_document_delegation',
            fnct_inv=_data_set, fnct_inv_arg='attached_document_delegation',
            string='Delegation Document', type="binary", nodrop=True),
        'attached_document_delegation_name': fields.char('Source File Name',
            size=256),
        'attached_document_delegation_size': fields.integer('Source File Size'),
        'attached_document_delegation_db_fdata': fields.binary(
            'Source File Database Data'),
        'attached_document_delegation_stored_fname': fields.char(
            'Source File Stored Filename', size=256),

        # strings
        'date_shipping_string': fields.function(_get_date_shipping_string,
            type='char', string='Shipping Date'),
        'partner_delivery_notes': fields.related('partner_id', 'delivery_notes',
            string='Delivery Notes', type='text', readonly=True),

        # accounting
        'to_be_invoiced': fields.function(_get_to_be_invoiced, type='boolean',
            fnct_search=_search_to_be_invoiced, string='To Be Invoiced',
            readonly=True),

        #sale
        'goods_value': fields.function(_get_sale_value, type='float',
            string='Value of goods', readonly=True,
            multi='_get_sale_value'),
        'goods_dropped_value_lines': fields.function(_get_sale_value,
            type='integer', string='Lines with no sale order',
            multi='_get_sale_value', readonly=True,
            digits_compute=dp.get_precision('Account')),
        'currency_id': fields.function(_get_sale_value, type='many2one',
            multi='_get_sale_value', obj='res.currency', string='Currency'),
        'goods_value_error': fields.function(_get_sale_value,
            type='text', multi='_get_sale_value', string='Error'),
        'insured_value': fields.float('Insured Value',
            digits_compute=dp.get_precision('Account')),
        # 'insured_value_text': fields.char('Insured Value Text', size=256),
        'insured_value_text': fields.function(_get_insured_value_text,
            type='char', string='Insured Value Text', store=True),
        'warning_message': fields.function(_get_warning_message, type='text', string='Warning Message'),
    }

    def get_warning_message(self, cr, uid, ids, name, args, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context):
            res[o.id] = ''
        return res

    def on_change_carrier_id(self, cr, uid, ids, carrier_id, context=None):
        value = {
            'carriage_condition_id': None,
            'goods_description_id': None,
            'transportation_reason_id': None,
            'transportation_responsible_id': None,
        }
        if carrier_id:
            carrier = self.pool.get('delivery.carrier').browse(cr, uid, carrier_id, context)
            value['carriage_condition_id'] = carrier.carriage_condition_id.id
            value['goods_description_id'] = carrier.goods_description_id.id
            value['transportation_reason_id'] = carrier.transportation_reason_id.id
            value['transportation_responsible_id'] = carrier.transportation_responsible_id.id
        return{'value': value}

    def on_change_partner_id(self, cr, uid, ids, partner_id, context=None):
        if partner_id:
            partner = self.pool.get('res.partner').read(cr, uid,
                partner_id, ['delivery_notes'], context=context)
            return {'value': {
                'partner_delivery_notes': partner['delivery_notes'],
            }}
        return {'value': {
            'partner_delivery_notes': None,
        }}

    _defaults = {
        'state': 'draft',
        'company_id': _default_company,
        'date_shipping': fields.date.context_today,
    }

    def _get_filestores(self):
        filestores = {
            'attached_document_delegation': {
                'file': 'attached_document_delegation',
                'file_name': 'attached_document_delegation_name',
                'file_size': 'attached_document_delegation_size',
                'db_fdata': 'attached_document_delegation_db_fdata',
                'stored_fname': 'attached_document_delegation_stored_fname',
            }
        }
        filestores.update(super(transport_document, self)._get_filestores())
        return filestores

    def _check_pickings(self, cr, uid, document, context):
        for p in document.picking_ids:
            if p.partner_id and p.partner_id.id != document.partner_id.id:
                raise openerp.exceptions.Warning(
                    _('Delivery orders must have the same destination!'))
            if p.customer_id and p.customer_id.id != document.customer_id.id:
                raise openerp.exceptions.Warning(
                    _('Delivery orders must have the same customer!'))
        return True


    def create(self, cr, uid, vals, context=None):
        doc_id = super(transport_document, self).create(cr, uid, vals, context)
        doc = self.browse(cr, uid, doc_id, context)
        self._check_pickings(cr, uid, doc, context)
        return doc_id

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        super(transport_document, self).write(cr, uid, ids, vals, context)
        for doc in self.browse(cr, uid, ids, context):
            self._check_pickings(cr, uid, doc, context)
        return True

    def legend_get(self, cr, uid, view_type=None, view_id=None, context=None):
        from techplus_base.tools import get_view_xml_id
        view_xml_id = get_view_xml_id(cr, 'techplus_l10n_it_sale', self._name,
            view_type, view_id)
        if view_xml_id == 'transport_document_tree':
            return [
                ('blue', _('Draft')),
                ('green', _('Delivered')),
            ]
        return []

    def state_draft_set(self, cr, uid, ids, *args):
        return self.write(cr, uid, ids, {'state': 'draft'})

    def state_confirmed_set(self, cr, uid, ids, *args):
        for document in self.browse(cr, uid, ids):
            vals = {'state': 'confirmed'}
            if not document.number_of_packages:
                raise openerp.exceptions.Warning(
                    _('Number of packages field is required!'))
            if not document.name:
                vals['name'] = self.pool.get('ir.sequence').get(cr, uid,
                    'stock.ddt')
            if not document.date_shipping:
                vals['date_shipping'] = dt.date.today().strftime(
                    DEFAULT_SERVER_DATE_FORMAT)
            self.write(cr, uid, ids, vals)
        return True

    def state_delivered_set(self, cr, uid, ids, *args):
        for document in self.browse(cr, uid, ids):
            vals = {'state': 'delivered'}
            if not document.date_receipt:
                d = dt.datetime.today()
                vals['date_receipt'] = dt.datetime(d.year, d.month, d.day, 12
                    ).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            self.write(cr, uid, ids, vals)
        return True

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        return [
            (r.id, "%s%s" % (r.name if r.name else _('Transport Document Draft: '),
                r.partner_id.name if not r.name else '')) for r in self.browse(
                cr, uid, ids, context=context)]

    def name_search(self, cr, uid, name='', args=None, operator='ilike',
        context=None, limit=10):
        if not args:
            args = []
        ids = []

        if name:
            partner_ids = self.pool.get('res.partner').search(cr, uid,
                [('name', 'ilike', name)], limit=limit, context=context)
            ids = self.search(cr, uid, [
                    '|',
                    ('partner_id', 'in', partner_ids),
                    ('name', 'ilike', name)
                ] + args, limit=limit, order='create_date desc',
                context=context)
        else:
            ids = self.search(cr, uid, [] + args,
                limit=limit, order='create_date desc', context=context)

        return self.name_get(cr, uid, ids, context)

    def unlink(self, cr, uid, ids, context=None):
        raise openerp.exceptions.Warning(_('A transport document cannot be '
            'deleted! You can set it to Cancel'))
        return False

    def send_transport_document_by_mail(self, cr, uid, ids, context=None):
        '''
        This function opens a window to compose an email, with the transport
        document template message loaded by default
        '''
        assert len(ids) == 1, 'This option should only be used for a single id \
                                at a time.'
        ir_model_data = self.pool.get('ir.model.data')
        try:
            template_id = ir_model_data.get_object_reference(cr, uid,
                'techplus_l10n_it_sale', 'email_template_transport_document')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference(cr, uid,
                'mail', 'email_template_transport_document')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict(context)
        ctx.update({
            'default_model': 'transport.document',
            'default_res_id': ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'privacy_sent': True
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }
