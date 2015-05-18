import os
import unittest
from mock import MagicMock as Mock
from mock import patch
import fabric.api
from uuid import uuid4
import random
from StringIO import StringIO
from ConfigParser import ConfigParser

import security
from commands import (
    ReleaseStore,
    stage_config,
    wipe_config,
    execute_release,
    __deploy__,
    )

class HerdDeployTests(unittest.TestCase):

    def setUp(self):
        self.remove = []
        self.releases = ReleaseStore("sqlite:///tmp_release_store")
        self.remove.append("tmp_release_store")
        self.mock_build_name = str(uuid4())
        self.mock_config_name = str(uuid4())
        self.release = self.releases.put(
            self.mock_build_name,
            self.mock_config_name
            )

        self.stop = []
        self.run_patcher = patch('commands.run')
        self.stop.append(self.run_patcher)
        self.settings_patcher = patch('commands.settings')
        self.stop.append(self.settings_patcher)
        self.mock_run = self.run_patcher.start()
        self.mock_settings = self.settings_patcher.start()

    def tearDown(self):
        def rm(p):
            try:
                os.remove(p)
            except:
                pass
            try:
                os.rmdir(p)
            except:
                pass

        def stop(p):
            p.stop()

        map(rm, self.remove)
        map(stop, self.stop)

    def test_stage_config(self):
        """ should stage the correct config on the target's ramdisk """
        # Set Up
        put_patcher = patch("commands.put")
        mock_put = put_patcher.start()
        self.stop.append(put_patcher)
        mock_sec = Mock()
        mock_cypherfile = StringIO(str(uuid4()))
        mock_sec.fetch_secret.return_value = mock_cypherfile
        mock_plaintext = str(uuid4())
        mock_sec.decrypt_and_verify_file.return_value = mock_plaintext
        sec_patcher = patch('commands.security', mock_sec)
        sec_patcher.start()
        self.stop.append(sec_patcher)
        host = str(uuid4())

        # run SUT
        config_stage_name = stage_config(self.release, host)

        # Should have fetched the correct config
        mock_sec.fetch_secret.assert_called_once_with(self.mock_config_name)

        # Should have decrypted and verified the config
        mock_sec.decrypt_and_verify_file.assert_called_once_with(
            mock_cypherfile,
            )

        # Should have put the file on the ramdisk
        # call mock_put once
        self.assertEqual(mock_put.call_count, 1)
        # first arg should be a file object containing mock_plaintext
        self.assertEqual(mock_put.call_args_list[0][0][0].read(),
                         mock_plaintext,
                         )
        # second arg should be the correct path
        self.assertEqual(mock_put.call_args_list[0][0][1],
                         "/test/config/stage/path/{}".format(config_stage_name),
                         )

        # should set host string to mock.host.com
        self.mock_settings.assert_called_once_with(host_string=host)

        # staged filename should be unique and random
        many_stage_names = [
            stage_config(self.release, host)
            for x
            in range(100)
            ]
        self.assertEqual(sorted(many_stage_names),
                         sorted(set(many_stage_names))
                         )


    def test_wipe_config(self):
        """ should use shred -u to remove the ramdisk file """
        # Set up
        host = str(uuid4())
        stage_name = str(uuid4())

        # Run SUT
        wipe_config(host, stage_name)

        # should set host string to mock.host.com
        self.mock_settings.assert_called_once_with(host_string=host)

        # should call expected shred command
        self.mock_run.assert_called_once_with(
            "shred -u /test/config/stage/path/{}".format(stage_name))

    def test_execute_release(self):
        """ should start the correct container with the ramdisk config """
        # Set up
        host = str(uuid4())
        port = str(random.randint(1000, 9999))
        stage_name = str(uuid4())
        service_port = str(random.randint(1000, 9999))
        dep = str(uuid4())
        manifest = ConfigParser()
        manifest.add_section("Service")
        manifest.set("Service", "service_port", service_port)
        manifest.add_section("Dependencies")
        manifest.set("Dependencies", dep, '')

        get_manifest_patcher = patch("commands.get_manifest")
        mock_get_manifest = get_manifest_patcher.start()
        mock_get_manifest.return_value = manifest
        self.stop.append(get_manifest_patcher)
        stage_config_patcher = patch('commands.stage_config')
        mock_stage_config = stage_config_patcher.start()
        self.stop.append(stage_config_patcher)

        # Run SUT
        execute_release(self.release, host, port, stage_name)

        # should run correct docker command
        expected_cmd = "docker run -d -p {}:{} --env-file={} -e {} {}".format(
            port,
            service_port,
            os.path.join("/test/config/stage/path", stage_name),
            dep.capitalize(),
            self.release.build,
            )
        self.mock_run.assert_called_once_with(expected_cmd)

        # should set host string to the host
        self.mock_settings.assert_called_once_with(host_string=host)

        # should get the manifest from the deploy target
        mock_get_manifest.assert_called_once_with(self.release, host)

    def test_deploy(self):
        """ deploy should stage, execute then wipe """
        # Set up
        stage_patcher = patch('commands.stage_config')
        exe_patcher = patch('commands.execute_release')
        wipe_patcher = patch('commands.wipe_config')
        mock_stage = stage_patcher.start()
        self.stop.append(mock_stage)
        mock_stage.return_value = uuid4()
        mock_exe = exe_patcher.start()
        self.stop.append(exe_patcher)
        mock_wipe = wipe_patcher.start()
        self.stop.append(wipe_patcher)

        host = str(uuid4())
        port = str(random.randint(1000, 9000))

        # Run SUT
        __deploy__(self.release, "{}:{}".format(host, port))

        # Stage should have been called with release and host
        mock_stage.assert_called_once_with(self.release, host)

        # exe should have been called with stage's return_value
        mock_exe.assert_called_once_with(self.release, host, port, mock_stage())

        # wipe should have been called with host and stage's
        # return_value
        mock_wipe.assert_called_once_with(host, mock_stage())

    def test_can_pass(self):
        self.assertTrue(True)
