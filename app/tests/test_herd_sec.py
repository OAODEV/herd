import os
import unittest
from uuid import uuid4 as uuid
import gnupg
from mock import MagicMock as Mock

from security import (
    sign_then_encrypt_file,
    decrypt_and_verify_file,
    distribute_secret,
    fetch_secret,
    DistributeMalformedError,
    NotTrustedError,
    DecryptionError,
    )


class HerdSecretsTest(unittest.TestCase):

    def setUp(self):
        self.remove = []
        os.environ['herd_config_path'] = "app/tests/test.conf"

        # set up test keys
        # 2 trusted keys and one untrusted key
        self.gpg = gnupg.GPG(homedir="app/tests/gnupghome",
                             binary=gnupg._util._which('gpg')[0])

        # set up identities
        self.my_fingerprint = "5064B59C5774AB9CCC514DD1CB8CD4CAF74E575E"
        self.their_fingerprint = "FE833075A8562AEF493A1C7D0829580E390A2D72"
        self.untrusted_fingerprint = "4A049AFD52104C5C072ABDDA83E4B2FC94F21313"
        self.recipients = [self.my_fingerprint, self.their_fingerprint]

        # set up test secret
        self.plainpath = str(uuid())
        self.remove.append(self.plainpath)
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
        self.remove.append(self.my_cypherpath)
        self.my_cyphertext = self.gpg.encrypt(
            self.my_secret,
            str(self.my_fingerprint),
            default_key=self.their_fingerprint,
            )
        with open(self.my_cypherpath, 'w') as my_cypherfile:
            my_cypherfile.write(self.my_cyphertext.data)

        # encrypt but don't sign something to me
        self.unverified_secret = str(uuid())
        self.unverified_cypherpath = str(uuid())
        self.remove.append(self.unverified_cypherpath)
        self.unverified_cyphertext = self.gpg.encrypt(
            self.my_secret,
            self.my_fingerprint)
        with open(self.unverified_cypherpath, 'w') as unverified_cypherfile:
            unverified_cypherfile.write(self.unverified_cyphertext.data)

        # encrypt but sign with untrusted key
        self.untrusted_secret = str(uuid())
        self.untrusted_cypherpath = str(uuid())
        self.remove.append(self.untrusted_cypherpath)
        self.untrusted_cyphertext = self.gpg.encrypt(
            self.my_secret,
            str(self.my_fingerprint),
            default_key=self.untrusted_fingerprint
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
            try:
                os.remove(p)
            except:
                pass
            try:
                os.rmdir(p)
            except:
                pass

        map(lambda x: remove(x), self.remove)

    def test_create_signed_encrypted_secret(self):
        """ herd should create signed then encrypted secret messages """

        # happy path
        cpath = sign_then_encrypt_file(
            self.plainpath,
            self.my_fingerprint,
            self.recipients,
            )
        self.remove.append(cypherpath)

        # confirm assumptions
        with open(cpath, 'r') as cfile, open(self.plainpath, 'r') as pfile:
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
        # set up
        cypherpath = sign_then_encrypt_file(
            self.plainpath,
            self.my_fingerprint,
            self.recipients,
            )
        self.remove.append(cypherpath)

        # excersize SUT (distribute tampered with cypherfiles)
        # bad file extension
        bad_extension_path = cypherpath[:-4] + ".gpg"
        self.remove.append(bad_extension_path)
        cypherfile = open(cypherpath, 'r')
        cyphertext = cypherfile.read()
        with open(bad_extension_path, 'w') as bad_extension_file:
            bad_extension_file.write(cyphertext)
        with self.assertRaises(DistributeMalformedError):
            distribute_secret(bad_extension_path)

        # check for correct errors when file not correctly encrypted
        def assert_malformed_exception(malformed_path, malformed, message):
            with open(malformed_path, 'w') as malfile:
                malfile.write(malformed)
            with self.assertRaises(DistributeMalformedError) as e:
                distribute_secret(malformed_path)
            self.assertEqual(str(e.exception), message)

        malformed_path = os.path.join(
            os.path.dirname(cypherpath),
            "mal_{}".format(os.path.basename(cypherpath)),
            )
        self.remove.append(malformed_path)

        # hash missmatch
        mal_lines = cyphertext.split('\n')
        mal_lines[-5] += "x"
        malformed = '\n'.join(mal_lines)
        assert_malformed_exception(malformed_path, malformed,
                                   "Hash missmatch")

        # incorrect first line
        malformed = "-" + cyphertext
        assert_malformed_exception(malformed_path, malformed,
                                   "Missing or malformed Armor Header Line")

        # incorrect last line
        malformed = cyphertext + "-"
        assert_malformed_exception(malformed_path, malformed,
                                   "Missing or malformed Armor Tail")

        # long line
        mal_lines = cyphertext.split('\n')
        mal_lines[-5] += "longlinelonglinelonglinelonglinelonglinelongline"
        malformed = '\n'.join(mal_lines)
        assert_malformed_exception(malformed_path, malformed,
                                   "Line longer than 78 characters")

        mal_lines = cyphertext.split('\n')
        mal_lines = filter(lambda x: x != '', mal_lines)
        malformed = '\n'.join(mal_lines) + '\n'
        assert_malformed_exception(malformed_path, malformed,
                                   "Missing blank line")

        mal_lines = cyphertext.split('\n')
        mal_lines = mal_lines[:2] + mal_lines[-2:]
        malformed = '\n'.join(mal_lines)
        assert_malformed_exception(malformed_path, malformed,
                                   "No ASCII-Armored data")

        # inappropriate whitespace
        mal_lines = cyphertext.split('\n')
        mal_lines[2] = "xxxxxxxxxxxxxxxxxxxxxxxxx xxxxxxxxxxxxxxxxxxxxxxxx"
        malformed = '\n'.join(mal_lines)
        assert_malformed_exception(malformed_path, malformed,
                                   "Whitespace in ASCII-Armored data")

        # confirm that os.system did not call any command
        self.assertEqual(os.system.call_count, 0)

        # excersize SUT (distribute the correct path)
        distribute_secret(cypherpath)

        # confirm that os.system called the correct scp command
        scp_cmd = "scp {} sec.iadops.com:/var/secret/{}".format(
            cypherpath, os.path.basename(cypherpath))
        os.system.assert_called_once_with(scp_cmd)

    def test_fetch_secret(self):
        """ herd should be able to download a secret file """
        # set up
        secret_name = str(uuid())
        mock_fetcher = Mock()

        # run SUT
        fetch_secret(secret_name, mock_fetcher)

        # confirm assumptions
        expected_str = "https://sec.iadops.com/secret/{}".format(secret_name)
        mock_fetcher.assert_called_once_with(expected_str)

    def test_decrypt_and_verify_my_secret(self):
        """ herd should decrypt and verify secrets intended for me

        Herd should also fail to decrypt secrets not intended for me. and
        should throw out secrets that don't have valid signitures from trusted
        keys.

        """

        # happy path
        with open(self.my_cypherpath, 'r') as cypherfile:
            plaintext = decrypt_and_verify_file(cypherfile)

        # confirm assumptions
        self.assertEqual(plaintext, self.my_secret)

        # no signiture
        with open(self.unverified_cypherpath, 'r') as unverified_cypherfile:
            with self.assertRaises(NotTrustedError) as e:
                plaintext = decrypt_and_verify_file(unverified_cypherfile)
        self.assertEqual(str(e.exception), "Invalid signiture")

        # untrusted signiture
        with open(self.untrusted_cypherpath, 'r') as untrusted_cypherfile:
            with self.assertRaises(NotTrustedError) as e:
                plaintext = decrypt_and_verify_file(untrusted_cypherfile)
        self.assertEqual(str(e.exception),
                         "Untrusted Key (OAO Tech) not fully trusted")

        # no encryption
        with open(self.plainpath, 'r') as plainfile:
            with self.assertRaises(DecryptionError):
                plaintext = decrypt_and_verify_file(plainfile)

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
