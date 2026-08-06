# -*- coding: utf-8 -*-
import os
import time
import unittest
from configparser import ConfigParser

from kb_CheckM2.kb_CheckM2Impl import kb_CheckM2

from installed_clients.WorkspaceClient import Workspace
from nose.plugins.skip import SkipTest


class kb_CheckM2Test(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("### kb_CheckM2_server_test.py loaded ###", __file__)
        print("### KB_DEPLOYMENT_CONFIG =", os.environ.get("KB_DEPLOYMENT_CONFIG"))
        print("### KB_AUTH_TOKEN set =", bool(os.environ.get("KB_AUTH_TOKEN")))
        token = os.environ.get('KB_AUTH_TOKEN', None)
        config_file = os.environ.get('KB_DEPLOYMENT_CONFIG', None)
        if not config_file or not os.path.isfile(config_file):
            raise SkipTest("KB_DEPLOYMENT_CONFIG not set; skipping integration-style server test")
        if not token:
            raise SkipTest("KB_AUTH_TOKEN not set; skipping integration-style server test")

        cls.cfg = {}
        config = ConfigParser()
        config.read([config_file])
        for nameval in config.items('kb_CheckM2'):
            cls.cfg[nameval[0]] = nameval[1]
        # Getting username from Auth profile for token
        user_id = os.environ.get('KB_AUTH_USER_ID', 'test_user')
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = {}
        cls.ctx.update({'token': token,
                        'user_id': user_id,
                        'provenance': [
                            {'service': 'kb_CheckM2',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = Workspace(cls.wsURL)
        cls.serviceImpl = kb_CheckM2(cls.cfg)
        cls.scratch = cls.cfg['scratch']
        cls.callback_url = os.environ['SDK_CALLBACK_URL']
        suffix = int(time.time() * 1000)
        cls.wsName = "test_ContigFilter_" + str(suffix)
        ret = cls.wsClient.create_workspace({'workspace': cls.wsName})  # noqa

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    # NOTE: According to Python unittest naming rules test method names should start from 'test'. # noqa
    def test_your_method(self):
        # Prepare test objects in workspace if needed using
        # self.getWsClient().save_objects({'workspace': self.getWsName(),
        #                                  'objects': []})
        #
        # Run your method by
        # ret = self.getImpl().your_method(self.getContext(), parameters...)
        #
        # Check returned data with
        # self.assertEqual(ret[...], ...) or other unittest methods
        ret = self.serviceImpl.run_checkm2_predict(self.ctx, {'workspace_name': self.wsName,
                                                             'parameter_1': 'Hello World!'})
