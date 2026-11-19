import unittest
from unittest.mock import Mock

from charge import charge


class ChargeTest(unittest.TestCase):
    def test_retries_timeout_before_acceptance(self):
        gateway = Mock()
        gateway.charge.side_effect = [TimeoutError("request did not arrive"), "receipt-1"]

        self.assertEqual(charge(gateway, 1250), "receipt-1")
        self.assertEqual(gateway.charge.call_count, 2)
