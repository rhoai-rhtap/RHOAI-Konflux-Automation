
from jsonupdate_ng import jsonupdate_ng
import argparse
import yaml
import json
from collections import defaultdict
import base64
class fbc_processor:
    PRODUCTION_REGISTRY = 'registry.redhat.io'
    def __init__(self, build_config_path:str, catalog_yaml_path:str, patch_yaml_path:str, single_bundle_path:str, output_file_path:str):
        self.build_config_path = build_config_path
        self.catalog_yaml_path = catalog_yaml_path
        self.patch_yaml_path = patch_yaml_path
        self.single_bundle_path = single_bundle_path
        self.output_file_path = output_file_path
        self.catalog_dict:defaultdict = self.parse_catalog_yaml()
        self.patch_dict = self.parse_patch_yaml()
        self.build_config = yaml.safe_load(open(self.build_config_path))
        self.current_olm_bundle = self.parse_single_bundle_catalog()

    def parse_catalog_yaml(self):
        objs = yaml.safe_load_all(open(self.catalog_yaml_path))
        print(type(objs))
        catalog_dict = defaultdict(dict)
        for obj in objs:
            catalog_dict[obj['schema']][obj['name']] = obj
        return catalog_dict

    def parse_single_bundle_catalog(self):
        objs = yaml.safe_load_all(open(self.single_bundle_path))
        single_olm_bundle = None
        for obj in objs:
            if obj['schema'] == 'olm.bundle':
                single_olm_bundle = obj
                break
        return single_olm_bundle

    def parse_patch_yaml(self):
        return yaml.safe_load(open(self.patch_yaml_path))
    def patch_catalog_yaml(self):
        if 'olm.package' in self.patch_dict['patch']:
            self.patch_olm_package()
        if 'olm.channels' in self.patch_dict['patch']:
            self.patch_olm_channels()
        self.patch_olm_bundles()

        self.write_output_catalog()

    def write_output_catalog(self):
        docs = [doc for schema, schema_val in self.catalog_dict.items() for name, doc in schema_val.items()]
        yaml.add_representer(str, str_presenter)
        yaml.representer.SafeRepresenter.add_representer(str, str_presenter)
        yaml.safe_dump_all(docs, open(self.output_file_path, 'w'), sort_keys=False)


    def patch_olm_package(self):
        SCHEMA = 'olm.package'
        patch = self.patch_dict['patch'][SCHEMA]
        self.catalog_dict[SCHEMA][patch['name']] = jsonupdate_ng.updateJson(self.catalog_dict[SCHEMA][patch['name']], patch)


    def patch_olm_channels(self):
        SCHEMA = 'olm.channel'
        PATCH_SCHEMA = 'olm.channels'
        for channel in self.patch_dict['patch'][PATCH_SCHEMA]:
            if channel['name'] in self.catalog_dict[SCHEMA]:
                self.catalog_dict[SCHEMA][channel['name']] = jsonupdate_ng.updateJson(self.catalog_dict[SCHEMA][channel['name']], channel, meta={'listPatchScheme': {'$.entries': 'name'}})
            else:
                self.catalog_dict[SCHEMA][channel['name']] = channel

    def apply_replacements_to_catalog(self, olm_bundle):
        olm_bundle['image'] = self.apply_replacement(olm_bundle['image'])

        for relatedImage in olm_bundle['relatedImages']:
            relatedImage['image'] = self.apply_replacement(relatedImage['image'])

        for property in olm_bundle['properties']:
            if property['type'] == 'olm.bundle.object':
                property['value']['data'] = self.apply_replacemenmt_to_olm_bundle_object(property['value']['data'])
        return olm_bundle


    def apply_replacemenmt_to_olm_bundle_object(self, encoded_object:str):
        bundle_str:str = base64.b64decode(encoded_object).decode('utf-8')
        bundle_object = json.loads(bundle_str)
        encoded_output = encoded_object
        if bundle_object['kind'] == 'ClusterServiceVersion':
            envs = \
            bundle_object['spec']['install']['spec']['deployments'][0]['spec']['template']['spec']['containers'][0][
                'env']
            for env in envs:
                if 'value' in env:
                    env['value'] = self.apply_replacement(env['value'])
            encoded_output = base64.b64encode(json.dumps(bundle_object).encode()).decode('utf-8')
            encoded_output = encoded_output.replace('\n', '')

        return encoded_output



    def apply_replacement(self, value:str):
        if value:
            for replacement in self.build_config['config']['replacements']:
                intermediate_registry = replacement['registry']
                for old, new in replacement['repo_mappings'].items():
                    value = value.replace(f'{intermediate_registry}/{old}@', f'{self.PRODUCTION_REGISTRY}/{new}@')
        return value


    def patch_olm_bundles(self):
        SCHEMA = 'olm.bundle'
        current_bundle_name = self.current_olm_bundle['name']
        self.catalog_dict[SCHEMA][current_bundle_name] = self.apply_replacements_to_catalog(self.current_olm_bundle)
        # apply replacements for bundle image Uri in catalog
        # apply replacements for related images in the catalog
        # replacement of the encoded bundle
        # 1. decode the last "olm.bundle" object
        # 2. apply the replacements for all the related images
        # 3. encode the "olm.bundle" again
        # 4. patch it with the catalog.yaml
def str_presenter(dumper, data):
    if data.count('\n') > 0:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)
class snapshot_processor:
    def __init__(self, snapshot_json_path:str, output_file_path:str, image_filter:str=''):
        self.snapshot_json_path = snapshot_json_path
        self.output_file_path = output_file_path
        self.image_filter = image_filter

    def extract_images_from_snapshot(self):
        snapshot = json.load(open(self.snapshot_json_path))
        output_images = []
        for component in snapshot['spec']['components']:
            output_images.append({'name': component['name'], 'imageUri': component['containerImage']})

        json.dump(output_images, indent=4, fp=open(self.output_file_path, 'w'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-op', '--operation', required=False,
                        help='Operation code, supported values are "catalog-patch" and "extract-snapshot-images"', dest='operation')
    parser.add_argument('-b', '--build-config-path', required=False,
                        help='Path of the build-config.yaml', dest='build_config_path')
    parser.add_argument('-c', '--catalog-yaml-path', required=False,
                        help='Path of the catalog.yaml from the main branch.', dest='catalog_yaml_path')
    parser.add_argument('-p', '--patch-yaml-path', required=False,
                        help='Path of the catalog-patch.yaml from the release branch.', dest='patch_yaml_path')
    parser.add_argument('-s', '--single-bundle-path', required=False,
                        help='Path of the single-bundle generated using the opm.', dest='single_bundle_path')
    parser.add_argument('-o', '--output-file-path', required=False,
                        help='Path of the single-bundle generated using the opm.', dest='output_file_path')
    parser.add_argument('-sn', '--snapshot-json-path', required=False,
                        help='Path of the single-bundle generated using the opm.', dest='snapshot_json_path')
    parser.add_argument('-f', '--image-filter', required=False,
                        help='Path of the single-bundle generated using the opm.', dest='image_filter')
    args = parser.parse_args()

    if args.operation.lower() == 'catalog-patch':
        processor = fbc_processor(build_config_path=args.build_config_path, catalog_yaml_path=args.catalog_yaml_path, patch_yaml_path=args.patch_yaml_path, single_bundle_path=args.single_bundle_path, output_file_path=args.output_file_path)
        processor.patch_catalog_yaml()
    elif args.operation.lower() == 'extract-snapshot-images':
        processor = snapshot_processor(snapshot_json_path=args.snapshot_json_path, output_file_path=args.output_file_path, image_filter=args.image_filter)
        processor.extract_images_from_snapshot()

        # c = '/home/dchouras/RHODS/DevOps/FBC/main/catalog/v4.13/rhods-operator/catalog.yaml'
        # p = '/home/dchouras/RHODS/DevOps/FBC/rhoai-2.13/catalog/catalog-patch.yaml'
        # s = '/home/dchouras/RHODS/DevOps/FBC/fbc-utils/utils/single_bundle_catalog_semver.yaml'
        # o = 'output.yaml'
        # b = '/home/dchouras/RHODS/DevOps/FBC/fbc-utils/utils/build-config.yaml'
        # processor = fbc_processor(build_config_path=b, catalog_yaml_path=c, patch_yaml_path=p, single_bundle_path=s, output_file_path=o)
        # processor.patch_catalog_yaml()