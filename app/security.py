import os
from urllib2 import urlopen
from itertools import dropwhile
from Crypto.Hash import SHA256
import gnupg
import re

from config import get_config

def sign_then_encrypt_file(path, signer, recipients, secret_name=None):
    """ sign then encrypt the file to the recipients.

    return a path to the encrypted file

    """

    # set up the secret human readable name
    if not secret_name:
        secret_name = os.path.basename(path)

    gpg = gnupg.GPG(homedir=get_config().get('security_gnupg_home', '~/.gnupg'),
                    binary=gnupg._util._which('gpg')[0])

    with open(path, 'r') as plainfile:
        crypt = gpg.encrypt(plainfile.read(), *recipients, default_key=signer)
        assert crypt.ok
        cyphertext = crypt.data
        h = SHA256.new()
        h.update(cyphertext)
        sha = h.hexdigest()

    # infer the filename
    sec_filename = "{}.{}.sec".format(secret_name, sha)
    sec_path = os.path.join(os.path.dirname(path), sec_filename)
    with open(sec_path, 'w') as cypherfile:
        cypherfile.write(cyphertext)

    return os.path.abspath(sec_path)

def decrypt_and_verify_file(cypherfile):
    """ decrypt and verify the encrypted secret """
    gpg = gnupg.GPG(homedir=get_config().get('security_gnupg_home', '~/.gnupg'),
                    binary=gnupg._util._which('gpg')[0])
    plain = gpg.decrypt_file(cypherfile)
    print plain.stderr

    try:
        assert plain.ok
    except:
        raise NotEncryptedError

    try:
        assert plain.valid
    except:
        raise NotTrustedError("invalid signiture")
    try:
        assert plain.trust_level >= plain.TRUST_FULLY
    except:
        raise NotTrustedError("{} not fully trusted".format(plain.username))

    return plain.data

def fetch_secret(secret_name, fetcher=urlopen):
    """ Return a secret fetched from the secret store """
    store = get_config()['security_remote_secret_store']
    url = "https://{}/secret/{}".format(store, secret_name)
    print url
    return fetcher(url)

def distribute_secret(path):
    """ upload the secret file to the secret store.

    Make an attempt to only upload encrypted files. We are going
    to rely on a few conventions to guard against distributing a
    plaintext secret. If someone really wants to distribute
    plaintext they will have to work hard to do it.

    Conventions we are going to check.
    filename <human name>.<sha256>.sec
    file should be in ascii armor format

    """

    def check_hash(path):
        """ The HMAC in the filename should authenticate the file """
        # grab the hmac. the thing between the last two dots
        hash_claim = os.path.basename(path).split('.')[-2]
        with open(path, 'r') as f:
            h = SHA256.new()
            h.update(f.read())
            if hash_claim != h.hexdigest():
                print "Hash missmatch {} is not {}".format(
                    hash_claim, h.hexdigest())
                raise DistributeMalformedError

    def assert_filename_extension(path):
        """ path should end with .sec """
        if path[-4:] != ".sec":
            print "filename ({}) should end in '.sec'".format(path)
            raise DistributeMalformedError

    def assert_armord_message(path):
        """ return True if data is OpenPGP ascii armor and False otherwise """
        potential_problem = ''
        with open(path, 'r') as f:
            lines = f.readlines()
            try:
                potential_problem = "bad first line"
                assert lines[0] == "-----BEGIN PGP MESSAGE-----\n"
                potential_problem = "bad last line"
                assert lines[-1] == "-----END PGP MESSAGE-----\n"
                potential_problem = "line longer than 78 characters"
                for line in lines:
                    assert len(line) < 79
                # lines after the first blank line and before the last
                # line should not have whitespace
                potential_problem = "whitespace in encrypted data"
                for line in dropwhile(lambda l: l!='\n', lines[:-2]):
                    assert not re.search("[ \t]+", line)
            except Exception, e:
                print "{} should be in ascii-armor format [{}]".format(
                    path, potential_problem)
                raise DistributeMalformedError

    assert_filename_extension(path)
    assert_armord_message(path)
    check_hash(path)

    remote_path = "{}:/var/secret/{}".format(
        get_config()['security_remote_secret_store'],
        os.path.basename(path)
        )
    os.system("scp {} {}".format(path, remote_path))

class DistributeMalformedError(Exception):
    """ attempted to distribute a malformed file """

class NotTrustedError(Exception):
    """ signiture not trusted """

class NotEncryptedError(Exception):
    """ Non enctypted data was treated as encrypted data """
