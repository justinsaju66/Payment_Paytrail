import werkzeug
import logging
import hmac
from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request



class PaytrailController(http.Controller):
    """Handles responses from Paytrail"""

    _success_url = "/payment/paytrail/success"
    _cancel_url = "/payment/paytrail/cancel"

    @http.route(
        [_success_url,_cancel_url],
        type="http",
        auth="public",
    )
    def paytrail_return_from_checkout(self, **data):
        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            ._get_tx_from_notification_data("paytrail", data)
        )
        self._verify_notification_signature(data, tx_sudo)
        tx_sudo._handle_notification_data("paytrail", data)
        return request.redirect("/payment/status")

    @staticmethod
    def _verify_notification_signature(notification_data, tx_sudo):

        # Retrieve the received signature from the data
        received_signature = notification_data.get("signature")
        if not received_signature:
            raise Forbidden()

        # Compare the received signature with the expected signature computed from the data
        expected_signature = tx_sudo.provider_id._paytrail_compute_signature(
            notification_data, ""
        )
        if not hmac.compare_digest(received_signature, expected_signature):
            raise Forbidden()

    @http.route(
        ["/payment/paytrail/redirect"],
        type="http",
        auth="public",
        csrf=False,
    )
    def paytrail_redirect(self, url, **kwargs):
        return werkzeug.utils.redirect(url)
