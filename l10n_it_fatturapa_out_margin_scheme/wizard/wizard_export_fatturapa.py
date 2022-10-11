# -*- coding: utf-8 -*-
##############################################################################
#
#    Invoice Down Payment
#    Copyright (C) Ermanno Gnan (<ermannognan@gmail.com>).
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

import logging
_logger = logging.getLogger(__name__)
from openerp.addons.l10n_it_fatturapa.bindings.fatturapa_v_1_2 import (
    DatiBeniServiziType,
    DettaglioLineeType,
    DatiRiepilogoType,
    CodiceArticoloType,
)
from openerp.osv.orm import TransientModel
try:
    from unidecode import unidecode
    from pyxb.exceptions_ import SimpleFacetValueError, SimpleTypeValueError
except ImportError as err:
    _logger.debug(err)

NATURA_MARGIN_SCHEME = 'N5'
RIFERIMENTO_NORMATIVO_MARGIN_SCHEME = 'Prodotti soggetti al regime del margine rif. Art. 36 D.L. 41/95'

class WizardExportFatturapa(TransientModel):
    _inherit = "wizard.export.fatturapa"

    def _get_regular_invoice_lines(self, invoice):
        lines = super(WizardExportFatturapa, self)._get_regular_invoice_lines(invoice)
        line_to_exclude_ids = []
        for line in invoice.margin_scheme_line_ids:
            line_to_exclude_ids += [line.taxable_line_id.id, line.untaxable_line_id.id]
        return [l for l in lines if l.id not in line_to_exclude_ids]

    def _get_regular_invoice_tax_lines(self, invoice):
        lines = super(WizardExportFatturapa, self)._get_regular_invoice_tax_lines(invoice)
        return [l for l in lines if l.id in [line.id for line in invoice.margin_scheme_tax_line_ids]]

    def setDettaglioLinee(self, cr, uid, invoice, body, context=None):
        res = super(WizardExportFatturapa, self).setDettaglioLinee(
            cr, uid, invoice, body, context)
        line_no = len(body.DatiBeniServizi.DettaglioLinee) + 1
        price_precision = self.pool['decimal.precision'].precision_get(cr, uid,
                                                                       'Product Price')
        uom_precision = self.pool['decimal.precision'].precision_get(cr, uid,
                                                                     'Product Unit of Measure')
        for line in invoice.margin_scheme_line_ids:
            aliquota = 0.0
            AliquotaIVA = '%.2f' % (aliquota)
            prezzo_unitario = line.amount
            DettaglioLinea = DettaglioLineeType(
                NumeroLinea=str(line_no),
                Descrizione=unidecode(line.name.replace('\n', ' ')),
                PrezzoUnitario=('%.' + str(
                    price_precision
                ) + 'f') % prezzo_unitario,
                Quantita=('%.' + str(
                    uom_precision
                ) + 'f') % line.quantity,
                UnitaMisura=line.uos_id and (
                    unidecode(line.uos_id.name)) or None,
                PrezzoTotale='%.2f' % (line.amount * line.quantity),
                AliquotaIVA=AliquotaIVA,
                Natura=NATURA_MARGIN_SCHEME)
            if line.product_id.default_code:
                CodiceArticolo = CodiceArticoloType(
                    CodiceTipo='ODOO',
                    CodiceValore=line.product_id.default_code
                )
                DettaglioLinea.CodiceArticolo.append(CodiceArticolo)
            if line.product_id.ean13:
                CodiceArticolo = CodiceArticoloType(
                    CodiceTipo='EAN',
                    CodiceValore=line.product_id.ean13
                )
                DettaglioLinea.CodiceArticolo.append(CodiceArticolo)
            line_no += 1

            body.DatiBeniServizi.DettaglioLinee.append(DettaglioLinea)
        return res

    def setDettaglioLinea(
        self, cr, uid, line_no, line, body, price_precision, uom_precision
    ):
        DettaglioLinea = super(WizardExportFatturapa, self).setDettaglioLinea(
            cr, uid, line_no, line, body, price_precision, uom_precision
        )
        if line.invoice_line_tax_id[0].lot_purchase_mode and \
                line.invoice_line_tax_id[0].lot_purchase_mode == 'all_used_margin':
            DettaglioLinea.AliquotaIVA = '%.2f' % 0.0
            DettaglioLinea.Imposta = '%.2f' % 0.0
            DettaglioLinea.PrezzoUnitario = ('%.' + str(
                    price_precision
                ) + 'f') % line.price_unit
            DettaglioLinea.PrezzoTotale = '%.2f' % (line.price_unit * line.quantity)
            DettaglioLinea.Natura = NATURA_MARGIN_SCHEME
        return DettaglioLinea

    def setDatiRiepilogo(self, cr, uid, invoice, body, context=None):
        if context is None:
            context = {}
        res = super(WizardExportFatturapa, self).setDatiRiepilogo(cr, uid, invoice, body, context)
        if invoice.margin_scheme_line_ids:
            margin_extra_line_amount = 0
            margin_scheme_invoice_line_ids = []
            for ms_line in invoice.margin_scheme_line_ids:
                margin_scheme_invoice_line_ids.append(ms_line.taxable_line_id.id)
                margin_scheme_invoice_line_ids.append(ms_line.untaxable_line_id.id)
            for line in invoice.invoice_line:
                if line.invoice_line_tax_id[0].lot_purchase_mode \
                    and line.invoice_line_tax_id[0].lot_purchase_mode == 'all_used_margin' \
                        and line.id not in margin_scheme_invoice_line_ids:
                    margin_extra_line_amount += (line.price_unit * line.quantity)
            margin_scheme_total_amount = sum([l.amount for l in invoice.margin_scheme_line_ids])
            riepilogo = DatiRiepilogoType(
                AliquotaIVA='%.2f' % 0.0,
                ImponibileImporto='%.2f' % (
                    margin_scheme_total_amount + margin_extra_line_amount),
                Imposta='%.2f' % 0.0,
            )
            riepilogo.Natura = NATURA_MARGIN_SCHEME
            riepilogo.RiferimentoNormativo = RIFERIMENTO_NORMATIVO_MARGIN_SCHEME
            body.DatiBeniServizi.DatiRiepilogo.append(riepilogo)

        return res
