import time
import json
import unittest
from time import mktime
from datetime import datetime
from dataserv.run import app, db
from btctxstore import BtcTxStore
from dataserv.Farmer import Farmer
from email.utils import formatdate
from dataserv.app import secs_to_mins, online_farmers


class TemplateTest(unittest.TestCase):
    def setUp(self):
        app.config["SKIP_AUTHENTICATION"] = True  # monkey patch
        app.config["DISABLE_CACHING"] = True

        self.btctxstore = BtcTxStore()
        self.bad_addr = 'notvalidaddress'

        self.app = app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def gen_wallet(self):
        """Generate a testing wallet, and return its public key."""
        return self.btctxstore.get_address(
            self.btctxstore.get_key(self.btctxstore.create_wallet()))


class RegisterTest(TemplateTest):
    def get_reg_sec(self, farmer_obj):
        epoch = datetime.utcfromtimestamp(0)
        return int((farmer_obj.reg_time - epoch).total_seconds())

    def test_register(self):
        btc_addr = self.gen_wallet()
        payout_addr = self.gen_wallet()
        rv = self.app.get('/api/register/{0}/{1}'.format(btc_addr,
                                                         payout_addr))

        data = json.loads(rv.data.decode("utf-8"))
        self.assertEqual(btc_addr, data["btc_addr"])
        self.assertEqual(payout_addr, data["payout_addr"])
        self.assertEqual(rv.status_code, 200)

    def test_register_no_payout(self):
        btc_addr = self.gen_wallet()
        rv = self.app.get('/api/register/{0}'.format(btc_addr))

        # good registration
        return_data = json.loads(rv.data.decode("utf-8"))
        farmer = Farmer(btc_addr).lookup()
        expected_data = {
            "height": 0,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 100,
            "reg_time": self.get_reg_sec(farmer)
        }
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(return_data, expected_data)

        # duplicate registration
        rv = self.app.get('/api/register/{0}'.format(btc_addr))
        self.assertEqual(b"Registration Failed: Address already is registered."
                         , rv.data)
        self.assertEqual(rv.status_code, 409)

    def test_register_w_payout(self):
        btc_addr = self.gen_wallet()
        payout_addr = self.gen_wallet()
        rv = self.app.get('/api/register/{0}/{1}'.format(btc_addr,
                                                         payout_addr))
        # good registration
        return_data = json.loads(rv.data.decode("utf-8"))
        farmer = Farmer(btc_addr).lookup()
        expected_data = {
            "height": 0,
            "btc_addr": btc_addr,
            'payout_addr': payout_addr,
            "last_seen": 0,
            "uptime": 100,
            "reg_time": self.get_reg_sec(farmer)
        }
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(return_data, expected_data)

        # duplicate registration
        rv = self.app.get('/api/register/{0}/{1}'.format(btc_addr,
                                                         payout_addr))
        self.assertEqual(b"Registration Failed: Address already is registered."
                         , rv.data)
        self.assertEqual(rv.status_code, 409)

        new_btc_addr = self.gen_wallet()

        # duplicate payout address is ok
        rv = self.app.get('/api/register/{0}/{1}'.format(new_btc_addr,
                                                         payout_addr))
        return_data = json.loads(rv.data.decode("utf-8"))
        farmer = Farmer(new_btc_addr).lookup()
        expected_data = {
            "height": 0,
            "btc_addr": new_btc_addr,
            'payout_addr': payout_addr,
            "last_seen": 0,
            "uptime": 100,
            "reg_time": self.get_reg_sec(farmer)
        }
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(return_data, expected_data)

    def test_register_invalid_address(self):
        # bad address only
        rv = self.app.get('/api/register/{0}'.format(self.bad_addr))
        self.assertEqual(b"Registration Failed: Invalid Bitcoin address.",
                         rv.data)
        self.assertEqual(rv.status_code, 400)

        # good address, bad address
        btc_addr = self.gen_wallet()
        rv = self.app.get('/api/register/{0}/{1}'.format(btc_addr,
                                                         self.bad_addr))
        self.assertEqual(b"Registration Failed: Invalid Bitcoin address.",
                         rv.data)
        self.assertEqual(rv.status_code, 400)

        # bad address, good address
        payout_addr = self.gen_wallet()
        rv = self.app.get('/api/register/{0}/{1}'.format(self.bad_addr,
                                                         payout_addr))
        self.assertEqual(b"Registration Failed: Invalid Bitcoin address.",
                         rv.data)
        self.assertEqual(rv.status_code, 400)


class PingTest(TemplateTest):

    def test_ping_good(self):
        btc_addr = self.gen_wallet()
        rv = self.app.get('/api/register/{0}'.format(btc_addr))
        self.assertEqual(rv.status_code, 200)

        # now test ping
        rv = self.app.get('/api/ping/{0}'.format(btc_addr))

        # good ping
        self.assertEqual(b"Ping accepted.", rv.data)
        self.assertEqual(rv.status_code, 200)

    def test_ping_not_found(self):
        # now test ping with no registration
        btc_addr = self.gen_wallet()
        rv = self.app.get('/api/ping/{0}'.format(btc_addr))

        # bad ping
        self.assertEqual(b"Ping Failed: Farmer not found.", rv.data)
        self.assertEqual(rv.status_code, 404)

    def test_ping_invalid_address(self):
        # now test ping with no registration and invalid address
        rv = self.app.get('/api/ping/{0}'.format(self.bad_addr))

        # bad ping
        self.assertEqual(b"Ping Failed: Invalid Bitcoin address.", rv.data)
        self.assertEqual(rv.status_code, 400)


class OnlineTest(TemplateTest):

    def test_online(self):
        btc_addr = self.gen_wallet()
        rv = self.app.get('/api/register/{0}'.format(btc_addr))
        self.assertEqual(rv.status_code, 200)

        # now test ping
        self.app.get('/api/ping/{0}'.format(btc_addr))

        # get online data
        rv = self.app.get('/api/online/json')

        # see if that address is in the online status
        self.assertTrue(btc_addr in str(rv.data))

    def test_farmer_json(self):  # test could be better
        btc_addr = self.gen_wallet()
        rv = self.app.get('/api/register/{0}'.format(btc_addr))
        self.assertEqual(rv.status_code, 200)

        # get online json data
        rv = self.app.get('/api/online/json')
        self.assertTrue(btc_addr in str(rv.data))

    def test_farmer_order(self):
        addr1 = self.gen_wallet()
        addr2 = self.gen_wallet()
        addr3 = self.gen_wallet()

        # register farmers
        self.app.get('/api/register/{0}'.format(addr1))
        self.app.get('/api/register/{0}'.format(addr2))
        self.app.get('/api/register/{0}'.format(addr3))

        # set height
        self.app.get('/api/height/{0}/{1}'.format(addr1, 0))
        self.app.get('/api/height/{0}/{1}'.format(addr2, 2475))
        self.app.get('/api/height/{0}/{1}'.format(addr3, 2525))

        # get farmers
        farmers = online_farmers()
        self.assertEqual(farmers[0].btc_addr, addr3)
        self.assertEqual(farmers[1].btc_addr, addr2)
        self.assertEqual(farmers[2].btc_addr, addr1)

        # set height
        self.app.get('/api/height/{0}/{1}'.format(addr1, 5000))

        # get farmers
        farmers = online_farmers()
        self.assertEqual(farmers[0].btc_addr, addr1)


class HeightTest(TemplateTest):

    def test_farmer_set_height(self):
        # not found
        btc_addr = self.gen_wallet()
        rv = self.app.get('/api/height/{0}/1'.format(btc_addr))
        self.assertEqual(rv.status_code, 404)

        # register farmer
        self.app.get('/api/register/{0}'.format(btc_addr))

        # correct
        rv = self.app.get('/api/height/{0}/5'.format(btc_addr))
        self.assertEqual(rv.status_code, 200)
        rv = self.app.get('/api/online/json'.format(btc_addr))
        self.assertTrue(b"5" in rv.data)

        # invalid btc address
        rv = self.app.get('/api/height/{0}/1'.format(self.bad_addr))
        self.assertEqual(rv.status_code, 400)

    def test_height_limit(self):
        btc_addr = self.gen_wallet()
        self.app.get('/api/register/{0}'.format(btc_addr))

        # set height 50
        self.app.get('/api/height/{0}/{1}'.format(btc_addr, 50))
        rv = self.app.get('/api/online/json')
        self.assertTrue(b"50" in rv.data)

        # set a crazy height
        rv = self.app.get('/api/height/{0}/{1}'.format(btc_addr,
                                                       200001))
        self.assertEqual(rv.status_code, 413)
        
        # allowed max height
        rv = self.app.get('/api/height/{0}/{1}'.format(btc_addr,
                                                       200000))
        self.assertEqual(rv.status_code, 200)


class AuditTest(TemplateTest):

    def test_first_audit(self):
        btc_addr = self.gen_wallet()
        self.app.get('/api/register/{0}'.format(btc_addr))

        ha = 'c059c8035bbd74aa81f4c787c39390b57b974ec9af25a7248c46a3ebfe0f9dc8'

        # accepted audit
        rv = self.app.get('/api/audit/{0}/{1}/{2}'.format(btc_addr, 0, ha))
        self.assertEqual(rv.status_code, 201)

        # duplicate audit
        rv = self.app.get('/api/audit/{0}/{1}/{2}'.format(btc_addr, 0, ha))
        self.assertEqual(rv.status_code, 409)

    def test_invalid_response(self):
        btc_addr = self.gen_wallet()
        self.app.get('/api/register/{0}'.format(btc_addr))

        ha = 'invalid hash'
        rv = self.app.get('/api/audit/{0}/{1}/{2}'.format(btc_addr, 0, ha))
        self.assertEqual(rv.status_code, 400)

    def test_invalid_address(self):
        ha = 'c059c8035bbd74aa81f4c787c39390b57b974ec9af25a7248c46a3ebfe0f9dc8'
        rv = self.app.get('/api/audit/{0}/{1}/{2}'.format('bad', 0, ha))
        self.assertEqual(rv.status_code, 400)

    def test_farmer_not_found(self):
        btc_addr = self.gen_wallet()
        ha = 'c059c8035bbd74aa81f4c787c39390b57b974ec9af25a7248c46a3ebfe0f9dc8'
        rv = self.app.get('/api/audit/{0}/{1}/{2}'.format(btc_addr, 0, ha))
        self.assertEqual(rv.status_code, 404)

    def test_auth(self):
        app.config["SKIP_AUTHENTICATION"] = False

        btc_addr = self.gen_wallet()
        self.app.get('/api/register/{0}'.format(btc_addr))

        ha = 'c059c8035bbd74aa81f4c787c39390b57b974ec9af25a7248c46a3ebfe0f9dc8'
        rv = self.app.get('/api/audit/{0}/{1}/{2}'.format(btc_addr, 0, ha))

        self.assertEqual(rv.status_code, 401)


class AppAuthenticationHeadersTest(unittest.TestCase):

    def setUp(self):
        app.config["SKIP_AUTHENTICATION"] = False  # monkey patch
        self.app = app.test_client()
        
        self.btctxstore = BtcTxStore()
        
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def gen_wallet(self):
        """Generate a testing wallet, and return its public key."""
        return self.btctxstore.get_address(
            self.btctxstore.get_key(self.btctxstore.create_wallet()))

    def test_success(self):

        # create header date and authorization signature
        wif = self.btctxstore.create_key()
        btc_addr = self.btctxstore.get_address(wif)
        header_date = formatdate(timeval=mktime(datetime.now().timetuple()),
                                 localtime=True, usegmt=True)
        message = app.config["ADDRESS"] + " " + header_date
        header_authorization = self.btctxstore.sign_unicode(wif, message)
        headers = {"Date": header_date, "Authorization": header_authorization}
        url = '/api/register/{0}'.format(btc_addr)
        rv = self.app.get(url, headers=headers)
        data = json.loads(rv.data.decode("utf-8"))
        self.assertEqual(btc_addr, data["btc_addr"])
        self.assertEqual(rv.status_code, 200)

    def test_fail(self):
        # register without auth headers fails
        btc_addr = self.gen_wallet()
        rv = self.app.get('/api/register/{0}'.format(btc_addr))
        self.assertEqual(rv.status_code, 401)

        # register first because ping is lazy
        wif = self.btctxstore.get_key(self.btctxstore.create_wallet())
        btc_addr = self.btctxstore.get_address(wif)
        header_date = formatdate(timeval=mktime(datetime.now().timetuple()),
                                 localtime=True, usegmt=True)
        message = app.config["ADDRESS"] + " " + header_date
        header_authorization = self.btctxstore.sign_unicode(wif, message)
        headers = {"Date": header_date, "Authorization": header_authorization}
        url = '/api/register/{0}'.format(btc_addr)
        rv = self.app.get(url, headers=headers)
        self.assertEqual(rv.status_code, 200)

        # ping without auth headers fails
        time.sleep(app.config["MAX_PING"])
        rv = self.app.get('/api/ping/{0}'.format(btc_addr))
        self.assertEqual(rv.status_code, 401)

        # set height without auth headers fails
        btc_addr = self.gen_wallet()
        rv = self.app.get('/api/height/{0}/10'.format(btc_addr))
        self.assertEqual(rv.status_code, 401)


class MiscAppTest(TemplateTest):

    # making sure that at least the web server works
    def test_hello_world(self):
        rv = self.app.get('/')
        self.assertEqual(b"Hello World.", rv.data)

    # time helper
    def test_helper_time(self):
        time1 = 15
        time2 = 75
        time3 = 4000

        self.assertEqual(secs_to_mins(time1), "15 second(s)")
        self.assertEqual(secs_to_mins(time2), "1 minute(s)")
        self.assertEqual(secs_to_mins(time3), "1 hour(s)")

    # total bytes call
    def test_farmer_total_bytes(self):
        addr1 = self.gen_wallet()
        addr2 = self.gen_wallet()
        addr3 = self.gen_wallet()
        addr4 = self.gen_wallet()

        # register farmers
        self.app.get('/api/register/{0}'.format(addr1))
        self.app.get('/api/register/{0}'.format(addr2))
        self.app.get('/api/register/{0}'.format(addr3))
        self.app.get('/api/register/{0}'.format(addr4))

        # set height
        self.app.get('/api/height/{0}/{1}'.format(addr1, 0))
        self.app.get('/api/height/{0}/{1}'.format(addr2, 2475))
        self.app.get('/api/height/{0}/{1}'.format(addr3, 2525))
        self.app.get('/api/height/{0}/{1}'.format(addr4, 5000))

        # check total bytes
        rv = self.app.get('/api/total')
        self.assertTrue(b'"total_TB": 1.22' in rv.data)
        self.assertTrue(b'"total_farmers": 4' in rv.data)

    def test_get_address(self):
        rv = self.app.get('/api/address')
        self.assertEqual(rv.status_code, 200)
        data = json.loads(rv.data.decode("utf-8"))
        self.assertEqual(app.config["ADDRESS"], data["address"])
