import os
import re
import sys
import unittest
from StringIO import StringIO
from mock import MagicMock as Mock
from uuid import uuid4 as uuid
from ConfigParser import ConfigParser
from fabric.api import *
import gnupg

from commands import (
    Release,
    project_root,
    unittest_cmd,
    service_name,
    setconfig,
    )

from security import (
    sign_then_encrypt_file,
    decrypt_and_verify_file,
    fetch_secret,
    distribute_secret,
    DistributePlaintextError,
    NotTrustedError,
)

from main import main, fmt_version
from config import (
    init,
    make_init_config,
    config_path,
    )

class HerdSecretsTest(unittest.TestCase):

    def setUp(self):
        # set up test keys
        self.gpghome = str(uuid())
        # 2 trusted keys and one untrusted key
        self.gpg = gnupg.GPG(gnupghome="app/unittest_gnupghome")

        # set up identities
        self.my_fingerprint = u'B133D6ED48CE0666BA77881C7C039C75475A96B2'
        self.their_fingerprint = u'0FE187AE80702283E85D7241389171E911C19847'
        self.untrusted_fingerprint = u"79985D6FF6E93B008F7C2872AFBAF11DA4791002"
        self.recipients = [self.my_fingerprint, self.their_fingerprint]

        # set up test secret
        self.plainpath = str(uuid())
        self.secret_a = str(uuid())
        self.secret_b = str(uuid())
        with open(self.plainpath, 'w') as plainfile:
            plainfile.writelines([
                    "a={}\n".format(self.secret_a),
                    "b={}\n".format(self.secret_b),
                    ])

        # encrypt and sign something to me
        self.my_secret = str(uuid())
        self.my_cypherpath = str(uuid())
        self.my_cyphertext = self.gpg.encrypt(
            self.my_secret,
            self.my_fingerprint,
            sign=self.their_fingerprint,
            )
        with open(self.my_cypherpath, 'w') as my_cypherfile:
            my_cypherfile.write(self.my_cyphertext.data)

        # encrypt but don't sign something to me
        self.unverified_secret = str(uuid())
        self.unverified_cypherpath = str(uuid())
        self.unverified_cyphertext = self.gpg.encrypt(
            self.my_secret,
            self.my_fingerprint)
        with open(self.unverified_cypherpath, 'w') as unverified_cypherfile:
            unverified_cypherfile.write(self.unverified_cyphertext.data)

        # encrypt but sign with untrusted key
        self.untrusted_secret = str(uuid())
        self.untrusted_cypherpath = str(uuid())
        self.untrusted_cyphertext = self.gpg.encrypt(
            self.my_secret,
            self.my_fingerprint,
            sign=self.untrusted_fingerprint
            )
        with open(self.untrusted_cypherpath, 'w') as untrusted_cypherfile:
            untrusted_cypherfile.write(self.untrusted_cyphertext.data)

        # intercept os.system
        self.realsystem = os.system
        self.mock_system = Mock()
        os.system = self.mock_system

    def tearDown(self):
        # restore os.system
        os.system = self.realsystem

        # remove test files
        def remove(p):
            try: os.remove(p)
            except: pass
            try: os.rmdir(p)
            except: pass

        map(lambda x: remove(x), [
                self.gpghome,
                self.plainpath,
                self.my_cypherpath,
                self.unverified_cypherpath,
                self.untrusted_cypherpath,
                ])

    def test_create_signed_encrypted_secret(self):
        """ herd should create signed then encrypted secret messages """

        # happy path
        cyperpath = sign_then_encrypt_file(
            self.plainpath,
            self.recipients,
            )

        # confirm assumptions
        with open(cyperpath, 'r') as cfile, open(self.plainpath, 'r') as pfile:
            decrypted_data = self.gpg.decrypt_file(cfile)
            # it decrypts to the original text
            self.assertEqual(pfile.read(), decrypted_data.data)
            # it is trusted ultimately
            self.assertTrue(
                decrypted_data.trust_level == decrypted_data.TRUST_ULTIMATE)
            # I signed it
            self.assertEqual(decrypted_data.fingerprint, self.my_fingerprint)

    def test_distribute_secret(self):
        """ herd should only distribute encrypted messages """
        #set up
        cypherpath = sign_then_encrypt_file(self.plainpath, self.recipients)

        # excersize SUT (distribute the plainpath)
        with self.assertRaises(DistributePlaintextError):
            distribute_secret(self.plainpath)

        # confirm that os.system did not call any command
        self.assertEqual(os.system.call_count, 0)

        # excersize SUT (distribute the correct path)
        distribute_secret(cypherpath)

        # confirm that os.system called the correct scp command
        scp_cmd = "scp {} sec.iadops.com/{}".format(
            cypherpath, os.path.basename(cypherpath))
        os.system.assert_called_once_with(scp_cmd)

    def test_get_secret(self):
        """ herd should be able to download a secret file """
        # set up
        secret_name = str(uuid())

        # run SUT
        fetch_secret(secret_name)

        # confirm assumptions
        expected_str = "wget sec.iadops.com/{}".format(secret_name)
        self.mock_system.assert_called_once_with(expected_str)

    def test_decrypt_and_verify_my_secret(self):
        """ herd should decrypt and verify secrets intended for me

        Herd should also fail to decrypt secrets not intended for me. and should
        throw out secrets that don't have valid signitures from trusted keys.

        """

        # happy path
        plaintext = decrypt_and_verify_file(self.my_cypherpath)

        # confirm assumptions
        self.assertEqual(plaintext, self.my_secret)

        # no signiture
        with self.assertRaises(NotTrustedError):
            plaintext = decrypt_and_verify(self.unverified_cypherpath)

        # untrusted signiture
        with self.assertRaises(NotTrustedError):
            plaintext = decrypt_and_verify(self.untrusted_cypherpath)

        # no encryption
        with self.assertRaises(NotEncryptedError):
            plaintext = decrypt_and_verify(self.plainpath)

    @unittest.skip("Creating keys will be done manually until after 1.0")
    def test_create_key(self):
        """ Herd should create keys for the user """
        self.fail("test not implemented")

    @unittest.skip("Distributing keys will be done manually until after 1.0")
    def test_distribute_keys(self):
        """ herd should distribute your public keys """
        self.fail("test not implemented")

    @unittest.skip("Showing keys will be done manually until after 1.0")
    def test_show_keys(self):
        """ Herd needs to be able to list local keys """
        self.fail("test not implemented")

    @unittest.skip("trusting keys will be done manually until after 1.0")
    def test_trust_key(self):
        """ Herd users should be able to assert that they trust a key """
        self.fail("test not implemented")

    @unittest.skip("Revoking keys will be done manually until after 1.0")
    def test_revoke_key(self):
        """ Herd users should be able to revoke their key """
        self.fail("test not implemented")

    @unittest.skip("Revoking keys will be done manually until after 1.0")
    def test_check_revocation(self):
        """ Herd should allow revocation checking of a key by other users"""
        self.fail("test not implemented")

    @unittest.skip("Listing secrets will be done manually until after 1.0")
    def test_list_secrets(self):
        """ Herd should be able to list secrets """
        self.fail("test not implemented")

    @unittest.skip("Skipping until working on deploy command")
    def test_load_ephemeral_config(self):
        """ herd should load a config file to the ephemeral storage """
        self.fail("test not implemented")

    @unittest.skip("Skipping until working on deploy command")
    def test_deploy_with_ephemeral_config(self):
        """ herd should deploy runs with the ephemeral config """
        self.fail("test not implemented")

    @unittest.skip("Skipping until working on deploy command")
    def test_wipe_ehpemeral_config(self):
        """ herd should wipe the config file when finished with it """
        self.fail("test not implemented")


class MockRelease(Release):

    @property
    def __manifest__(self):
        manifest = """[Service]
service_port=9999
[Dependencies]
mock_deps
"""
        config = ConfigParser(allow_no_value=True)
        config.readfp(StringIO(manifest))
        return config

    def __get_host_env_pair__(self, key):
        return (key, 'mockvalue')


class HerdMainTests(unittest.TestCase):

    def test_illegal_characters(self):
        sys.argv = ['herd', 'trivial', 'a', 'b', 'c', 'd;']
        with self.assertRaises(ValueError):
            main()
        sys.argv = ['herd', 'trivial', 'a', 'b', 'c', 'd&']
        with self.assertRaises(ValueError):
            main()

        sys.argv = ['herd', 'trivial', 'a', 'b', 'c', 'd']
        try:
            main()
        except ValueError:
            self.fail("main() raised ValueError unexpectedly")

    def test_fmt_version(self):
        """ a version 5-tuple should be formatted in the 3 appropriate ways """
        self.assertEqual(fmt_version('long', (1, 2, 3, 't')), '1.2.3-t')
        self.assertEqual(fmt_version(v=(1, 2, 3, 't')), '1.2.3-t')
        self.assertEqual(fmt_version('short', (1, 2, 3, 't')), '1.2.3')
        self.assertEqual(fmt_version('major', (1, 2, 3, 't')), '1')

        # Make sure fmt has default args and can just be called with
        # appropriate exclusions
        assert fmt_version()
        assert fmt_version("long")
        assert fmt_version("short")
        assert fmt_version("major")

        with self.assertRaises(NameError):
            fmt_version('foo')

class HerdDeployTests(unittest.TestCase):

    def setUp(self):
        # mock a config... dumb config.
        self.config_path = str(uuid())
        with open(self.config_path, 'w') as config:
            config.write('[Config]\n')
            config.write('testkey=mockvalue\n')
            config.write('t2=m2\n')

        self.mock_host = 'dumb_host'
        self.mock_port = '0000'
        self.mock_image_name = 'dumb_image_name'

        # mock a release... dumb release.
        self.mock_release = MockRelease(self.mock_image_name,
                                        self.config_path,
                                        '')

    def tearDown(self):
        os.system("rm {}".format(self.config_path))

    def test_config_pairs(self):
        """
        __config_pairs__ should create a list of tuples from the config file

        """

        self.assertEqual(self.mock_release.__config_pairs__,
                         [('testkey', 'mockvalue'), ('t2', 'm2')])

    def test_docker_run_command(self):
        """
        __docker_run_command__ should build an appropriate run command

        """

        cmd = self.mock_release.__docker_run_command__(self.mock_port)
        self.assertTrue(re.search('^docker run .+', cmd))
        self.assertTrue(' -e testkey=mockvalue ' in cmd)
        self.assertTrue(' -e t2=m2 ' in cmd)
        self.assertTrue('-p {}:'.format(self.mock_port) in cmd)
        self.assertTrue(self.mock_image_name in cmd)

    def test_can_pass(self):
        self.assertTrue(True)


class HerdUnittestTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_project_root(self):
        """ ensure that the path reported by project root has a .git folder """
        self.assertTrue(os.path.exists(os.path.join(project_root(), ".git")))

    def test_service_name(self):
        self.assertEqual(service_name(), "herd")

    def test_unittest_cmd(self):
        self.assertEqual(unittest_cmd(), "python app/test_herd.py")


class HerdConfigTests(unittest.TestCase):

    def setUp(self):
        self.test_config_path = "./{}".format(str(uuid()))
        os.environ['herd_config_path'] = self.test_config_path
        with open(self.test_config_path, 'w') as configfile:
            conf = ConfigParser()
            conf.add_section("Mock")
            conf.set("Mock", "mockopt", "mockval")
            conf.write(configfile)

    def tearDown(self):
        try:
            os.remove(self.test_config_path)
        except:
            pass

    def test_configure(self):
        key = str(uuid())
        value = str(uuid())
        section = str(uuid())
        setconfig(section, key, value)
        with open(self.test_config_path, 'r') as configfile:
            conf = ConfigParser()
            conf.readfp(configfile)
            self.assertEqual(conf.get(section, key), value)
            self.assertEqual(conf.get("Mock", "mockopt"), "mockval")

    def test_make_init_config_file(self):
        """ make_init_config should write a config file """

        make_init_config(self.test_config_path, "mock.host.io")
        with open(self.test_config_path, 'r') as configfile:
            config = ConfigParser()
            config.readfp(configfile)
            self.assertEqual(config.get("Build", "host"), "mock.host.io")
            self.assertEqual(config.get("Build", "base_path"),
                             "/var/herd/build")

    def test_config_path_helper(self):

        # if it's none, return the default
        del os.environ['herd_config_path']
        self.assertEqual(config_path(), os.path.expanduser("~/.herdconfig"))

        # if it's something return that
        os.environ['herd_config_path'] = "/mock/path/.herdconfig"
        self.assertEqual(config_path(), "/mock/path/.herdconfig")

if __name__ == '__main__':
    unittest.main()
