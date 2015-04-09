import os
import re
from urllib2 import urlopen
from itertools import dropwhile
import gnupg

from config import get_config

# we import both Crypto.Hash and then everything inside it because of
# the way the crypto library interacts with getattr
import Crypto.Hash
from Crypto.Hash import *
# keep both these imports here

default_hash_algo = "SHA256"


def calculate_digest(data):
    hash_algo = get_config().get("security_hash_algo", default_hash_algo)
    hasher = getattr(Crypto.Hash, hash_algo)
    h = hasher.new()
    h.update(data)
    return h.hexdigest()


def sign_then_encrypt_file(path,
                           signer=None,
                           recipients=[],
                           secret_name=None
                           ):
    """ sign then encrypt the file to the recipients.

    return a path to the encrypted file

    """

    # set up the secret human readable name
    if not secret_name:
        secret_name = os.path.basename(path)

    if not signer:
        signer = get_config()['security_my_fingerprint']

    gpg = gnupg.GPG(homedir=get_config().get('security_gnupg_home', '~/.gnupg'),
                    binary=gnupg._util._which('gpg')[0])

    with open(path, 'r') as plainfile:
        crypt = gpg.encrypt(plainfile.read(), *recipients, default_key=signer)
        assert crypt.ok
        cyphertext = crypt.data
        digest = calculate_digest(cyphertext)

    # infer the filename
    sec_filename = "{}.{}.sec".format(secret_name, digest)
    sec_path = os.path.join(os.path.dirname(path), sec_filename)
    with open(sec_path, 'w') as cypherfile:
        cypherfile.write(cyphertext)

    return os.path.abspath(sec_path)

def decrypt_and_verify_file(cypherfile):
    """ decrypt and verify the encrypted secret

    File -> String

    """
    gpg = gnupg.GPG(homedir=get_config().get('security_gnupg_home', '~/.gnupg'),
                    binary=gnupg._util._which('gpg')[0])
    plain = gpg.decrypt_file(cypherfile)
    print plain.stderr

    try: assert plain.ok
    except: raise DecryptionError

    try: assert plain.valid
    except: raise NotTrustedError("Invalid signiture")

    try: assert plain.trust_level >= plain.TRUST_FULLY
    except: raise NotTrustedError("{} not fully trusted".format(plain.username))

    return plain.data


def fetch_secret(secret_name, fetcher=urlopen):
    """ Return a secret fetched from the secret store

    String -> File

    """
    store = get_config()['security_remote_secret_store']
    url = "https://{}/secret/{}".format(store, secret_name)
    return fetcher(url)


def distribute_secret(path):
    """ upload the secret file to the secret store.

    Make an attempt to only upload encrypted files. We are going
    to rely on a few conventions to guard against distributing a
    plaintext secret. If someone really wants to distribute
    plaintext they will have to work hard to do it.

    Conventions we are going to check.
    filename <human name>.<hash digest>.sec
    file should be in ascii armor format

    """

    def assert_correct_hash(path):
        """ The hash in the filename should verify the file's consistency """
        # grab the hash digest, the thing between the last two dots
        hash_claim = os.path.basename(path).split('.')[-2]
        with open(path, 'r') as f:
            if hash_claim != calculate_digest(f.read()):
                print "Hash missmatch"
                raise DistributeMalformedError("Hash missmatch")

    def assert_filename_extension(path):
        """ path should end with .sec """
        if path[-4:] != ".sec":
            print "filename ({}) should end in '.sec'".format(path)
            raise DistributeMalformedError

    def assert_armord_message(path):
        """ return True if data is OpenPGP ascii armor and False otherwise

        This check is not intended to defend against any dedicated attacker. It
        is simply here to assist Alice. If she attempts to distribute a file
        she thought was cyphertext, but was instead plaintext, this should
        trigger and let her know. Eve could still distribute a secret through
        this function, however Eve would need to be able to manipulate the text
        in the secret file to conform to these checks in order to do so.

        """

        potential_problem = "Unknown error"
        with open(path, 'r') as f:
            lines = f.readlines()
            try:
                potential_problem = "Missing or malformed Armor Header Line"
                assert lines[0] == "-----BEGIN PGP MESSAGE-----\n"

                potential_problem = "Missing or malformed Armor Tail"
                assert lines[-1] == "-----END PGP MESSAGE-----\n"

                potential_problem = "Line longer than 78 characters"
                for line in lines:
                    assert len(line) < 79

                potential_problem = "Missing blank line"
                body_lines = list(dropwhile(lambda l: l!='\n', lines[:-1]))
                assert body_lines[0] == "\n"

                potential_problem = "No ASCII-Armored data"
                assert len(body_lines) > 2

                potential_problem = "Whitespace in ASCII-Armored data"
                # lines after the first blank line and before the last
                # line should not have whitespace
                for line in body_lines[1:-2]:
                    assert not re.search("[ \t]+", line)
            except Exception, e:
                print "{} should be in ASCII-Armor format [{}]".format(
                    path, potential_problem)
                raise DistributeMalformedError(potential_problem)

    assert_filename_extension(path)
    assert_armord_message(path)
    assert_correct_hash(path)

    remote_path = "{}:/var/secret/{}".format(
        get_config()['security_remote_secret_store'],
        os.path.basename(path)
        )
    os.system("scp {} {}".format(path, remote_path))
    return os.path.basename(path)


class DistributeMalformedError(Exception):
    """ attempted to distribute an incorrect secret file """


class NotTrustedError(Exception):
    """ signiture not trusted """


class DecryptionError(Exception):
    """ Decryption did not complete successfully """
