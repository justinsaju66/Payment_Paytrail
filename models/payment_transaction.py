import json
import uuid
import requests

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_paytrail.controllers.main import PaytrailController


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    paytrail_checkout_stamp = fields.Char(string="Paytrail checkout stamp", readonly=True)
    paytrail_checkout_account = fields.Char(string="Paytrail checkout account", readonly=True)
    paytrail_checkout_provider = fields.Char(string="Paytrail checkout provider", readonly=True)

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "paytrail":
            return res
        payload = self._paytrail_prepare_payload()
        print("payload",payload)
        token = self._paytrail_create_payment(payload)
        if token.get("status") == "error":
            raise ValidationError(token.get("message"))
        res["paytrail_url"] = f"/payment/paytrail/redirect?url={token.get('href')}"
        return res

    def _paytrail_prepare_payload(self):
        order = self.sale_order_ids[:1]
        if not order:
            raise ValidationError(_("Paytrail: Transaction must be linked to a sale order."))
        order = order[0]
        first_name, last_name = payment_utils.split_partner_name(order.partner_id.name)

        items = []
        for line in order.order_line:
            if line.product_uom_qty <= 0:
                continue
            vat = sum(line.tax_id.mapped("amount"))
            qty = int(round(line.product_uom_qty))
            price = round(line.price_total * 100 / qty)
            items.append({
                "unitPrice": price,
                "units": qty,
                "vatPercentage": vat,
                "productCode": line.product_id.default_code or str(line.product_id.id),
                "description": line.product_id.name,
                "category": line.product_id.categ_id.display_name,
            })

        return json.dumps({
            "stamp": str(uuid.uuid4()),
            "reference": self.reference,
            "amount": payment_utils.to_minor_currency_units(order.amount_total, self.currency_id),
            "currency": order.currency_id.name,
            "language": order.partner_id.lang[:2].upper() if order.partner_id.lang else "EN",
            "items": items,
            "customer": {
                "email": order.partner_id.email,
                "firstName": first_name,
                "lastName": last_name,
                "phone": order.partner_id.phone or "",
                "vatId": order.partner_id.vat or "",
            },
            "deliveryAddress": {
                "streetAddress": order.partner_shipping_id.street[:50],
                "postalCode": order.partner_shipping_id.zip,
                "city": order.partner_shipping_id.city[:30],
                "country": order.partner_shipping_id.country_id.code,
            },
            "invoicingAddress": {
                "streetAddress": order.partner_invoice_id.street[:50],
                "postalCode": order.partner_invoice_id.zip,
                "city": order.partner_invoice_id.city[:30],
                "country": order.partner_invoice_id.country_id.code,
            },
            "redirectUrls": {
                "success": f"{self.provider_id.paytrail_base_url}{PaytrailController._success_url}",
                "cancel": f"{self.provider_id.paytrail_base_url}{PaytrailController._cancel_url}",
            },
            "callbackUrls": {
                "success": f"{self.provider_id.paytrail_base_url}{PaytrailController._success_url}",
                "cancel": f"{self.provider_id.paytrail_base_url}{PaytrailController._cancel_url}",
            },
            "usePricesWithoutVat": False,
        }, separators=(",", ":"))

    def _paytrail_create_payment(self, payload):
        headers = self.provider_id._get_paytrail_headers(payload)
        print("Header=",headers)
        response = requests.post("https://services.paytrail.com/payments", headers=headers, data=payload)
        if response.status_code == 201:
            return response.json()
        try:
            return {"status": "error", "message": response.json().get("message", "Unknown error")}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        print(notification_data)
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != "paytrail" or len(tx) == 1:
            return tx
        reference = notification_data.get("checkout-reference")
        print("reference=",reference)
        if not reference:
            raise ValidationError("Paytrail: " + _("Missing transaction reference."))
        tx = self.search([("reference", "=", reference), ("provider_code", "=", "paytrail")])
        if not tx:
            raise ValidationError("Paytrail: " + _("No transaction found matching reference %s.", reference))
        return tx

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        if self.provider_code != "paytrail":
            return
        self.write({
            "provider_reference": notification_data.get("checkout-transaction-id"),
            "paytrail_checkout_stamp": notification_data.get("checkout-stamp"),
            "paytrail_checkout_account": notification_data.get("checkout-account"),
            "paytrail_checkout_provider": notification_data.get("checkout-provider"),
        })
        status = notification_data.get("checkout-status")
        if status == "ok":
            self._set_done()
        elif status in ["pending", "delayed"]:
            self._set_pending()
        elif status == "fail":
            self._set_canceled()
        else:
            self._set_error("Paytrail: " + _("Unknown payment status: %s", status))
