#
# Copyright (C) 2019  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
import unittest

from unittest.mock import patch, create_autospec

from tests.nosetests.pyanaconda_tests import check_dbus_property, patch_dbus_publish_object, \
    PropertiesChangedCallback
from tests.nosetests.pyanaconda_tests.module_payload_shared import PayloadKickstartSharedTest

from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.configuration.payload import PayloadSection
from pyanaconda.modules.common.constants.objects import PAYLOAD_PACKAGES
from pyanaconda.modules.common.errors import InvalidValueError, UnsupportedValueError
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.packages.packages import PackagesModule
from pyanaconda.modules.payloads.packages.packages_interface import PackagesInterface
from pyanaconda.modules.payloads.packages.constants import TIMEOUT_UNSET, RETRIES_UNSET, \
    LANGUAGES_DEFAULT, LANGUAGES_NONE


class PackagesKSTestCase(unittest.TestCase):

    def setUp(self):
        self.payload_module = PayloadsService()
        self.payload_module_interface = PayloadsInterface(self.payload_module)

        self.shared_tests = PayloadKickstartSharedTest(self,
                                                       self.payload_module,
                                                       self.payload_module_interface)

        # test variables
        self._expected_env = ""
        self._expected_packages = []
        self._expected_groups = []
        self._expected_excluded_packages = []
        self._expected_excluded_groups = []

    def _get_packages_interface(self):
        packages_module = self.payload_module._packages

        self.assertIsInstance(packages_module, PackagesModule)
        return PackagesInterface(packages_module)

    def _check_properties(self, nocore=False, multilib="best",
                          langs=LANGUAGES_DEFAULT, ignore_missing=False, ignore_broken=False):
        intf = self._get_packages_interface()

        self.assertEqual(self._expected_env, intf.Environment)
        self.assertEqual(self._expected_packages, intf.Packages)
        self.assertEqual(self._expected_groups, intf.Groups)
        self.assertEqual(self._expected_excluded_packages, intf.ExcludedPackages)
        self.assertEqual(self._expected_excluded_groups, intf.ExcludedGroups)

        self.assertEqual(nocore, not intf.CoreGroupEnabled)
        self.assertEqual(multilib, intf.MultilibPolicy)
        if langs:
            self.assertEqual(langs, intf.Languages)
        else:
            self.assertEqual([], intf.Languages)
        self.assertEqual(ignore_missing, intf.MissingIgnored)
        self.assertEqual(ignore_broken, intf.BrokenIgnored)

    @patch_dbus_publish_object
    def packages_section_empty_kickstart_test(self, publisher):
        """Test the empty packages section."""
        ks_in = """
        %packages
        %end
        """
        ks_out = """
        %packages

        %end
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)
        self._check_properties()

    @patch_dbus_publish_object
    def packages_section_kickstart_test(self, publisher):
        """Test the packages section."""
        ks_in = """
        %packages
        package
        @group
        @module:10
        @module2:1.5/server
        @^environment
        %end
        """
        ks_out = """
        %packages
        @^environment
        @group
        @module2:1.5/server
        @module:10
        package

        %end
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)

        self._expected_env = "environment"
        self._expected_packages = ["package"]
        self._expected_groups = ["group", "module:10", "module2:1.5/server"]
        self._check_properties()

    @patch_dbus_publish_object
    def packages_section_complex_kickstart_test(self, publisher):
        """Test the packages section with duplicates."""
        ks_in = """
        %packages
        @^environment1
        package1
        @group1
        package2

        # Only this environment will stay (last specified wins)
        @^environment2
        @group2

        # duplicates
        package2
        @group2

        # modules
        @module:4
        @module:3.5/server

        %end
        """
        # The last specified environment wins, you can't specify two environments
        # Same package or group specified twice will be deduplicated
        ks_out = """
        %packages
        @^environment2
        @group1
        @group2
        @module:3.5/server
        @module:4
        package1
        package2

        %end
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)

        self._expected_env = "environment2"
        self._expected_packages = ["package1", "package2"]
        self._expected_groups = ["group1", "group2", "module:4", "module:3.5/server"]
        self._check_properties()

    @patch_dbus_publish_object
    def packages_section_with_attribute_kickstart_test(self, publisher):
        """Test the packages section with attribute."""
        ks_in = """
        %packages --nocore
        %end
        """
        ks_out = """
        %packages --nocore

        %end
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(nocore=True)

    @patch_dbus_publish_object
    def packages_section_multiple_attributes_kickstart_test(self, publisher):
        """Test the packages section with multiple attributes."""
        ks_in = """
        %packages --nocore --multilib --inst-langs en_US.UTF-8

        %end
        """
        ks_out = """
        %packages --nocore --inst-langs=en_US.UTF-8 --multilib

        %end
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(nocore=True, multilib="all", langs="en_US.UTF-8")

    @patch_dbus_publish_object
    def packages_section_excludes_kickstart_test(self, publisher):
        """Test the packages section with excludes."""
        ks_in = """
        %packages
        -vim
        %end
        """
        ks_out = """
        %packages
        -vim

        %end
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)

        self._expected_excluded_packages = ["vim"]
        self._check_properties()

    @patch_dbus_publish_object
    def packages_section_complex_exclude_kickstart_test(self, publisher):
        """Test the packages section with complex exclude example."""
        ks_in = """
        %packages --nocore --ignoremissing --ignorebroken --inst-langs=
        @^environment1
        @group1
        package1
        -package2
        -@group2
        @group3
        package3
        %end
        """
        ks_out = """
        %packages --nocore --ignoremissing --ignorebroken --inst-langs=
        @^environment1
        @group1
        @group3
        package1
        package3
        -@group2
        -package2

        %end
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)

        self._expected_env = "environment1"
        self._expected_packages = ["package1", "package3"]
        self._expected_groups = ["group1", "group3"]
        self._expected_excluded_packages = ["package2"]
        self._expected_excluded_groups = ["group2"]

        self._check_properties(nocore=True, ignore_missing=True, ignore_broken=True,
                               langs=LANGUAGES_NONE)

    @patch("pyanaconda.modules.payloads.kickstart.conf")
    @patch_dbus_publish_object
    def packages_section_with_disabled_ignore_broken_test(self, publisher, conf):
        """Test if disabled ignore broken will fail as expected."""
        ks_in = """
        %packages --ignorebroken
        %end
        """

        conf.payload = create_autospec(PayloadSection)
        conf.payload.enable_ignore_broken_packages = False

        report = self.shared_tests.check_kickstart(ks_in=ks_in, ks_out=None, ks_valid=False)

        self.assertEqual(len(report.error_messages), 1)
        ks_message = report.error_messages[0]
        self.assertEqual(ks_message.message,
                         "The %packages --ignorebroken feature is not supported on your product!")


class PackagesInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.packages_module = PackagesModule()
        self.packages_interface = PackagesInterface(self.packages_module)

        self.callback = PropertiesChangedCallback()
        self.packages_interface.PropertiesChanged.connect(self.callback)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            PAYLOAD_PACKAGES,
            self.packages_interface,
            *args, **kwargs)

    def core_group_enabled_properties_test(self):
        self._check_dbus_property("CoreGroupEnabled", True)

    def core_group_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.CoreGroupEnabled, True)

    def default_environment_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.DefaultEnvironment, False)

    def environment_properties_test(self):
        self._check_dbus_property("Environment", "TestEnv")

    def environment_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.Environment, "")

    def groups_properties_test(self):
        self._check_dbus_property("Groups", ["group1", "group2"])

    def groups_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.Groups, [])

    def packages_properties_test(self):
        self._check_dbus_property("Packages", ["package1", "package2"])

    def packages_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.Packages, [])

    def excluded_groups_properties_test(self):
        self._check_dbus_property("ExcludedGroups", ["group1", "group2"])

    def excluded_groups_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.ExcludedGroups, [])

    def excluded_packages_properties_test(self):
        self._check_dbus_property("ExcludedPackages", ["package1", "package2"])

    def excluded_packages_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.ExcludedPackages, [])

    def docs_excluded_properties_test(self):
        self._check_dbus_property("DocsExcluded", True)

    def docs_excluded_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.DocsExcluded, False)

    def weakdeps_excluded_properties_test(self):
        self._check_dbus_property("WeakdepsExcluded", True)

    def weakdeps_excluded_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.WeakdepsExcluded, False)

    def missing_ignored_properties_test(self):
        self._check_dbus_property("MissingIgnored", True)

    def missing_ignored_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.MissingIgnored, False)

    def broken_ignored_properties_test(self):
        self._check_dbus_property("BrokenIgnored", True)

    def broken_ignored_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.BrokenIgnored, False)

    @patch("pyanaconda.modules.payloads.packages.packages.conf")
    def broken_ignored_disabled_properties_test(self, conf):
        conf.payload = create_autospec(PayloadSection)
        conf.payload.enable_ignore_broken_packages = False

        with self.assertRaises(UnsupportedValueError):
            self.packages_interface.SetBrokenIgnored(True)

        self.assertEqual(self.packages_interface.BrokenIgnored, False)
        self.callback.assert_not_called()

    def languages_properties_test(self):
        self._check_dbus_property("Languages", "en, es")

    def languages_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.Languages, LANGUAGES_DEFAULT)

    def languages_incorrect_value_properties_test(self):
        with self.assertRaises(InvalidValueError):
            self.packages_interface.SetLanguages("")

        self.callback.assert_not_called()

    def multilib_policy_properties_test(self):
        self._check_dbus_property("MultilibPolicy", 'all')

    def multilib_policy_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.MultilibPolicy, 'best')

    def timeout_properties_test(self):
        self._check_dbus_property("Timeout", 60)

    def timeout_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.Timeout, TIMEOUT_UNSET)

    def retries_properties_test(self):
        self._check_dbus_property("Retries", 30)

    def retries_not_set_properties_test(self):
        self.assertEqual(self.packages_interface.Retries, RETRIES_UNSET)
