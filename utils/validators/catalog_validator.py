import sys
import argparse
import yaml
from collections import defaultdict
import itertools
import re

class catalog_validator:
    MISSING_BUNDLE_EXCEPTIONS = ['rhods-operator.2.9.0', 'rhods-operator.2.9.1'] #ref - RHOAIENG-8828
    MIN_OCP_VERSION_FOR_RHOAI_30 = 419
    # Matches both raw image tags (e.g. "v3.4.0-ea.1") and operator bundle names
    # (e.g. "rhods-operator.3.4.0-ea.1"). The $ anchor rejects build-number tags
    # (v2.16.0-1733155920) and source tags (v2.16.0-source) since they have
    # trailing content that doesn't match end-of-string.
    #
    # Capture groups:
    #   1 = full version string  (e.g. "3.4.0-ea.1")
    #   2 = major, 3 = minor, 4 = patch
    #   5 = EA sequence number   (None for GA)
    #   6 = EA hotfix number     (None if no hotfix)
    VERSION_REGEX = re.compile(
        r'(?:rhods-operator\.|v?)((\d+)\.(\d+)\.(\d+)(?:-ea\.(\d+)(?:\.(\d+))?)?)$'
    )

    class rhods_operator:
        def __init__(self, version: str):
            self.version = version
            self._parsed_tuple = self._parse_version(version)

        def _parse_version(self, version_string):
            """
            Parse 'rhods-operator.MAJOR.MINOR.PATCH[-ea.SEQ[.HOTFIX]]'
            into a comparable tuple.

            GA versions get is_ga=1 (sorts higher than EA's is_ga=0),
            so 3.4.0 (GA) > 3.4.0-ea.N (any EA).
            """
            match_result = catalog_validator.VERSION_REGEX.match(version_string)
            if not match_result:
                raise ValueError(f"Cannot parse operator version: {version_string}")

            major = int(match_result.group(2))
            minor = int(match_result.group(3))
            patch = int(match_result.group(4))
            ea_sequence = match_result.group(5)
            ea_hotfix = match_result.group(6)

            if ea_sequence is not None:
                is_ga = 0
                ea_sequence_num = int(ea_sequence)
                ea_hotfix_num = int(ea_hotfix) if ea_hotfix else 0
            else:
                is_ga = 1
                ea_sequence_num = 0
                ea_hotfix_num = 0

            return (major, minor, patch, is_ga, ea_sequence_num, ea_hotfix_num)

        def __ge__(self, other):
            return self._parsed_tuple >= other._parsed_tuple

        def __le__(self, other):
            return self._parsed_tuple <= other._parsed_tuple

        def __gt__(self, other):
            return self._parsed_tuple > other._parsed_tuple

        def __lt__(self, other):
            return self._parsed_tuple < other._parsed_tuple

        def __eq__(self, other):
            return self._parsed_tuple == other._parsed_tuple

        def __getitem__(self, key):
            return self._parsed_tuple[key]

        def __repr__(self):
            return self.version

        # given a list of versions, determine if this is the globally latest ea version 
        def is_latest_ea(self, versions_list):
            latest = self

            for item in versions_list:
                # This try block filters out all the legacy releases that don't match 
                #  the expected pattern
                try: 
                    version = self.__class__(item) 
                except ValueError:
                    continue
                else:
                    # Check if greater, but skip if GA release
                    if version >= latest and version[3] == 0:
                        latest = version

            print(f"{latest} is the newest EA release")
            return latest == self
            
    def __init__(self, build_config_path, catalog_folder_path, shipped_rhoai_versions_path, operation, global_config_path):
        self.build_config_path = build_config_path
        self.catalog_folder_path = catalog_folder_path
        self.shipped_rhoai_versions_path = shipped_rhoai_versions_path

        self.operation = operation

        self.build_config = yaml.safe_load(open(self.build_config_path))
        self.supported_ocp_versions = sorted(list(set(self.build_config['config']['supported-ocp-versions']['release'] + [item['name'] for item in self.build_config['config']['supported-ocp-versions']['build']]))) if operation == 'validate-catalogs' \
            else sorted(self.build_config['config']['supported-ocp-versions'], key=lambda x: x['version']) if operation == 'validate-pcc' else None

        self.global_config = yaml.safe_load(open(global_config_path))
        global_ocp_versions = self.global_config['config']['supported-ocp-versions']
        self.discontinuity_map = {entry['version']: entry['discontinued-from'] if 'discontinued-from' in entry else 'rhods-operator.9.99.99' for entry in global_ocp_versions}
        self.onboarding_map = {entry['version']: entry['onboarded-since'] if 'onboarded-since' in entry else 'rhods-operator.0.0.0' for entry in global_ocp_versions}
        self.skip_bundles_map = {entry['version']: entry['skip-bundles'] if 'skip-bundles' in entry else [] for entry in global_ocp_versions}

        self.shipped_rhoai_versions = open(self.shipped_rhoai_versions_path).readlines()

        self.shipped_rhoai_versions = sorted(list(set(
            version_match.group(1)
            for raw_version in self.shipped_rhoai_versions
            for version_match in [self.VERSION_REGEX.match(raw_version.strip())]
            if version_match
        )))
        print('shipped_rhoai_versions', self.shipped_rhoai_versions)

    def parse_catalog_yaml(self, catalog_yaml_path):
        # objs = yaml.safe_load_all(open(self.catalog_yaml_path))
        objs = yaml.safe_load_all(open(catalog_yaml_path))
        catalog_dict = defaultdict(dict)
        for obj in objs:
            catalog_dict[obj['schema']][obj['name']] = obj
        return catalog_dict

    def validate_catalogs(self):
        missing_bundles = {}
        incorrect_3x_bundles = {}

        for ocp_version in self.supported_ocp_versions:
            catalog_dict = self.parse_catalog_yaml(f'{self.catalog_folder_path}/{ocp_version}/rhods-operator/catalog.yaml')
            bundles = catalog_dict['olm.bundle']
            numeric_ocp_version = int(ocp_version.replace('v4.', '4'))
            missing_bundles[ocp_version] = []
            incorrect_3x_bundles[ocp_version] = []

            for rhoai_version in self.shipped_rhoai_versions:
                operator_name = f'rhods-operator.{rhoai_version}'
                is_3x_on_unsupported_ocp = (
                    rhoai_version.startswith('3')
                    and numeric_ocp_version < self.MIN_OCP_VERSION_FOR_RHOAI_30
                )

                if operator_name in bundles:
                    if is_3x_on_unsupported_ocp:
                        incorrect_3x_bundles[ocp_version].append(operator_name)
                    continue

                if operator_name in self.MISSING_BUNDLE_EXCEPTIONS:
                    continue

                if operator_name in self.skip_bundles_map[ocp_version]:
                    print(f'{operator_name} is in skip-bundles list for OCP {ocp_version}. Skipping')
                    continue

                if is_3x_on_unsupported_ocp:
                    print(f"Skipping the catalog validation for {rhoai_version} bundle for OCP {ocp_version}, since 3.x is not shipped on this OCP version!")
                    continue

                if self.rhods_operator(operator_name) >= self.rhods_operator(self.discontinuity_map[ocp_version]) \
                        or self.rhods_operator(operator_name) < self.rhods_operator(self.onboarding_map[ocp_version]):
                    print(f'Ignoring missing {operator_name} since OCP {ocp_version} is not supported for it')
                    continue

                if not self.rhods_operator(operator_name).is_latest_ea(bundles):
                    print(f'Ignoring missing {operator_name} since it is expected to be overwritten by a newer EA release')
                    continue

                missing_bundles[ocp_version].append(operator_name)

        print('missing_bundles', missing_bundles)
        print('incorrect_3x_bundles', incorrect_3x_bundles)

        bundles_missing, bundles_incorrect = False, False

        if list(itertools.chain.from_iterable([bundles for ocp_version, bundles in missing_bundles.items()])):
            print('Following bundles are missing from the catalogs:', missing_bundles)
            print('Exiting, please fix the missing bundles')
            bundles_missing = True
        else:
            print('No missing bundles found in all the catalogs')

        if list(itertools.chain.from_iterable([bundles for ocp_version, bundles in incorrect_3x_bundles.items()])):
            print('Following 3.x bundles are incorrectly added to unsupported OCP versions:', incorrect_3x_bundles)
            print('Exiting, please fix the incorrect bundles')
            incorrect_3x_bundles = True
        else:
            print('No incorrect 3.x bundles found in all the catalogs')

        if bundles_missing or bundles_incorrect:
            # sys.exit(1)
            print('should have exited here')

    def validate_pcc(self):
        missing_bundles = {}
        pcc_catalog_files = [f'catalog-{ocp_version["version"]}.yaml' for ocp_version in
                                  self.supported_ocp_versions]

        for pcc_file in pcc_catalog_files:
            ocp_version = re.search('^catalog-(.*).yaml', pcc_file).group(1)
            numeric_ocp_version = int(ocp_version.replace('v4.', '4'))

            catalog_dict = self.parse_catalog_yaml(f'{self.catalog_folder_path}/{pcc_file}')
            bundles = catalog_dict['olm.bundle']
            missing_bundles[pcc_file] = []

            for rhoai_version in self.shipped_rhoai_versions:
                operator_name = f'rhods-operator.{rhoai_version}'
                is_3x_on_unsupported_ocp = (
                    rhoai_version.startswith('3')
                    and numeric_ocp_version < self.MIN_OCP_VERSION_FOR_RHOAI_30
                )
                if operator_name in bundles:
                    continue

                if operator_name in self.MISSING_BUNDLE_EXCEPTIONS:
                    continue

                if operator_name in self.skip_bundles_map[ocp_version]:
                    print(f'{operator_name} is in skip-bundles list for OCP {ocp_version}. Skipping')
                    continue

                if is_3x_on_unsupported_ocp:  # bypassing check for 3.0 for OCP < 4.19
                    continue

                if self.rhods_operator(operator_name) >= self.rhods_operator(self.discontinuity_map[ocp_version]) \
                        or self.rhods_operator(operator_name) < self.rhods_operator(self.onboarding_map[ocp_version]):
                    print(f'Ignoring missing {operator_name} since OCP {ocp_version} is not supported for it')
                    continue

                if not self.rhods_operator(operator_name).is_latest_ea(bundles):
                    print(f'Ignoring missing {operator_name} since it is expected to be overwritten by a newer EA release')
                    continue

                missing_bundles[pcc_file].append(operator_name)



        print('missing_bundles', missing_bundles)


        if list(itertools.chain.from_iterable([bundles for ocp_version, bundles in missing_bundles.items()])):
            print('Following bundles are missing from the catalogs:', missing_bundles)
            print('Exiting, please fix the missing bundles')
            sys.exit(1)
        else:
            print('No missing bundles found in all the catalogs')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-op', '--operation', required=False,
                        help='Operation code, supported values are "validate-catalogs" and "validate-pcc"', dest='operation')
    parser.add_argument('-b', '--build-config-path', required=False,
                        help='Path of the build-config.yaml', dest='build_config_path')
    parser.add_argument('-c', '--catalog-folder-path', required=False,
                        help='Path of the catalog.yaml from the main branch.', dest='catalog_folder_path')
    parser.add_argument('-s', '--shipped-rhoai-versions-path', required=False,
                        help='Path of the shipped_rhoai_versions.txt from the main branch.', dest='shipped_rhoai_versions_path')
    parser.add_argument('-g', '--global-config-path', required=True,
                        help='Path of the global config.yaml (from main branch) containing discontinuity/onboarding maps.', dest='global_config_path')
    args = parser.parse_args()

    if args.operation.lower() == 'validate-catalogs':
        validator = catalog_validator(build_config_path=args.build_config_path, catalog_folder_path=args.catalog_folder_path, shipped_rhoai_versions_path=args.shipped_rhoai_versions_path, operation=args.operation, global_config_path=args.global_config_path)
        validator.validate_catalogs()
    elif args.operation.lower() == 'validate-pcc':
        validator = catalog_validator(build_config_path=args.build_config_path, catalog_folder_path=args.catalog_folder_path, shipped_rhoai_versions_path=args.shipped_rhoai_versions_path, operation=args.operation, global_config_path=args.global_config_path)
        validator.validate_pcc()


    # build_config_path = '/home/dchouras/RHODS/DevOps/RBC/rhoai-2.17/config/build-config.yaml'
    # shipped_rhoai_versions_path = '/home/dchouras/RHODS/DevOps/RBC/main/pcc/shipped_rhoai_versions.txt'

    # catalog_folder_path = '/home/dchouras/RHODS/DevOps/RBC-RHDS/catalog'
    # stage_catalog_folder_path = '/home/dchouras/RHODS/DevOps/RBC/main/catalog/rhoai-2.17'



    # validator = catalog_validator(build_config_path=build_config_path, catalog_folder_path=catalog_folder_path,
    #                               shipped_rhoai_versions_path=shipped_rhoai_versions_path)
    # validator.validate_catalogs()

    # validator = catalog_validator(build_config_path=build_config_path, catalog_folder_path=stage_catalog_folder_path,
    #                               shipped_rhoai_versions_path=shipped_rhoai_versions_path)
    # validator.validate_catalogs()

    # build_config_path = '/home/dchouras/RHODS/DevOps/RBC-RHDS/config/config.yaml'
    # shipped_rhoai_versions_path = '/home/dchouras/RHODS/DevOps/RBC-RHDS/pcc/shipped_rhoai_versions.txt'
    # pcc_folder_path = '/home/dchouras/RHODS/DevOps/RBC-RHDS/pcc'
    # validator = catalog_validator(build_config_path=build_config_path, catalog_folder_path=pcc_folder_path,
    #                               shipped_rhoai_versions_path=shipped_rhoai_versions_path, operation='validate-pcc')
    # validator.validate_pcc()
