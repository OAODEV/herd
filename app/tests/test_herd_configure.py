import os
import unittest
from uuid import uuid4
from mock import MagicMock as Mock
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from commands import (
    configure,
    ReleaseStore,
    Release
    )

Base = declarative_base()


class HerdConfigureTests(unittest.TestCase):
    """ Tests the herd configure command """

    def setUp(self):
        os.environ['herd_config_path'] = "app/tests/test.conf"
        self.remove_paths = []

    def tearDown(self):
        def remove(p):
            try:
                os.remove(p)
            except:
                pass
            try:
                os.rmdir(p)
            except:
                pass

        map(remove, self.remove_paths)

    def test_configure(self):
        """ configure should encrypt the config and add the release to the log

        The file should be encrypted to the correct recipients and should be
        distributed

        """
        # set up
        build_name = str(uuid4())
        conf_path = str(uuid4())
        mock_sec = Mock()
        mock_conf_filename = "{}.mock_hash.sec".format(conf_path)
        mock_sec.distribute_secret.return_value = mock_conf_filename
        mock_sec.sign_then_encrypt_file.return_value = mock_conf_filename
        mock_release_store = Mock()

        # run SUT
        configure(build_name,
                  conf_path,
                  __security_module__=mock_sec,
                  __release_store__=mock_release_store,
                  )

        # check assumptions

        # build name and the conf filename put into the release store
        mock_release_store.put.assert_called_once_with(
            build_name,
            mock_conf_filename,
            )

        # the security module was used to sign then encrypt the conf
        # file to the correct recipients
        expected_recipients = ['FE833075A8562AEF493A1C7D0829580E390A2D72']
        mock_sec.sign_then_encrypt_file.assert_called_once_with(
            conf_path, recipients=expected_recipients)

        # the security module was used to distribute the encrypted
        # file
        mock_sec.distribute_secret.assert_called_once_with(
            mock_conf_filename)

    def test_release_store(self):
        """ the release store should store build, config pairs """

        # set up
        tmp_log_path = str(uuid4())
        self.remove_paths.append(tmp_log_path)
        release_store = ReleaseStore('sqlite:///{}'.format(tmp_log_path))
        engine = create_engine('sqlite:///{}'.format(tmp_log_path))
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        build_name = str(uuid4())
        config_name = str(uuid4())

        # run SUT
        first_release_id = release_store.put(build_name, config_name).id_

        # assert that there is one release in the store.
        all_releases = list(session.query(Release).all())
        first_release = session.query(Release).first()
        self.assertEqual(len(all_releases), 1)
        self.assertEqual(first_release.build, build_name)
        self.assertEqual(first_release.config, config_name)

        # if we add another it should be there
        second_build_name = build_name + '2'
        second_config_name = config_name + '2'
        second_release_id = release_store.put(second_build_name,
                                              second_config_name,
                                              ).id_

        all_releases = list(session.query(Release).all())
        second_release = session.query(Release).filter(
            Release.build==second_build_name).first()
        self.assertEqual(len(all_releases), 2)
        self.assertTrue(second_release in all_releases)
        self.assertEqual(second_release.build, second_build_name)
        self.assertEqual(second_release.config, second_config_name)

        # we can get releases out by their id
        self.assertEqual(
            release_store.get(first_release_id).build,
            session.query(Release).filter(
                Release.id_==first_release_id).first().build
            )
        self.assertEqual(
            release_store.get(second_release_id).build,
            session.query(Release).filter(
                Release.id_==second_release_id).first().build
            )
            
    def test_can_pass(self):
        self.assertTrue(True)
