import sys
import argparse
import yaml
from collections import defaultdict
import itertools
import re

class catalog_validator:
    MISSING_CATALOG_EXCEPTIONS = ['rhods-operator.2.9.0', 'rhods-operator.2.9.1'] #ref - RHOAIENG-8828
    MISSING_PCC_EXCEPTIONS = ['rhods-operator.2.9.0', 'rhods-operator.2.9.1', 'rhods-operator.3.3.0'] #ref - RHOAIENG-8828
    MIN_OCP_VERSION_FOR_RHOAI_30 = 419

    class rhods_operator:
        def __init__(self, version:str):
            self.version = version

        def __ge__(self, other):
            self.semver = self.version.replace('rhods-operator.', '').split('.')
            other.semver = other.version.replace('rhods-operator.', '').split('.')
            return True if self.semver[0] > other.semver[0] else (True if self.semver[1] > other.semver[1] else self.semver[2] >= other.semver[2] if self.semver[1] == other.semver[1] else False) if self.semver[0] == other.semver[0] else False

        def __le__(self, other):
            self.semver = self.version.replace('rhods-operator.', '').split('.')
            other.semver = other.version.replace('rhods-operator.', '').split('.')
            return True if self.semver[0] < other.semver[0] else (True if self.semver[1] < other.semver[1] else self.semver[2] <= other.semver[2] if self.semver[1] == other.semver[1] else False) if self.semver[0] == other.semver[0] else False

    def __init__(self, build_config_path, catalog_folder_path, shipped_rhoai_versions_path, operation):
        self.build_config_path = build_config_path
        self.catalog_folder_path = catalog_folder_path
        self.shipped_rhoai_versions_path = shipped_rhoai_versions_path

        self.operation = operation

        self.build_config = yaml.safe_load(open(self.build_config_path))
        self.supported_ocp_versions = sorted(list(set(self.build_config['config']['supported-ocp-versions']['release'] + [item['name'] for item in self.build_config['config']['supported-ocp-versions']['build']]))) if operation == 'validate-catalogs' \
            else sorted(self.build_config['config']['supported-ocp-versions'], key=lambda x: x['version']) if operation == 'validate-pcc' else None

        self.shipped_rhoai_versions = open(self.shipped_rhoai_versions_path).readlines()

        self.shipped_rhoai_versions = sorted(list(
            set([version.split('-')[0].strip('\n').replace('v', '') for version in self.shipped_rhoai_versions if
                 version.count('.') > 1])))
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
        # need to get the global config.yaml and process the discontinuity map in order to ignore the unsupported OCP versions like 4.14, same as what was done for pcc validation
        for ocp_version in self.supported_ocp_versions:
            catalog_dict = self.parse_catalog_yaml(f'{self.catalog_folder_path}/{ocp_version}/rhods-operator/catalog.yaml')
            bundles = catalog_dict['olm.bundle']
            numeric_ocp_version = int(ocp_version.replace('v4.', '4'))
            missing_bundles[ocp_version] = []
            incorrect_3x_bundles[ocp_version] = []

            for rhoai_version in self.shipped_rhoai_versions:
                operator_name = f'rhods-operator.{rhoai_version}'
                if operator_name not in bundles and operator_name not in self.MISSING_CATALOG_EXCEPTIONS:
                    if not (rhoai_version.startswith(
                            'v3') and numeric_ocp_version < self.MIN_OCP_VERSION_FOR_RHOAI_30):  # bypassing check for 3.0 for OCP < 4.19
                        print(f"Skipping the catalog validation for {rhoai_version} bundle for OCP {ocp_version}, since 3.x is not shipped on this OCP version!")
                        continue
                    missing_bundles[ocp_version].append(operator_name)

                if operator_name in bundles and rhoai_version.startswith('v3') and numeric_ocp_version < self.MIN_OCP_VERSION_FOR_RHOAI_30: # adding check to ensure 3.x doesn't land on OCP < 4.19
                    incorrect_3x_bundles[ocp_version].append(operator_name)

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
            sys.exit(1)

    def validate_pcc(self):
        missing_bundles = {}
        discontinuity_map = {ocp_version['version']:ocp_version['discontinued-from'] if 'discontinued-from' in ocp_version else 'rhods-operator.9.99.99' for ocp_version in self.supported_ocp_versions }
        onboarding_map = {ocp_version['version']:ocp_version['onboarded-since'] if 'onboarded-since' in ocp_version else 'rhods-operator.0.0.0' for ocp_version in self.supported_ocp_versions }
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
                if operator_name not in bundles and operator_name not in self.MISSING_PCC_EXCEPTIONS:
                    if not (rhoai_version.startswith('v3') and numeric_ocp_version < self.MIN_OCP_VERSION_FOR_RHOAI_30): # bypassing check for 3.0 for OCP < 4.19
                        if not self.rhods_operator(operator_name) >= self.rhods_operator(discontinuity_map[ocp_version]) and not self.rhods_operator(operator_name) <= self.rhods_operator(onboarding_map[ocp_version]):
                            missing_bundles[pcc_file].append(operator_name)
                        else:
                            print(f'Ignoring since OCP {ocp_version} is not supported for {operator_name}')



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
    args = parser.parse_args()

    if args.operation.lower() == 'validate-catalogs':
        validator = catalog_validator(build_config_path=args.build_config_path, catalog_folder_path=args.catalog_folder_path, shipped_rhoai_versions_path=args.shipped_rhoai_versions_path, operation=args.operation)
        validator.validate_catalogs()
    elif args.operation.lower() == 'validate-pcc':
        validator = catalog_validator(build_config_path=args.build_config_path, catalog_folder_path=args.catalog_folder_path, shipped_rhoai_versions_path=args.shipped_rhoai_versions_path, operation=args.operation)
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
